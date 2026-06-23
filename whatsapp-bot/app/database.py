import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# Fetch the database URL from environment variable, defaulting to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./blitztech.db")

# Critical Render Fix: SQLAlchemy 1.4+ requires postgresql:// instead of postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Initialize engine dynamically based on the database type
if DATABASE_URL.startswith("sqlite"):
    # connect_args={"check_same_thread": False} is required for SQLite in multi-threaded environments like FastAPI
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    # Initialize normally for PostgreSQL
    engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize the database by creating all tables defined in models.py."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for getting a database session for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
