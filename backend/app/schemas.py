from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
# Import enums from constants.py
from .constants import DocumentStatus, DocumentType # Import from constants

# --- API Request Models ---

class IngestURLRequest(BaseModel):
    url: str

# Removed ChatMessageCreate schema here as messages are created via the /query endpoint
# If you need a separate endpoint just to add arbitrary messages, you could reinstate this.

class ChatSessionCreate(BaseModel):
    title: str
    # Optional: Link initial documents to the session upon creation
    document_ids: List[int] = []

class SummaryRequest(BaseModel):
    document_ids: List[int]
    format: str = Field(default="txt", pattern="^(txt|docx|script|audio)$") # Allowed formats

class ChatQueryRequest(BaseModel):
    session_id: int # Associate question with a specific session
    question: str
    document_ids: List[int] = [] # Relevant document IDs for grounding the query

# Optional: Schema for updating documents linked to a session
# class UpdateSessionDocumentsRequest(BaseModel):
#     document_ids: List[int]
#     link: bool # True to link, False to unlink


# --- API Response Models ---

class DocumentResponse(BaseModel):
    id: int
    filename: str
    document_type: DocumentType # Use the imported Enum
    status: DocumentStatus # Use the imported Enum
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True # Compatibility with SQLAlchemy models

class TaskStatusResponse(BaseModel):
    task_id: int # Corresponds to document ID
    status: DocumentStatus # Use the imported Enum
    filename: str
    error_message: Optional[str] = None

class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    content: str
    role: str # Use str for schema, validation handled on creation/storage
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    # Make updated_at optional as it might be None on creation
    updated_at: Optional[datetime] = None

    # Exclude messages in the session list, fetch separately
    # messages: List[ChatMessageResponse] = []
    documents: List[DocumentResponse] = [] # Include associated documents in session details

    class Config:
        from_attributes = True # Compatibility with SQLAlchemy models

class SummaryResponse(BaseModel):
    message: str
    download_url: Optional[str] = None # URL to download the generated file (if applicable)
    task_id: Optional[str] = None # If audio generation is backgrounded, use a task ID string

class UploadResponse(BaseModel):
    message: str
    document: DocumentResponse

class ChatQueryResponse(BaseModel):
     answer: str
     # Optional: Include source documents used for the answer
     source_documents: List[DocumentResponse] = []
