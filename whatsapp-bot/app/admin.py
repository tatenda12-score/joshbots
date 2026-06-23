import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from .database import SessionLocal
from .models import Product, Category, Quotation, UserSession
from .config import config

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBasic()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, config.ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, config.ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Pydantic Models
class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ProductCreate(BaseModel):
    sku: str
    name: str
    price: float
    category_id: int
    stock_quantity: int = 0
    description: Optional[str] = None

class ProductUpdate(BaseModel):
    price: Optional[float] = None
    stock_quantity: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    category_id: Optional[int] = None

# Routes
@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    total_products = db.query(Product).count()
    total_categories = db.query(Category).count()
    total_quotations = db.query(Quotation).count()
    total_conversations = db.query(UserSession).count()
    
    return {
        "products": total_products,
        "categories": total_categories,
        "quotations": total_quotations,
        "user_sessions": total_conversations
    }

@router.get("/products")
def list_products(db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    return db.query(Product).all()

@router.post("/products", status_code=status.HTTP_201_CREATED)
def add_product(prod: ProductCreate, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    db_prod = Product(**prod.model_dump() if hasattr(prod, 'model_dump') else prod.dict())
    db.add(db_prod)
    db.commit()
    db.refresh(db_prod)
    return db_prod

@router.put("/products/{id}")
def update_product(id: int, update_data: ProductUpdate, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    db_prod = db.query(Product).filter(Product.id == id).first()
    if not db_prod:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_dict = update_data.model_dump(exclude_unset=True) if hasattr(update_data, 'model_dump') else update_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(db_prod, key, value)
        
    db.commit()
    db.refresh(db_prod)
    return db_prod

@router.delete("/products/{id}")
def delete_product(id: int, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    db_prod = db.query(Product).filter(Product.id == id).first()
    if not db_prod:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(db_prod)
    db.commit()
    return {"message": "Product deleted successfully"}

@router.get("/categories")
def list_categories(db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    return db.query(Category).all()

@router.post("/categories", status_code=status.HTTP_201_CREATED)
def add_category(cat: CategoryCreate, db: Session = Depends(get_db), admin: str = Depends(get_current_admin)):
    db_cat = Category(name=cat.name, description=cat.description)
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    return db_cat
