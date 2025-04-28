from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from . import database, schemas
from .database import Document, DocumentStatus, DocumentType
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

async def create_document(db: AsyncSession, filename: str, original_path: str, doc_type: DocumentType) -> Document:
    db_doc = Document(
        filename=filename,
        original_path=original_path,
        document_type=doc_type,
        status=DocumentStatus.PENDING
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
        doc.status = status
        doc.error_message = error_message
        if status == DocumentStatus.COMPLETED:
             doc.error_message = None # Clear error on success
        await db.commit()
        await db.refresh(doc)
        logger.info(f"Updated document {doc_id} status to {status}")
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
            Document.status == DocumentStatus.COMPLETED,
            Document.processed_text_path != None # Ensure text exists
        )
    )
    return result.scalars().all()
