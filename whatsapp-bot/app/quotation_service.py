import datetime
from .models import Product, UserSession, Quotation
# DB session is injected from the caller — no local SessionLocal needed here
from .whatsapp_api import send_text
from .logger import setup_logger

logger = setup_logger(__name__)

def generate_quote_ref(db) -> str:
    """Generates a reference number like QT-2026-0001."""
    year = datetime.datetime.now().year
    count = db.query(Quotation).count() + 1
    return f"QT-{year}-{count:04d}"


async def request_quotation_start(phone: str, user_session: UserSession, db):
    """
    Step 1: Called when customer says 'request quote'.
    Sets awaiting_quote flag and prompts the customer to list their products.
    Receives the single database session from the caller to avoid dual-session conflicts.
    """
    from sqlalchemy.orm.attributes import flag_modified
    try:
        # Reset cart and set awaiting flag
        context = user_session.context_data or {}
        context["awaiting_quote"] = True
        context["cart"] = []
        user_session.context_data = context
        flag_modified(user_session, "context_data")
        db.add(user_session)
        db.commit()

        msg = (
            "🛒 *Great! Let's build your quotation.*\n\n"
            "Please list the products and quantities you need in one message. For example:\n"
            "_5 esp32, 2 arduino, 10 capacitors, 1 keypad_\n\n"
            "I will check what's in stock and generate your quotation!"
        )
        await send_text(phone, msg)
    except Exception as e:
        logger.error(f"Error starting quotation: {str(e)}")




