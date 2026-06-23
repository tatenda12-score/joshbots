from fastapi import FastAPI
from fastapi.responses import FileResponse
from .database import engine
from .models import Base
from .webhook import router as webhook_router
from .admin import router as admin_router
from .config import config

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI App
app = FastAPI(
    title=config.APP_NAME,
    description="Professional WhatsApp Sales Chatbot with AI and Quotation PDF Generation",
    version="1.0.0"
)

# Include Routers
app.include_router(webhook_router)
app.include_router(admin_router)

@app.get("/admin-panel")
async def admin_panel():
    """Serves the frontend admin panel."""
    return FileResponse("admin_panel/index.html")

@app.get("/")
async def root():
    """Root endpoint to confirm the API is healthy and running."""
    return {
        "status": "online",
        "bot_name": config.APP_NAME,
        "message": "WhatsApp Webhook is active and listening for events."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
