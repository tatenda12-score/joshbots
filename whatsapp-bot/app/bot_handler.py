import datetime
from .intent_engine import process_message
from .whatsapp_api import send_text, send_buttons
from .quotation_service import request_quotation_start, build_quotation_from_list
from .location_service import get_location_message
from .handoff_service import escalate_to_human
# DB session is injected from webhook.py — no local SessionLocal needed here
from .logger import setup_logger
from sqlalchemy.orm.attributes import flag_modified

logger = setup_logger(__name__)


def get_history(session) -> list:
    """Retrieves conversation history from session context."""
    context = session.context_data or {}
    return context.get("history", [])


def save_to_history(session, db, user_msg: str, bot_msg: str):
    """Appends the latest exchange to conversation history (keeps last 10)."""
    context = session.context_data or {}
    history = context.get("history", [])

    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": bot_msg})

    # Keep only last 10 messages (5 exchanges) to avoid bloat
    context["history"] = history[-10:]
    session.context_data = context
    flag_modified(session, "context_data")
    db.add(session)
    db.commit()


async def handle_message(phone: str, message: str, session, db):
    """
    Main orchestrator for incoming WhatsApp messages.
    Uses Claude AI with full context to reason and respond naturally.
    Receives the single database session from the caller (webhook.py) to avoid
    dual-session conflicts and SQLite lock contention.
    """
    try:
        # 0. Session timeout check (2 hours inactivity resets context)
        now = datetime.datetime.utcnow()
        if session.last_interaction and (now - session.last_interaction) > datetime.timedelta(hours=2):
            logger.info(f"Session expired for {phone}. Resetting.")
            session.is_human_mode = False
            session.context_data = {}
            flag_modified(session, "context_data")
            await send_text(phone, "⏱️ Your previous session expired. Let's start fresh! How can I help you today?")

        session.last_interaction = now
        db.add(session)
        db.commit()

        # 1. Skip if in human mode
        if session.is_human_mode:
            logger.info(f"Bypassing bot for {phone} (Human Mode active)")
            return

        # 2. Basic input validation
        if not message or not message.strip():
            return
        if len(message) > 1500:
            await send_text(phone, "Your message is too long. Please keep it shorter and try again!")
            return

        # Map interactive button IDs to natural language queries for Claude to understand
        button_mapping = {
            "browse_cat": "Show me your products",
            "get_quote": "I want to request a quotation",
            "human_agent": "I want to talk to a human agent"
        }
        message_cleaned = message.strip()
        if message_cleaned in button_mapping:
            message = button_mapping[message_cleaned]

        # Universal reset command — clears all stuck states
        reset_triggers = {"reset", "start over", "restart", "clear", "menu", "/start", "/reset"}
        if message_cleaned.lower() in reset_triggers:
            session.context_data = {}
            session.is_human_mode = False
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(session, "context_data")
            db.add(session)
            db.commit()
            greeting_msg = "Session cleared! How can I help you? I can check prices, stock, or build a quotation."
            buttons = [
                {"id": "browse_cat", "title": "Browse Products"},
                {"id": "get_quote", "title": "Request Quote"},
                {"id": "human_agent", "title": "Talk to Human"},
            ]
            await send_buttons(phone, greeting_msg, buttons)
            logger.info(f"Session reset by {phone}")
            return

        # 3. Check if awaiting quotation product list
        context = session.context_data or {}
        if context.get("awaiting_quote"):
            logger.info(f"Awaiting quote list from {phone}, processing their product list")
            history = get_history(session)
            await build_quotation_from_list(phone, message, session, db, history)
            return

        # 3b. Check if awaiting confirmation of a previously sent quotation
        if context.get("awaiting_confirmation"):
            msg_lower = message_cleaned.lower()
            confirm_keywords = {"proceed", "yes", "confirm", "i want it"}
            # Broad escape hatch: cancellations, corrections, frustration signals
            cancel_keywords = {
                "cancel", "no", "wrong", "edit", "change",
                "wait", "stop", "fuck", "shit", "restart", "redo",
                "start over", "clear", "reset", "mistake",
            }

            if any(kw in msg_lower for kw in confirm_keywords):
                # Customer confirmed — clear state & cart
                # CRITICAL: force is_human_mode=False so the bot never goes silent
                context["awaiting_confirmation"] = False
                context["cart"] = []
                session.context_data = context
                session.is_human_mode = False
                flag_modified(session, "context_data")
                db.add(session)
                db.commit()
                logger.info(f"Order confirmed by {phone}. Human mode explicitly cleared.")
                await send_text(
                    phone,
                    "✅ Great! Your order has been logged. What else can I help you find today?"
                )
                return

            elif any(kw in msg_lower for kw in cancel_keywords):
                # Customer cancelled or wants to correct — clear state & cart
                # CRITICAL: force is_human_mode=False so the bot never goes silent
                context["awaiting_confirmation"] = False
                context["cart"] = []
                session.context_data = context
                session.is_human_mode = False
                flag_modified(session, "context_data")
                db.add(session)
                db.commit()
                logger.info(f"Quotation cleared/cancelled by {phone} (trigger: '{msg_lower}'). Human mode explicitly cleared.")
                await send_text(
                    phone,
                    "No problem, I've cleared that quotation. Let's start over — what do you need?"
                )
                return

            else:
                # Unrecognised reply while in confirmation state — prompt again
                # Bypass Claude entirely and return a static, hardcoded guardrails message
                await send_text(
                    phone,
                    'Please reply "proceed" to confirm your quote, or "cancel" to start over.'
                )
                return

        # 4. Get conversation history for context
        history = get_history(session)

        # 5. Let Claude reason about the message with full context
        result = await process_message(message, history, db)

        action = result.get("action", "chat")
        ai_message = result.get("message", "")
        secondary_action = result.get("secondary_action")
        product_name = result.get("product_name")
        category = result.get("category")

        logger.info(f"Action for {phone}: {action} | secondary: {secondary_action}")

        # 6. Route to structured actions or send Claude's response directly
        if action == "greeting":
            greeting_msg = "Hii 👋 Welcome to *BlitzTech Electronics*! How can I help you?"
            buttons = [
                {"id": "browse_cat", "title": "Browse Products"},
                {"id": "get_quote", "title": "Request Quote"},
                {"id": "human_agent", "title": "Talk to Human"},
            ]
            await send_buttons(phone, greeting_msg, buttons)
            save_to_history(session, db, message, greeting_msg)

        elif action == "browse_categories":
            await send_text(phone, ai_message)
            save_to_history(session, db, message, ai_message)

        elif action == "browse_products":
            await send_text(phone, ai_message)
            save_to_history(session, db, message, ai_message)

        elif action == "check_price":
            await send_text(phone, ai_message)
            save_to_history(session, db, message, ai_message)

        elif action == "request_quote":
            quantity = result.get("quantity")
            if product_name and quantity:
                # Claude already knows WHAT and HOW MANY — build quote directly, no double-prompt
                logger.info(f"Direct quote: {quantity}x {product_name} for {phone}")
                await build_quotation_from_list(phone, f"{quantity} {product_name}", session, db, history)
                save_to_history(session, db, message, ai_message)
            else:
                # Product or quantity unknown — start the formal quote flow
                await send_text(phone, ai_message)
                save_to_history(session, db, message, ai_message)
                await request_quotation_start(phone, session, db)

        elif action == "view_location":
            location_msg = get_location_message()
            await send_text(phone, location_msg)
            save_to_history(session, db, message, location_msg)

            # Handle secondary intent if present (e.g. customer also wants to browse/buy)
            if secondary_action == "browse_products":
                followup = "👆 There's our location!\n\nNow, what products are you looking for? I can show you what we have in stock."
                await send_text(phone, followup)
            elif secondary_action == "request_quote":
                followup = "👆 There's our location!\n\nReady to build a quotation? Just tell me what products and quantities you need."
                await send_text(phone, followup)

        elif action == "talk_to_human":
            # Send Claude's empathetic bridging message before handing off
            if ai_message:
                await send_text(phone, ai_message)
            await escalate_to_human(phone, session)
            save_to_history(session, db, message, ai_message)

        elif action == "out_of_scope":
            # Send Claude's context-aware, empathetic message first
            if ai_message:
                await send_text(phone, ai_message)
            # Then follow up with quick-reply buttons to guide them back
            redirect_msg = "Here's what I *can* help you with:"
            buttons = [
                {"id": "browse_cat", "title": "Browse Products"},
                {"id": "human_agent", "title": "Talk to Human"},
            ]
            await send_buttons(phone, redirect_msg, buttons)
            save_to_history(session, db, message, ai_message)

        elif action == "gibberish":
            fallback_msg = "I didn't quite catch that! I can help you find our business location, check product inquiries, or loop in a human agent. What can I help you with?"
            buttons = [
                {"id": "human_agent", "title": "Talk to Human"},
                {"id": "browse_cat", "title": "Browse Products"},
            ]
            await send_buttons(phone, fallback_msg, buttons)
            save_to_history(session, db, message, fallback_msg)

        else:
            # Fallback — send Claude's message if available, then guide with buttons
            if ai_message:
                await send_text(phone, ai_message)
            redirect_msg = "Here's what I *can* help you with:"
            buttons = [
                {"id": "browse_cat", "title": "Browse Products"},
                {"id": "human_agent", "title": "Talk to Human"},
            ]
            await send_buttons(phone, redirect_msg, buttons)
            save_to_history(session, db, message, ai_message)

    except Exception as e:
        logger.error(f"Error in handle_message for {phone}: {str(e)}")
        await send_text(phone, "I encountered an unexpected error. Please try again!")