async def build_quotation_from_list(phone: str, message: str, user_session: UserSession, db, session_history: list = None):
    """
    Step 2: Called when customer has listed their products.
    Parses each item, checks stock, builds the cart, and sends a plain text quotation.

    db: the single database session injected from the caller (webhook.py) to avoid
    dual-session conflicts and SQLite lock contention.
    session_history: kept for API compatibility but no longer used for product resolution.
    Product names are now tracked explicitly via context_data["pending_product"].
    """
    import anthropic, json, re
    from .config import config
    from sqlalchemy.orm.attributes import flag_modified

    try:
        # --- Context injection: resolve bare number by consuming saved pending_product ---
        resolved_message = message.strip()
        msg_lower = resolved_message.lower()
        context = user_session.context_data or {}
        pending_product = context.get("pending_product")

        # 1. Guard against conversational questions replacing pending state
        # If user explicitly wants to cancel/correct
        cancel_keywords = {
            "cancel", "no", "wrong", "edit", "change", 
            "wait", "stop", "restart", "redo", "start over", 
            "clear", "reset", "mistake"
        }
        if any(kw in msg_lower for kw in cancel_keywords):
            if "pending_product" in context:
                context.pop("pending_product", None)
            context["awaiting_quote"] = False
            user_session.context_data = context
            flag_modified(user_session, "context_data")
            db.add(user_session)
            db.commit()
            await send_text(phone, "No problem, I've cleared your pending item. Let's start over — what do you need?")
            return

        has_digit = any(char.isdigit() for char in resolved_message)

        if pending_product:
            if has_digit:
                # User replied with a quantity after we asked — combine them
                resolved_message = f"{resolved_message} {pending_product}"
                logger.info(
                    f"Resolved bare number '{message}' + pending_product '{pending_product}' "
                    f"→ '{resolved_message}' for {phone}."
                )
                # We do NOT pop pending_product here yet. We wait for AI to successfully parse.
            else:
                # User asked a question or sent text without digits.
                # Leave pending_product intact so bot remembers what they are talking about.
                logger.info(f"Conversational question detected while pending '{pending_product}'. Asking for quantity again.")
                await send_text(phone, f"Regarding the '{pending_product}', how many units would you like? (Or reply 'cancel' to clear it).")
                return
        else:
            # No pending product. Guard: require at least one digit before parsing
            if not has_digit:
                logger.info(
                    f"No quantity detected in message '{resolved_message}' from {phone}. "
                    f"Saving as pending_product and prompting for quantity."
                )
                context["awaiting_quote"] = True
                context["pending_product"] = resolved_message.strip()
                user_session.context_data = context
                flag_modified(user_session, "context_data")
                db.add(user_session)
                db.commit()
                await send_text(phone, "How many units of that would you like?")
                return

        # --- Use Claude to parse product list from the customer's free-text message ---
        client = anthropic.AsyncAnthropic(
            api_key=config.ANTHROPIC_API_KEY,
            max_retries=5
        )
        parse_prompt = f"""
        Your sole function is to extract product items and quantities into a structured JSON format. 
        You are a rigid data extraction utility, not a conversational assistant. 
        Do NOT answer user questions, do NOT provide explanations, do NOT define terms, and do NOT add conversational filler. 
        Output raw JSON data only.

        Extract all products and quantities from this customer message.
        Return ONLY a JSON array like: [{{"product": "esp32", "quantity": 5}}, ...]
        If no quantity is mentioned, default to 1.
        
        Message: "{resolved_message}"
        """
        response = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": parse_prompt}]
        )
        content = response.content[0].text
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        
        if not json_match:
            await send_text(phone, "I couldn't understand your list. Please try again, e.g.: _5 esp32, 2 arduino, 1 keypad_")
            return
            
        # Successfully parsed valid quantity - consume pending_product
        if pending_product:
            context.pop("pending_product", None)
            user_session.context_data = context
            flag_modified(user_session, "context_data")
            db.add(user_session)
            db.commit()
            
        requested_items = json.loads(json_match.group())

        # --- Check each item against stock ---
        cart = []
        not_found = []
        out_of_stock = []

        for item in requested_items:
            product_name = item.get("product", "")
            qty = int(item.get("quantity", 1))

            product = db.query(Product).filter(
                Product.name.ilike(f"%{product_name}%")
            ).first()

            if not product:
                not_found.append(product_name)
                continue

            if product.stock_quantity <= 0:
                out_of_stock.append(product.name)
                continue

            # Cap quantity at available stock
            actual_qty = min(qty, product.stock_quantity)
            cart.append({
                "sku": product.sku,
                "name": product.name,
                "qty": actual_qty,
                "price": product.price
            })

        # --- If nothing could be added ---
        if not cart:
            issues = ""
            if not_found:
                issues += f"❌ Not found: {', '.join(not_found)}\n"
            if out_of_stock:
                issues += f"⚠️ Out of stock: {', '.join(out_of_stock)}\n"
            await send_text(phone, f"Sorry, none of the products you listed are available:\n\n{issues}\nPlease try again with different products.")
            # Clear the awaiting flag
            context = user_session.context_data or {}
            context["awaiting_quote"] = False
            user_session.context_data = context
            flag_modified(user_session, "context_data")
            db.add(user_session)
            db.commit()
            return

        # --- Save cart and clear awaiting flag ---
        context = user_session.context_data or {}
        context["cart"] = cart
        context["awaiting_quote"] = False
        user_session.context_data = context
        flag_modified(user_session, "context_data")
        db.add(user_session)
        db.commit()

        # --- Generate Quote Reference ---
        quote_ref = generate_quote_ref(db)
        total_amount = sum(item['qty'] * item['price'] for item in cart)

        new_quote = Quotation(
            phone_number=phone,
            items=cart,
            total_amount=total_amount,
            status="pending"
        )
        db.add(new_quote)
        db.commit()

        # --- Build & Send Plain Text Quotation ---
        current_date = datetime.datetime.now()
        valid_until = current_date + datetime.timedelta(days=30)

        quotation = f"📋 *OFFICIAL QUOTATION*\n"
        quotation += f"━━━━━━━━━━━━━━━━━━━━\n"
        quotation += f"🏢 *{config.COMPANY_NAME}*\n"
        quotation += f"📄 Ref: *{quote_ref}*\n"
        quotation += f"📅 Date: {current_date.strftime('%Y-%m-%d')}\n"
        quotation += f"⏳ Valid Until: {valid_until.strftime('%Y-%m-%d')}\n"
        quotation += f"━━━━━━━━━━━━━━━━━━━━\n\n"

        quotation += f"📦 *Items:*\n"
        for i, item in enumerate(cart, 1):
            line_total = item['qty'] * item['price']
            quotation += f"{i}. {item['name']}\n"
            quotation += f"   Qty: {item['qty']} × ${item['price']:,.2f} = *${line_total:,.2f}*\n"

        quotation += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        quotation += f"💰 *GRAND TOTAL: ${total_amount:,.2f}*\n"
        quotation += f"━━━━━━━━━━━━━━━━━━━━\n"

        if not_found:
            quotation += f"\n❌ *Not Found:* {', '.join(not_found)}"
        if out_of_stock:
            quotation += f"\n⚠️ *Out of Stock:* {', '.join(out_of_stock)}"

        quotation += f"\n\n💳 *Payment:* 100% upfront via Bank Transfer or Mobile Money\n"
        quotation += f"📍 *Collect at:* {config.COMPANY_ADDRESS}\n"
        quotation += f"📞 *Contact:* {config.COMPANY_PHONE}\n\n"
        quotation += f"_This quotation is valid for 30 days._\n"
        quotation += f"_Thank you for choosing {config.COMPANY_NAME}!_"

        await send_text(phone, quotation)

        # --- Lock state: quotation sent, now await customer confirmation ---
        context = user_session.context_data or {}
        context["awaiting_quote"] = False
        context["awaiting_confirmation"] = True
        user_session.context_data = context
        flag_modified(user_session, "context_data")
        db.add(user_session)
        db.commit()
        logger.info(f"Quotation sent to {phone}. State set to awaiting_confirmation.")

    except Exception as e:
        logger.error(f"Error building quotation from list: {str(e)}")
        await send_text(phone, "I encountered an error while building your quotation. Please try again.")
