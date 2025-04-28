from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Enum, DateTime, Text
import enum
from datetime import datetime
import asyncio

from .config import settings

# Use async engine for FastAPI
engine = create_async_engine(settings.database_url, echo=True) # echo=True for debugging SQL
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

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
    original_path = Column(String) # Path in uploads/ or the source URL
    processed_text_path = Column(String, nullable=True) # Path to extracted text file
    document_type = Column(Enum(DocumentType))
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Use cautiously for development
        await conn.run_sync(Base.metadata.create_all)

# Dependency to get DB session in routes
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Initialize DB on startup (can be done in main.py)
# asyncio.run(init_db()) # Run only once, perhaps via a startup script or manually
