"""Member 1 fixtures use a fresh PostgreSQL schema, never shared application tables."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database.member_setup import install_member_view
from app.models.member import FitnessGoal, HealthMetric, Member
from app.models.member_attendance import ClassAttendance, GroupClass


@pytest.fixture
def m1_engine():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set TEST_DATABASE_URL=postgresql+psycopg://... to run PostgreSQL tests."
        )
    admin = create_engine(url)
    if admin.dialect.name != "postgresql" or admin.dialect.driver != "psycopg":
        admin.dispose()
        pytest.fail(
            "Member 1 persistence tests require PostgreSQL with the psycopg driver."
        )
    schema = "test_member1_" + uuid4().hex
    engine = None
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={schema},public -ctimezone=UTC"},
        )
        tables = [
            Member.__table__,
            FitnessGoal.__table__,
            HealthMetric.__table__,
            GroupClass.__table__,
            ClassAttendance.__table__,
        ]
        Member.metadata.create_all(engine, tables=tables)
        install_member_view(engine)
        yield engine
    finally:
        if engine:
            engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def m1_session(m1_engine):
    with Session(m1_engine, expire_on_commit=False) as session:
        yield session
        session.rollback()
