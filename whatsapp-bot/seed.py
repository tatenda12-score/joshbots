from app.database import SessionLocal, init_db
from app.models import Product, Category

def seed_data():
    init_db()
    db = SessionLocal()

    try:
        # --- Clear old demo data ---
        print("Clearing old demo data...")
        db.query(Product).delete()
        db.query(Category).delete()
        db.commit()

        # --- Create Categories ---
        print("Creating categories...")
        consumer = Category(name="Consumer Electronics", description="TVs, laptops, and consumer devices")
        components = Category(name="Electronics Components", description="Microcontrollers, sensors, and dev boards")
        db.add_all([consumer, components])
        db.commit()
        db.refresh(consumer)
        db.refresh(components)

        # --- Real BlitzTech Products ---
        products = [
            # Consumer Electronics
            {
                "sku": "CE-001", "name": "HP Laptop", "category_id": consumer.id,
                "price": 480.00, "stock_quantity": 10,
                "description": "HP laptop - ideal for work and study"
            },
            {
                "sku": "CE-002", "name": "Samsung TV", "category_id": consumer.id,
                "price": 850.00, "stock_quantity": 5,
                "description": "Samsung flat screen TV"
            },

            # Electronics Components
            {
                "sku": "EC-001", "name": "ESP32", "category_id": components.id,
                "price": 9.00, "stock_quantity": 10,
                "description": "ESP32 Wi-Fi + Bluetooth microcontroller module"
            },
            {
                "sku": "EC-002", "name": "Water Flow Sensor", "category_id": components.id,
                "price": 1.00, "stock_quantity": 10,
                "description": "Water flow sensor for liquid measurement projects"
            },
            {
                "sku": "EC-003", "name": "MQ-4 Natural Gas Sensor", "category_id": components.id,
                "price": 4.00, "stock_quantity": 10,
                "description": "MQ-4 gas sensor for natural gas / methane detection"
            },
            {
                "sku": "EC-004", "name": "Arduino Uno", "category_id": components.id,
                "price": 8.00, "stock_quantity": 10,
                "description": "Arduino Uno R3 microcontroller development board"
            },
        ]

        print("Adding products...")
        for p in products:
            db.add(Product(**p))

        db.commit()
        print("SUCCESS: Database seeded with", len(products), "products in", 2, "categories.")

        # Verify
        print("\n--- Loaded Products ---")
        for p in db.query(Product).all():
            cat = db.query(Category).filter_by(id=p.category_id).first()
            print(f"  [{cat.name}] {p.name} | Price: ${p.price} | Stock: {p.stock_quantity}")

    except Exception as e:
        db.rollback()
        print("ERROR seeding database:", e)
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
