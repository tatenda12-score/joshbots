from app.database import SessionLocal, init_db
from app.product_service import ProductService

def seed_data():
    init_db()
    db = SessionLocal()
    
    # Sample products
    products = [
        {"name": "Wireless Headphones", "description": "High-quality noise-cancelling headphones", "price": 199.99, "stock": 50},
        {"name": "Smart Watch", "description": "Track your fitness and notifications", "price": 299.99, "stock": 30},
        {"name": "Bluetooth Speaker", "description": "Portable speaker with deep bass", "price": 89.99, "stock": 100},
        {"name": "USB-C Hub", "description": "7-in-1 adapter for your laptop", "price": 49.99, "stock": 200},
    ]

    print("Seeding products...")
    for p_data in products:
        ProductService.create_product(
            db, 
            name=p_data["name"], 
            description=p_data["description"], 
            price=p_data["price"], 
            stock=p_data["stock"]
        )
    
    db.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed_data()
