from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from db import SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
