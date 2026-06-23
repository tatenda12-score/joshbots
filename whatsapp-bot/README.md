# WhatsApp Chatbot

A Python-based WhatsApp chatbot using FastAPI and Anthropic's Claude.

## Project Structure
- `app/`: Source code
- `data/`: Database files (SQLite)
- `venv/`: Virtual environment

## Setup
1. Copy `.env.example` to `.env` and fill in your credentials.
2. Activate the virtual environment: `.\venv\Scripts\activate`
3. Run the server: `uvicorn app.main:app --reload`
