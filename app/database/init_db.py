"""Database schema initialization using SQLAlchemy ORM."""

from app.database.base import Base
from app.database.connection import engine


def init_db() -> None:
    """Create tables for all registered SQLAlchemy models."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    from app.database.member_setup import install_member_view

    install_member_view(engine)
    print("Database tables initialized successfully.")


if __name__ == "__main__":
    init_db()
