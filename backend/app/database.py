import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

# Import Base from models.py
from .models import Base
# Import enums from constants.py if needed for database logic (not strictly necessary for table creation)
# from .constants import DocumentStatus, DocumentType, ChatMessageRole

from .config import settings

DATABASE_PATH = settings.full_data_dir / "db" / "app.db"
# Ensure parent directory exists before creating the database file
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Enums are now in constants.py ---


# Use async engine for FastAPI
try:
    logger.info(f"Connecting to database with URL: {DATABASE_URL}")
    # Removed echo=True unless needed for debugging, can be noisy
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
except Exception as e:
    logger.error(f"Error creating database engine: {e}")
    # It's crucial to handle this error, as the app cannot function without a DB connection.
    # Raise the exception here to prevent the app from starting if the database fails.
    raise

# Dependency to get DB session in routes
async def get_db():
    """Provides an asynchronous database session."""
    logger.debug("Getting DB session...")
    async with AsyncSessionLocal() as session:
        yield session
    logger.debug("DB session closed.")


async def init_db():
    """
    Initialize the database: create tables if they don't exist.
    """
    logger.info("Attempting to initialize database tables...")
    try:
        async with engine.begin() as conn:
            logger.info("Running Base.metadata.create_all...")
            # This will create all tables defined in models.py that inherit from Base
            # only if they do not already exist in the database.
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Base.metadata.create_all finished.")
        logger.info("Database tables created or already exist.")
    except OperationalError as e:
        logger.error(f"OperationalError during database initialization: {e}")
        # Re-raise to stop startup if migration/creation fails
        raise
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
