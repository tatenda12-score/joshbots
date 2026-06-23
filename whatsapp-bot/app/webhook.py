import time
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from .config import config
from .database import SessionLocal
from .models import UserSession
from .bot_handler import handle_message
from .handoff_service import return_to_bot
from .logger import setup_logger
from .whatsapp_api import send_text

router = APIRouter()
logger = setup_logger(__name__)

# In-memory dictionary for rate limiting: phone_number -> list of timestamps
rate_limit_cache = {}

def check_rate_limit(phone: str) -> bool:
    """Checks if a phone number has exceeded 10 messages per minute."""
    current_time = time.time()
    if phone not in rate_limit_cache:
        rate_limit_cache[phone] = []
    
    # Filter out timestamps older than 60 seconds
    rate_limit_cache[phone] = [ts for ts in rate_limit_cache[phone] if current_time - ts < 60]
    
    if len(rate_limit_cache[phone]) >= 10:
        return False
        
    rate_limit_cache[phone].append(current_time)
    return True

from fastapi.responses import PlainTextResponse

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """Verifies the webhook with Meta WhatsApp API."""
    if hub_mode == "subscribe" and hub_verify_token == config.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(content=hub_challenge)
    
    logger.warning("Webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

async def process_webhook_message_job(phone: str, msg: dict):
    db = SessionLocal()
    try:
        msg_type = msg.get("type")
        
        # Intercept media and non-text types (audio, image, video, sticker, document, etc.)
        if msg_type not in ["text", "interactive"]:
            logger.info(f"Intercepted media/non-text message of type: {msg_type} from {phone}")
            agent_number_raw = config.HUMAN_AGENT_NUMBER
            agent_number_clean = ''.join(c for c in agent_number_raw if c.isdigit())
            fallback_media_text = (
                "I can't process images, audios, videos, or stickers just yet! "
                "Please type your message out in text, or if you prefer, you can click here "
                f"to chat directly with a human agent right now: wa.me/{agent_number_clean}"
            )
            await send_text(phone, fallback_media_text)
            return

        message_body = ""
        # Handle Text Messages
        if msg_type == "text":
            message_body = msg.get("text", {}).get("body", "")
        
        # Handle Button Replies
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                message_body = interactive.get("button_reply", {}).get("id", "")
            elif interactive.get("type") == "list_reply":
                message_body = interactive.get("list_reply", {}).get("id", "")

        if not message_body:
            return

        # Get or Create User Session
        session = db.query(UserSession).filter(UserSession.phone_number == phone).first()
        if not session:
            session = UserSession(phone_number=phone)
            db.add(session)
            db.commit()
            db.refresh(session)

        # Route Command
        if message_body.strip().lower() == "#bot":
            await return_to_bot(phone, session, db)
        else:
            await handle_message(phone, message_body, session, db)
            
    except Exception as e:
        logger.error(f"Error in background message processing: {str(e)}")
    finally:
        db.close()

@router.post("/webhook")
async def handle_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
    """
    Receives incoming WhatsApp messages and interactive replies.
    """
    payload = await request.json()
    
    try:
        # 1. Parse Meta WhatsApp Payload
        if "entry" in payload:
            for entry in payload["entry"]:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if "messages" in value:
                        for msg in value["messages"]:
                            phone = msg.get("from")
                            if not phone:
                                continue
                            
                            # Enforce Rate Limiting (10 messages / minute)
                            if not check_rate_limit(phone):
                                logger.warning(f"Rate limit exceeded for {phone}")
                                continue

                            # Queue the message processing in a background task
                            background_tasks.add_task(process_webhook_message_job, phone, msg)

        return {"status": "success"}
    
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}
