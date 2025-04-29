from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from .database import DocumentStatus, DocumentType

# --- API Request Models ---

class IngestURLRequest(BaseModel):
    url: str

class ChatRequest(BaseModel):
    message: str
    document_ids: List[int] = [] # Which documents to ground the chat on
    session_id: Optional[str] = None # For future session memory

class SummaryRequest(BaseModel):
    document_ids: List[int]
    format: str = Field(default="txt", pattern="^(txt|docx|script|audio)$") # Allowed formats

# --- API Response Models ---

class DocumentResponse(BaseModel):
    id: int
    filename: str
    document_type: DocumentType
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True # Compatibility with SQLAlchemy models

class TaskStatusResponse(BaseModel):
    task_id: int # Corresponds to document ID
    status: DocumentStatus
    filename: str
    error_message: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[DocumentResponse] = [] # Documents used in RAG

class SummaryResponse(BaseModel):
    message: str
    download_url: Optional[str] = None # URL to download the generated file (if applicable)
    task_id: Optional[int] = None # If audio generation is backgrounded

class UploadResponse(BaseModel):
    message: str
    document: DocumentResponse
