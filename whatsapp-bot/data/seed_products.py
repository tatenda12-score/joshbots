import sys
import os

# Add the parent directory to sys.path to allow importing from the 'app' package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models import Base, Category, Product

def seed_database():
    """Seeds the database with electronic components and categories."""
    
    # 1. Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 2. Add Categories
        categories_data = [
            "Resistors", "Capacitors", "Transistors", "ICs", "Sensors", "Connectors"
        ]
        
        category_map = {}
        for cat_name in categories_data:
            existing = db.query(Category).filter(Category.name == cat_name).first()
            if not existing:
                category = Category(name=cat_name, description=f"Electronic {cat_name} components")
                db.add(category)
                db.commit()
                db.refresh(category)
                category_map[cat_name] = category.id
            else:
                category_map[cat_name] = existing.id

        # 3. Add Products
        products_data = [
            {"sku": "RES-001", "name": "10k Ohm Resistor 1/4W", "price": 0.05, "stock": 5000, "cat": "Resistors"},
            {"sku": "RES-002", "name": "1k Ohm Resistor 1/4W", "price": 0.05, "stock": 4500, "cat": "Resistors"},
            {"sku": "CAP-001", "name": "10uF Electrolytic Capacitor", "price": 0.15, "stock": 2000, "cat": "Capacitors"},
            {"sku": "CAP-002", "name": "100nF Ceramic Capacitor", "price": 0.08, "stock": 8000, "cat": "Capacitors"},
            {"sku": "TRA-001", "name": "2N2222 NPN Transistor", "price": 0.25, "stock": 1500, "cat": "Transistors"},
            {"sku": "TRA-002", "name": "IRFZ44N MOSFET", "price": 1.20, "stock": 800, "cat": "Transistors"},
            {"sku": "IC-001", "name": "NE555 Precision Timer IC", "price": 0.45, "stock": 1200, "cat": "ICs"},
            {"sku": "IC-002", "name": "ATmega328P Microcontroller", "price": 4.50, "stock": 300, "cat": "ICs"},
            {"sku": "SEN-001", "name": "DHT11 Humidity & Temp Sensor", "price": 2.50, "stock": 600, "cat": "Sensors"},
            {"sku": "SEN-002", "name": "HC-SR04 Ultrasonic Sensor", "price": 3.75, "stock": 450, "cat": "Sensors"},
            {"sku": "CON-001", "name": "USB Micro-B Port Breakout", "price": 0.95, "stock": 1000, "cat": "Connectors"}
        ]

        for p in products_data:
            existing_p = db.query(Product).filter(Product.sku == p["sku"]).first()
            if not existing_p:
                new_product = Product(
                    sku=p["sku"],
                    name=p["name"],
                    description=f"Standard {p['name']}",
                    price=p["price"],
                    stock_quantity=p["stock"],
                    category_id=category_map[p["cat"]]
                )
                db.add(new_product)
        
        db.commit()
        print("Database successfully seeded with categories and electronic components!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
