import asyncio
import sys
from unittest.mock import patch
from app.database import SessionLocal, engine, Base
from app.models import UserSession
from app.bot_handler import handle_message

# Fix console encoding for emojis on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

async def mock_send_text(to: str, message: str):
    print(f"\n[BOT] (Text to {to}):\n{message}\n")

async def mock_send_buttons(to: str, body: str, buttons: list):
    print(f"\n[BOT] (Buttons to {to}):\n{body}")
    for b in buttons:
        print(f" - [{b['title']}] (ID: {b['id']})")
    print()

async def mock_send_list(to: str, body: str, button_text: str, sections: list):
    print(f"\n[BOT] (List to {to}):\n{body}")
    print(f"Button: {button_text}")
    for s in sections:
        print(f" Section: {s.get('title')}")
        for r in s.get("rows", []):
            print(f"  - {r.get('title')} (ID: {r.get('id')})")
    print()

async def mock_send_document(to: str, file_url: str, filename: str):
    print(f"\n[BOT] (Document to {to}):\nFile: {filename}\nURL: {file_url}\n")


async def mock_detect_intent(message: str) -> dict:
    msg_lower = message.lower()
    if "hello" in msg_lower:
        return {"intent": "greeting"}
    elif "resistors" in msg_lower:
        return {"intent": "browse_products", "category": "resistors"}
    elif "price of 2n2222" in msg_lower:
        return {"intent": "check_price", "product_name": "2N2222"}
    elif "quotation" in msg_lower:
        return {"intent": "add_to_quote", "product_name": "2N2222", "quantity": 10}
    elif "located" in msg_lower:
        return {"intent": "view_location"}
    elif "human" in msg_lower:
        return {"intent": "talk_to_human"}
    else:
        return {"intent": "unknown"}

async def run_tests():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    phone = "1234567890"

    session = db.query(UserSession).filter(UserSession.phone_number == phone).first()
    if not session:
        session = UserSession(phone_number=phone)
        db.add(session)
        db.commit()
        db.refresh(session)
    
    session.is_human_mode = False
    session.quote_items = []
    db.commit()

    test_messages = [
        "hello",
        "show me resistors",
        "price of 2N2222",
        "I want a quotation for 10x 2N2222",
        "where are you located",
        "talk to human"
    ]

    print("Starting Intent Simulation...")
    print("="*50)

    patchers = [
        patch('app.bot_handler.send_text', mock_send_text),
        patch('app.bot_handler.send_buttons', mock_send_buttons),
        patch('app.quotation_service.send_text', mock_send_text),
        patch('app.handoff_service.send_text', mock_send_text),
        patch('app.bot_handler.detect_intent', mock_detect_intent),
    ]

    for p in patchers:
        p.start()

    try:
        for msg in test_messages:
            print(f"\n>> [USER]: {msg}")
            await handle_message(phone, msg, session)
            db.commit() 
            await asyncio.sleep(0.5)
    finally:
        for p in patchers:
            p.stop()
        db.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_tests())
