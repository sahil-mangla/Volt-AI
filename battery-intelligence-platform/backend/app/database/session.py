import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./battery_data.db")

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

# Initialize engine and SessionLocal at module level for background thread reliability
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    # Model tables are created via Base.metadata.create_all(bind=engine) in main.py
    logger.info("Database engine and SessionLocal initialized at module level.")

Base = declarative_base()

def get_db():
    # SessionLocal is now guaranteed to be a callable sessionmaker
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()