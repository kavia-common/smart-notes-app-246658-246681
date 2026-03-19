"""
Database setup for PostgreSQL using SQLAlchemy.

This module exposes a dependency (`get_db`) that provides a per-request Session,
and an initialization function that creates tables when the app starts.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.core.config import get_settings

# Create engine once per process.
_settings = get_settings()

# SQLAlchemy accepts "postgresql://..." with psycopg2 installed.
engine = create_engine(
    _settings.postgres_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


# PUBLIC_INTERFACE
@contextmanager
def db_session() -> Iterator[Session]:
    """Yield a SQLAlchemy Session and ensure it is closed.

    Yields:
        Session: SQLAlchemy ORM session.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# PUBLIC_INTERFACE
def init_db() -> None:
    """Initialize database tables.

    This uses SQLAlchemy metadata `create_all` which is appropriate for this template project.
    In production, a migration tool (Alembic) is recommended.
    """
    from src.api.models import Base  # imported here to avoid circular imports

    Base.metadata.create_all(bind=engine)
