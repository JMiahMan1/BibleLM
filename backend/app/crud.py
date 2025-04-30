from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload # Import joinedload for relationships
# Import enums from constants.py
from .constants import DocumentStatus, DocumentType, ChatMessageRole
# Import models from models.py
from .models import Document, ChatSession, ChatMessage, ChatSessionDocument
from pathlib import Path
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# --- Document CRUD ---

async def create_document(db: AsyncSession, filename: str, original_path: str, doc_type: DocumentType) -> Document:
    db_doc = Document(
        filename=filename,
        original_path=original_path,
        document_type=doc_type, # Use the Enum directly
        status=DocumentStatus.PENDING # Use the Enum directly
    )
    db.add(db_doc)
    await db.commit()
    await db.refresh(db_doc)
    logger.info(f"Created document record for {filename} (ID: {db_doc.id})")
    return db_doc

async def get_document(db: AsyncSession, doc_id: int) -> Document | None:
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    return result.scalar_one_or_none()

async def get_documents(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Document]:
    result = await db.execute(select(Document).offset(skip).limit(limit))
    return result.scalars().all()

async def update_document_status(db: AsyncSession, doc_id: int, status: DocumentStatus, error_message: str | None = None) -> Document | None:
    doc = await get_document(db, doc_id)
    if doc:
        doc.status = status # Use the Enum directly
        doc.error_message = error_message
        if status == DocumentStatus.COMPLETED:
             doc.error_message = None # Clear error on success
        await db.commit()
        await db.refresh(doc)
        logger.info(f"Updated document {doc_id} status to {status.name}")
    return doc

async def update_document_processed_path(db: AsyncSession, doc_id: int, processed_path: str) -> Document | None:
    doc = await get_document(db, doc_id)
    if doc:
        doc.processed_text_path = processed_path
        await db.commit()
        await db.refresh(doc)
        logger.info(f"Set processed path for document {doc_id} to {processed_path}")
    return doc

async def get_documents_by_ids(db: AsyncSession, doc_ids: list[int]) -> list[Document]:
    if not doc_ids:
        return []
    result = await db.execute(select(Document).filter(Document.id.in_(doc_ids)))
    return result.scalars().all()

async def get_completed_documents_by_ids(db: AsyncSession, doc_ids: list[int]) -> list[Document]:
    if not doc_ids:
        return []
    result = await db.execute(
        select(Document).filter(
            Document.id.in_(doc_ids),
            Document.status == DocumentStatus.COMPLETED, # Compare with Enum member
            Document.processed_text_path != None # Ensure text exists
        )
    )
    return result.scalars().all()

# --- Chat Session CRUD ---

async def create_chat_session(db: AsyncSession, title: str, document_ids: List[int] = []) -> ChatSession:
    db_session = ChatSession(title=title)
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)

    # Link documents if provided
    if document_ids:
        documents = await get_documents_by_ids(db, document_ids)
        for doc in documents:
            # Create association object
            session_document = ChatSessionDocument(chat_session_id=db_session.id, document_id=doc.id)
            db.add(session_document)
        await db.commit()
        await db.refresh(db_session) # Refresh again to load the documents relationship

    logger.info(f"Created chat session: {title} (ID: {db_session.id})")
    return db_session

async def get_chat_session(db: AsyncSession, session_id: int) -> ChatSession | None:
    """Gets details for a specific chat session."""
    # Use joinedload to fetch documents along with the session
    result = await db.execute(
        select(ChatSession)
        .filter(ChatSession.id == session_id)
        .options(joinedload(ChatSession.documents)) # Eager load documents
    )
    # Try using .first() instead of .scalar_one_or_none()
    return result.scalars().first() # Replaced scalar_one_or_none() with first()

async def get_chat_sessions(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[ChatSession]:
    """Gets a list of all chat sessions."""
    # Use joinedload to fetch documents along with the sessions in the list
    result = await db.execute(
        select(ChatSession)
        .offset(skip)
        .limit(limit)
        .options(joinedload(ChatSession.documents)) # Eager load documents
        .order_by(ChatSession.created_at.desc()) # Order by creation date, newest first
    )
    # Keep unique() here as it's needed when fetching multiple items with joinedload
    return result.unique().scalars().all() # This line should remain unchanged from the previous fix

# --- Chat Message CRUD ---

async def create_chat_message(db: AsyncSession, session_id: int, role: str, content: str) -> ChatMessage:
    # Validate role using the Enum (redundant if Pydantic schema is used, but defensive)
    if role not in [e.value for e in ChatMessageRole]:
        logger.warning(f"Attempted to create message with invalid role: {role}")
        # Optionally raise an error or default
        role = ChatMessageRole.SYSTEM.value # Default to system for invalid roles

    db_message = ChatMessage(
        session_id=session_id,
        role=ChatMessageRole(role), # Convert string role to Enum member
        content=content
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    logger.debug(f"Added message to session {session_id} (Role: {role})")
    return db_message

async def get_chat_messages(db: AsyncSession, session_id: int, skip: int = 0, limit: int = 100) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at) # Order by creation date
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
