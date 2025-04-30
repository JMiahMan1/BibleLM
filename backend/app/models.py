# app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# Import enums from constants.py
from .constants import DocumentStatus, DocumentType, ChatMessageRole

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    original_path = Column(String)  # Path in uploads/ or the source URL
    processed_text_path = Column(String, nullable=True)  # Path to extracted text file
    document_type = Column(Enum(DocumentType)) # Use the imported Enum
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING) # Use the imported Enum
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    error_message = Column(Text, nullable=True)

    # Relationship for many-to-many with ChatSession
    chat_sessions = relationship("ChatSession", secondary="chat_session_documents", back_populates="documents")


class ChatSession(Base):
    __tablename__ = "chat_sessions" # Renamed from 'chats'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")
    # Relationship for many-to-many with Document
    documents = relationship("Document", secondary="chat_session_documents", back_populates="chat_sessions")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(Enum(ChatMessageRole)) # Use the imported Enum
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")

    # Optional: Store source document IDs used for this message (RAG)
    # source_document_ids = Column(Text, nullable=True) # Store as comma-separated string or JSON


# Association table for many-to-many relationship between ChatSession and Document
class ChatSessionDocument(Base):
    __tablename__ = "chat_session_documents"
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), primary_key=True)


# The original SourceTable, AudioNoteTable, AudioFileTable models are kept.
class Source(Base): # This seems redundant with Document, investigate usage
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Removed 'chats' relationship as chat logic is moving to ChatSession
    # chats = relationship("Chat", back_populates="source")


class Audio(Base): # Renamed from AudioNoteTable to avoid clash with database.py
    __tablename__ = "audio_notes"
    id = Column(Integer, primary_key=True, index=True)
    generated_note = Column(Text, index=True)
    tool_used = Column(String)

class AudioFile(Base): # Renamed from AudioFileTable to avoid clash with database.py
    __tablename__ = "audio_files"
    id = Column(Integer, primary_key=True, index=True)
    audio_title = Column(String)
    file_path = Column(String)
    duration = Column(Integer) # Duration in seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
