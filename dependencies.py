"""
Dependency injection para FastAPI
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from config import get_settings
from core.logging import logger


settings = get_settings()

# Crear engine de SQLAlchemy
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.debug
)

# SessionLocal para crear sesiones de BD
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency para obtener sesión de base de datos
    Se cierra automáticamente al finalizar la petición
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Error en sesión de BD: {e}")
        db.rollback()
        raise
    finally:
        db.close()
