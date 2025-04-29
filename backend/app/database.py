import enum
import logging
from datetime import datetime
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text
from sqlalchemy.exc import OperationalError

from .config import settings

DATABASE_PATH = settings.full_data_dir / "db" / "app.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# --- Logging Setup ---
logger = logging.getLogger(__name__)  # Get the logger for this module

# Use async engine for FastAPI
try:
    logger.info(f"Connecting to database with URL: {DATABASE_URL}")  # Log the URL
    engine = create_async_engine(DATABASE_URL, echo=True)  # echo=True for debugging SQL
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
except Exception as e:
    logger.error(f"Error creating database engine: {e}")
    # It's crucial to handle this error, as the app cannot function without a DB connection.
    # You might want to raise an exception here to prevent the app from starting.
    raise  # Re-raise the exception to stop the application startup

Base = declarative_base()


class DocumentStatus(enum.Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocumentType(enum.Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    EPUB = "EPUB"
    TXT = "TXT"
    MP3 = "MP3"
    WAV = "WAV"
    MP4 = "MP4"
    MOV = "MOV"
    PNG = "PNG"
    JPG = "JPG"
    URL = "URL"
    UNKNOWN = "UNKNOWN"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    original_path = Column(String)  # Path in uploads/ or the source URL
    processed_text_path = Column(String, nullable=True)  # Path to extracted text file
    document_type = Column(Enum(DocumentType))
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)


async def init_db():
    try:
        async with engine.begin() as conn:
            # await conn.run_sync(Base.metadata.drop_all)  # Use cautiously for development
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully.")
    except OperationalError as e:
        logger.error(f"OperationalError during database initialization: {e}")
        raise  # Re-raise to stop startup
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise  # Re-raise to stop startup


# Dependency to get DB session in routes
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
