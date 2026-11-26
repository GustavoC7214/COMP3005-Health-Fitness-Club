"""Database schema initialization using SQLAlchemy ORM."""

from sqlalchemy import text

from app.database.base import Base
from app.database.connection import engine
from app.database.member_setup import install_member_view


def init_db() -> None:
    """Create registered ORM tables and install database views."""
    import app.models  # noqa: F401

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))

    Base.metadata.create_all(bind=engine)
    install_member_view(engine)

    print("Database tables initialized successfully.")


if __name__ == "__main__":
    init_db()
