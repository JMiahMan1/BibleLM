# app/dependencies.py

from typing import Annotated
from fastapi import Depends, Request # Import Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import get_db and AsyncSessionLocal from database.py
from .database import get_db, AsyncSessionLocal
from .config import AppConfig, settings
# Import RagHandler class
from .utils.rag_handler import RagHandler

import logging

logger = logging.getLogger(__name__)


# Dependency to get settings
def get_settings() -> AppConfig:
    """Provides application settings."""
    return settings

# Dependency to get DB session in routes
async def get_db_session() -> AsyncSession:
    """Provides an asynchronous database session."""
    logger.debug("Getting DB session...")
    async with AsyncSessionLocal() as session:
        yield session
    logger.debug("DB session closed.")

# Dependency function to initialize and return RagHandler
# Removed the -> RagHandler type hint here as a potential workaround for import issues
async def get_rag_handler_dependency(db: AsyncSession = Depends(get_db_session)):
    """Initializes and returns the RagHandler instance as a dependency."""
    logger.info("Inside get_rag_handler_dependency, initializing RagHandler...")
    try:
        rag_handler_instance = RagHandler()
        # Ensure ainit is awaited
        await rag_handler_instance.ainit() # Calls ainit
        logger.info("RagHandler initialized in get_rag_handler_dependency.")
        return rag_handler_instance
    except Exception as e:
        logger.error(f"RagHandler dependency initialization failed: {e}")
        # Depending on how critical RAG is, you might raise HTTPException here
        # to prevent routes depending on it from working if it fails.
        # For now, re-raising the original exception might provide more details
        # during startup debugging. If this is a runtime dependency,
        # an HTTPException might be more appropriate here.
        raise # Re-raise the original exception


# Define the dependency alias using Annotated
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentSettings = Annotated[AppConfig, Depends(get_settings)]

# Define the RagHandler dependency alias
# This defines the dependency using Depends on the async function
CurrentRagHandler = Annotated[RagHandler, Depends(get_rag_handler_dependency)]
