from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .config import AppConfig, settings

# Dependency to get settings
def get_settings() -> AppConfig:
    return settings

# Type hints for dependencies
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentSettings = Annotated[AppConfig, Depends(get_settings)]
