import httpx
import os
from dotenv import load_dotenv
from .config import config
from .logger import setup_logger

logger = setup_logger(__name__)


def _get_headers():
    """Build headers fresh every call so token updates are picked up."""
    load_dotenv(override=True)
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", config.WHATSAPP_TOKEN)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _get_base_url():
    return f"https://graph.facebook.com/{config.WHATSAPP_API_VERSION}/{config.PHONE_NUMBER_ID}/messages"

async def send_text(to: str, message: str):
    """Sends a plain text message."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    return await _send_request(payload)

async def send_buttons(to: str, body: str, buttons: list):
    """
    Sends interactive button messages.
    buttons: list of dicts with 'id' and 'title'
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": b["id"], "title": b["title"]}
                    } for b in buttons
                ]
            }
        }
    }
    return await _send_request(payload)

async def send_list(to: str, body: str, button_text: str, sections: list):
    """
    Sends interactive list messages.
    sections: list of dicts containing rows
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
    }
    return await _send_request(payload)

async def upload_media(file_path: str, mime_type: str = "application/pdf"):
    """Uploads a local file to Meta's Media API and returns the media_id."""
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", config.WHATSAPP_TOKEN)
    upload_url = f"https://graph.facebook.com/{config.WHATSAPP_API_VERSION}/{config.PHONE_NUMBER_ID}/media"
    
    async with httpx.AsyncClient(timeout=30.0) as client_http:
        try:
            with open(file_path, "rb") as f:
                files = {
                    "file": (os.path.basename(file_path), f, mime_type),
                }
                data = {
                    "messaging_product": "whatsapp",
                    "type": mime_type,
                }
                headers = {"Authorization": f"Bearer {token}"}
                response = await client_http.post(upload_url, headers=headers, data=data, files=files)
                response.raise_for_status()
                result = response.json()
                media_id = result.get("id")
                logger.info(f"Media uploaded successfully. media_id: {media_id}")
                return media_id
        except httpx.HTTPStatusError as e:
            logger.error(f"Media upload HTTP error ({e.response.status_code}): {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Media upload error: {str(e)}")
            return None


async def send_document(to: str, file_path: str, filename: str):
    """Uploads a local PDF file to Meta and sends it as a document message."""
    # Step 1: Upload the file to get a media_id
    media_id = await upload_media(file_path)
    if not media_id:
        logger.error(f"Failed to upload document {file_path}, sending text fallback")
        await send_text(to, f"📄 Your quotation ({filename}) has been generated but I couldn't attach the PDF. Please contact us to receive it.")
        return None
    
    # Step 2: Send the document using the media_id
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {
            "id": media_id,
            "filename": filename
        }
    }
    return await _send_request(payload)

async def _send_request(payload: dict, max_retries: int = 3):
    """Internal helper to send the POST request to Meta with retry logic."""
    import asyncio
    last_error = None
    for attempt in range(1, max_retries + 1):
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(_get_base_url(), headers=_get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                logger.info(f"WhatsApp message sent successfully (attempt {attempt})")
                return result
            except httpx.HTTPStatusError as e:
                logger.error(f"WhatsApp API Error ({e.response.status_code}): {e.response.text}")
                return None  # Don't retry HTTP errors (auth, bad request, etc.)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as e:
                last_error = e
                logger.warning(f"WhatsApp send attempt {attempt}/{max_retries} failed (network): {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error sending WhatsApp message (attempt {attempt}): {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
    
    logger.error(f"WhatsApp send FAILED after {max_retries} attempts. Last error: {str(last_error)}")
    return None
