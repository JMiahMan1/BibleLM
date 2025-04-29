# app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    chats = relationship("Chat", back_populates="source")

class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    title = Column(String)
    messages = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    source = relationship("Source", back_populates="chats")

class Audio(Base):
    __tablename__ = "audio_notes"
    id = Column(Integer, primary_key=True, index=True)
    generated_note = Column(Text, index=True)
    tool_used = Column(String)

class AudioFiles(Base):
    __tablename__ = "audio_files"
    id = Column(Integer, primary_key=True, index=True)
    audio_title = Column(String)
    file_path = Column(String)
    duration = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    id = Column(Integer, primary_key=True, index=True)
    generated_note = Column(Text, index=True)
    tool_used = Column(String)

