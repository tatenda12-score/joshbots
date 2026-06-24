import datetime
from .intent_engine import process_message
from .whatsapp_api import send_text, send_buttons
from .quotation_service import build_quotation_from_list
from .location_service import get_location_message
from .handoff_service import escalate_to_human
from .logger import setup_logger
from sqlalchemy.orm.attributes import flag_modified

logger = setup_logger(__name__)


def get_history(session) -> list:
    """Retrieves conversation history from session context."""
    context = session.context_data or {}
    return context.get("history", [])


def save_to_history(session, db, user_msg: str, bot_msg: str):
    """Appends the latest exchange to conversation history (keeps last 20 messages = 10 exchanges)."""
    context = session.context_data or {}
    history = context.get("history", [])

    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": bot_msg})

    # Keep last 20 messages (10 exchanges) for better memory
    context["history"] = history[-20:]
    session.context_data = context
    flag_modified(session, "context_data")
    db.add(session)
    db.commit()


async def handle_message(phone: str, message: str, session, db):
    """
    Main orchestrator. Claude AI reasons about every message using full conversation
    history as memory. No blocking state machines — customers can change topics freely.
    """
    try:
        # 0. Session timeout: 4 hours inactivity resets context
        now = datetime.datetime.utcnow()
        if session.last_interaction and (now - session.last_interaction) > datetime.timedelta(hours=4):
            logger.info(f"Session expired for {phone}. Resetting.")
            session.context_data = {}
            session.is_human_mode = False
            flag_modified(session, "context_data")

        session.last_interaction = now
        db.add(session)
        db.commit()

        # 1. Skip if human agent is handling
        if session.is_human_mode:
            logger.info(f"Bypassing bot for {phone} (Human Mode active)")
            return

        # 2. Basic validation
        if not message or not message.strip():
            return
        if len(message) > 1500:
            await send_text(phone, "Your message is too long. Please keep it under 1500 characters.")
            return

        # 3. Map button IDs to natural language
        button_mapping = {
            "browse_cat": "Show me your products",
            "get_quote": "I want a quotation",
            "human_agent": "I want to talk to a human agent"
        }
        message_cleaned = message.strip()
        if message_cleaned in button_mapping:
            message = button_mapping[message_cleaned]

        # 4. Universal reset — clears stuck states
        reset_triggers = {"reset", "start over", "restart", "menu", "/start", "/reset"}
        if message_cleaned.lower() in reset_triggers:
            session.context_data = {}
            session.is_human_mode = False
            flag_modified(session, "context_data")
            db.add(session)
            db.commit()
            greeting_msg = "Fresh start! How can I help you today?"
            buttons = [
                {"id": "browse_cat", "title": "Browse Products"},
                {"id": "get_quote", "title": "Request Quote"},
                {"id": "human_agent", "title": "Talk to Human"},
            ]
            await send_buttons(phone, greeting_msg, buttons)
            logger.info(f"Session reset by {phone}")
            return

        # 5. Handle post-quotation confirmation (non-blocking — Claude can override)
        context = session.context_data or {}
        if context.get("awaiting_confirmation"):
            msg_lower = message_cleaned.lower()
            confirm_keywords = {"proceed", "yes", "confirm", "send it", "okay", "ok", "approved", "go ahead"}
            cancel_keywords = {"cancel", "no thanks", "nope", "never mind", "nevermind", "start over", "different", "change"}

            if any(kw in msg_lower for kw in confirm_keywords):
                context["awaiting_confirmation"] = False
                context["cart"] = []
                session.context_data = context
                session.is_human_mode = False
                flag_modified(session, "context_data")
                db.add(session)
                db.commit()
                reply = "Your order has been noted! Our team will follow up shortly. Is there anything else I can help with?"
                await send_text(phone, reply)
                save_to_history(session, db, message, reply)
                return

            elif any(kw in msg_lower for kw in cancel_keywords):
                context["awaiting_confirmation"] = False
                context["cart"] = []
                session.context_data = context
                session.is_human_mode = False
                flag_modified(session, "context_data")
                db.add(session)
                db.commit()
                reply = "Quotation cleared. What else can I help you with?"
                await send_text(phone, reply)
                save_to_history(session, db, message, reply)
                return

            else:
                # Customer said something else — let Claude handle it freely
                # (they might be asking a new question or changing topic)
                context["awaiting_confirmation"] = False
                context["cart"] = []
                session.context_data = context
                flag_modified(session, "context_data")
                db.add(session)
                db.commit()

        # 6. Get conversation history and let Claude reason about everything
        history = get_history(session)
        result = await process_message(message, history, db)

        action = result.get("action", "chat")
        ai_message = result.get("message", "")
        secondary_action = result.get("secondary_action")
        product_name = result.get("product_name")
        quantity = result.get("quantity")

        logger.info(f"Action for {phone}: {action} | product: {product_name} | qty: {quantity}")

        # 7. Route actions
        if action == "greeting":
            greeting_msg = "Hi! Welcome to *BlitzTech Electronics*. How can I help you?"
            buttons = [
                {"id": "browse_cat", "title": "Browse Products"},
                {"id": "get_quote", "title": "Request Quote"},
                {"id": "human_agent", "title": "Talk to Human"},
            ]
            await send_buttons(phone, greeting_msg, buttons)
            save_to_history(session, db, message, greeting_msg)

        elif action in ("browse_categories", "browse_products", "check_price"):
            await send_text(phone, ai_message)
            save_to_history(session, db, message, ai_message)

        elif action == "request_quote":
            if product_name and quantity:
                # Claude extracted both product + quantity — build quote directly
                logger.info(f"Building direct quote: {quantity}x {product_name} for {phone}")
                await build_quotation_from_list(phone, f"{quantity} {product_name}", session, db, history)
                save_to_history(session, db, message, ai_message)
            elif product_name and not quantity:
                # Claude knows the product but needs quantity — ask naturally, no state lock
                await send_text(phone, ai_message)
                save_to_history(session, db, message, ai_message)
            else:
                # Claude needs more info — send its natural response
                await send_text(phone, ai_message)
                save_to_history(session, db, message, ai_message)

        elif action == "view_location":
            location_msg = get_location_message()
            await send_text(phone, location_msg)
            save_to_history(session, db, message, location_msg)
            if secondary_action == "browse_products":
                await send_text(phone, "What products are you looking for? I can check prices and stock.")
            elif secondary_action == "request_quote":
                await send_text(phone, "Ready to quote — just tell me what products and quantities you need.")

        elif action == "talk_to_human":
            if ai_message:
                await send_text(phone, ai_message)
            await escalate_to_human(phone, session)
            save_to_history(session, db, message, ai_message)

        elif action == "out_of_scope":
            if ai_message:
                await send_text(phone, ai_message)
            buttons = [
                {"id": "browse_cat", "title": "Browse Products"},
                {"id": "human_agent", "title": "Talk to Human"},
            ]
            await send_buttons(phone, "Here's what I can help with:", buttons)
            save_to_history(session, db, message, ai_message)

        elif action == "gibberish":
            fallback_msg = "I didn't catch that. I can help with prices, stock, quotations, or our location."
            buttons = [
                {"id": "browse_cat", "title": "Browse Products"},
                {"id": "human_agent", "title": "Talk to Human"},
            ]
            await send_buttons(phone, fallback_msg, buttons)
            save_to_history(session, db, message, fallback_msg)

        else:
            if ai_message:
                await send_text(phone, ai_message)
                save_to_history(session, db, message, ai_message)

    except Exception as e:
        logger.error(f"Error in handle_message for {phone}: {str(e)}")
        await send_text(phone, "Sorry, something went wrong on my end. Please try again!")
