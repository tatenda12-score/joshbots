from .database import SessionLocal
from .models import Product, Category
from sqlalchemy.orm import Session
from sqlalchemy import or_

async def get_categories() -> str:
    """Queries all categories and returns a formatted string list with numbering."""
    db = SessionLocal()
    try:
        categories = db.query(Category).all()
        if not categories:
            return "No categories available."
        
        response = "*Available Categories:*\n\n"
        for i, cat in enumerate(categories, 1):
            response += f"{i}. {cat.name}\n"
        return response
    finally:
        db.close()

async def get_products(category_name: str = None) -> str:
    """
    Queries products filtered by category (optional), limited to 20.
    Returns a compact price list: name, price, stock status.
    """
    db = SessionLocal()
    try:
        query = db.query(Product)
        
        if category_name:
            query = query.join(Category).filter(Category.name.ilike(f"%{category_name}%"))
            
        products = query.limit(20).all()
        
        if not products:
            return f"No products found{' in ' + category_name if category_name else ''}."
        
        response = f"*{category_name if category_name else 'Products'}:*\n"
        for p in products:
            if p.stock_quantity > 0:
                response += f"*{p.name}* — ${p.price:,.2f} ✅\n"
            else:
                response += f"*{p.name}* — ❌ Out of Stock\n"
        response += "\nNeed a quote? Send quantities."
        return response
    finally:
        db.close()

async def get_price(query_text: str) -> str:
    """
    Searches products by name or SKU and returns a single-line price.
    """
    db = SessionLocal()
    try:
        # Search by name or SKU using ilike
        product = db.query(Product).filter(
            or_(
                Product.name.ilike(f"%{query_text}%"),
                Product.sku.ilike(f"%{query_text}%")
            )
        ).first()
        
        if not product:
            return f"Sorry, *{query_text}* is not available."
        
        if product.stock_quantity > 0:
            return f"*{product.name}* — ${product.price:,.2f} ✅\n\nNeed a quote? Send the quantity."
        else:
            return f"*{product.name}* — ❌ Out of Stock"
    finally:
        db.close()
