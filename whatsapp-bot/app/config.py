import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # App Settings
    APP_NAME = "WhatsApp Chatbot"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Anthropic Claude Settings
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    CLAUDE_MODEL = "claude-3-haiku-20240307"

    # Meta WhatsApp API Settings
    PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
    WHATSAPP_API_VERSION = "v21.0"

    # Company Information
    COMPANY_NAME = "BlitzTech Electronics"
    COMPANY_ADDRESS = "Zimpost Building, 4th Floor, Harare, Zimbabwe"
    COMPANY_PHONE = "+263 78 000 0000"
    COMPANY_EMAIL = "info@blitztechelectronics.co.zw"
    MAPS_LINK = "https://maps.google.com/?q=Zimpost+Building+Harare+Zimbabwe"
    BUSINESS_HOURS = "Mon-Fri: 8AM - 5PM | Sat: 8AM - 1PM"

    # Human Handoff
    HUMAN_AGENT_NUMBER = os.getenv("HUMAN_AGENT_NUMBER", "+1234567890")

    # Database Settings
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/chatbot.db")

    # Admin Settings
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

config = Config()
