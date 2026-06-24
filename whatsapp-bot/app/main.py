from fastapi import FastAPI
from fastapi.responses import FileResponse
from .database import engine, SessionLocal
from .models import Base, Product, Category
from .webhook import router as webhook_router
from .admin import router as admin_router
from .config import config

# Create database tables
Base.metadata.create_all(bind=engine)


def auto_seed():
    """Seeds the database with BlitzTech products if empty. Runs on every startup."""
    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            return  # Already has products, skip

        print("[Startup] No products found — seeding BlitzTech catalog...")

        # Categories
        consumer = Category(name="Consumer Electronics", description="TVs, laptops, and consumer devices")
        components = Category(name="Electronics Components", description="Microcontrollers, sensors, and dev boards")
        db.add_all([consumer, components])
        db.commit()
        db.refresh(consumer)
        db.refresh(components)

        # Products
        products = [
            Product(sku="CE-001", name="HP Laptop", price=480.00, stock_quantity=10,
                    description="HP laptop - ideal for work and study", category_id=consumer.id),
            Product(sku="CE-002", name="Samsung TV", price=850.00, stock_quantity=5,
                    description="Samsung flat screen TV", category_id=consumer.id),
            Product(sku="EC-001", name="ESP32", price=9.00, stock_quantity=10,
                    description="ESP32 Wi-Fi + Bluetooth microcontroller module", category_id=components.id),
            Product(sku="EC-002", name="Water Flow Sensor", price=1.00, stock_quantity=10,
                    description="Water flow sensor for liquid measurement projects", category_id=components.id),
            Product(sku="EC-003", name="MQ-4 Natural Gas Sensor", price=4.00, stock_quantity=10,
                    description="MQ-4 gas sensor for natural gas / methane detection", category_id=components.id),
            Product(sku="EC-004", name="Arduino Uno", price=8.00, stock_quantity=10,
                    description="Arduino Uno R3 microcontroller development board", category_id=components.id),
        ]
        db.add_all(products)
        db.commit()
        print(f"[Startup] Seeded {len(products)} products successfully.")

    except Exception as e:
        db.rollback()
        print(f"[Startup] Seed error: {e}")
    finally:
        db.close()


# Run auto-seed on startup
auto_seed()

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
