"""Database schema initialization using SQLAlchemy ORM."""

from sqlalchemy import text

from app.database.base import Base
from app.database.connection import engine


def init_db() -> None:
    """Create PostgreSQL extensions and registered ORM tables."""
    import app.models  # noqa: F401

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))

    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")


if __name__ == "__main__":
    init_db()
