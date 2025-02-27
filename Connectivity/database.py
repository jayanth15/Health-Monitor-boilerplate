import os
from dotenv import load_dotenv
from sqlmodel import create_engine, SQLModel, Session
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Database connection parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "magejay15")

# PostgreSQL connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)

def get_session():
    """Return a new database session"""
    with Session(engine) as session:
        yield session

def init_db():
    """Initialize database by creating all tables"""
    SQLModel.metadata.create_all(engine)

def close_db():
    """Close database connections"""
    # Clean up connections when needed
    pass