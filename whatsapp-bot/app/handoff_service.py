# DB session is injected from the caller — no local SessionLocal needed here
from .config import config
from .whatsapp_api import send_text
from .logger import setup_logger

logger = setup_logger(__name__)

async def escalate_to_human(phone: str, user_session, db=None):
    """Notifies human agent without silencing the bot. Bot remains active.
    db parameter accepted for signature consistency but not used (no DB writes here).
    """
    try:
        # Build clickable WhatsApp link for the agent
        # Strip non-digit chars from agent number to form valid wa.me link
        agent_number_raw = config.HUMAN_AGENT_NUMBER
        agent_number_clean = ''.join(c for c in agent_number_raw if c.isdigit())
        agent_link = f"https://wa.me/{agent_number_clean}"

        # 1. Notify Customer - bot stays active, include direct link
        customer_msg = (
            "🤝 I've notified one of our agents to assist you!\n\n"
            f"If you're in a hurry, you can message them directly on WhatsApp right now:\n"
            f"👉 {agent_link}\n\n"
            "In the meantime, I'm still here! You can continue browsing products, "
            "checking prices, or building a quotation."
        )
        await send_text(phone, customer_msg)

        # 2. Notify Agent with customer details
        agent_msg = (
            "🔔 *HUMAN HANDOFF REQUEST*\n"
            f"Customer Phone: {phone}\n"
            "Action Required: Please reach out to the customer directly to assist them."
        )
        await send_text(config.HUMAN_AGENT_NUMBER, agent_msg)
        
        logger.info(f"Handoff notification sent for {phone} - bot remains active")
    except Exception as e:
        logger.error(f"Error during human handoff: {str(e)}")

async def return_to_bot(phone: str, user_session, db):
    """Returns session to bot mode. Receives the single db session from the caller."""
    try:
        user_session.is_human_mode = False
        db.add(user_session)
        db.commit()

        msg = "🤖 Human agent has left the chat. I am back to assist you with products and quotes!"
        await send_text(phone, msg)
        
        logger.info(f"Session returned to bot for {phone}")
    except Exception as e:
        logger.error(f"Error returning to bot: {str(e)}")
