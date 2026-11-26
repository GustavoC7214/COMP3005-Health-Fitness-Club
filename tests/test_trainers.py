"""Tests for Trainer ORM model definitions."""

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, Index, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.member import FitnessGoal, HealthMetric, Member
from app.models.trainer import PTSession, Trainer, TrainerAvailability
from app.trainers.trainer_service import (
    add_trainer_availability,
    book_pt_session,
    cancel_pt_session,
    get_trainer_assigned_members,
    get_trainer_availability,
    get_trainer_schedule,
    reschedule_pt_session,
)


def test_trainer_tables_registered():
    """All trainer-related tables should be registered."""
    assert Trainer.__tablename__ in Base.metadata.tables
    assert TrainerAvailability.__tablename__ in Base.metadata.tables
    assert PTSession.__tablename__ in Base.metadata.tables


def test_trainer_primary_key():
    """Trainer should use trainer_id as its primary key."""
    primary_keys = {column.name for column in Trainer.__table__.primary_key}

    assert primary_keys == {"trainer_id"}


def test_availability_foreign_key():
    """Availability must reference the trainer table."""
    foreign_keys = {
        str(foreign_key.target_fullname)
        for foreign_key in TrainerAvailability.__table__.foreign_keys
    }

    assert "trainers.trainer_id" in foreign_keys


def test_pt_session_foreign_keys():
    """PT sessions must reference trainers and members."""
    foreign_keys = {
        str(foreign_key.target_fullname)
        for foreign_key in PTSession.__table__.foreign_keys
    }

    assert foreign_keys == {
        "trainers.trainer_id",
        "members.member_id",
    }


def test_availability_time_constraint():
    """Availability must have a valid time-range constraint."""
    constraints = {
        constraint.name
        for constraint in TrainerAvailability.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_trainer_availability_valid_time" in constraints


def test_pt_session_constraints():
    """PT sessions must validate time ranges and status."""
    constraints = {
        constraint.name
        for constraint in PTSession.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_pt_session_valid_time" in constraints
    assert "ck_pt_session_status" in constraints


def test_trainer_availability_index():
    """Trainer availability should have a scheduling index."""
    indexes = {
        index.name
        for index in TrainerAvailability.__table__.indexes
        if isinstance(index, Index)
    }

    assert "ix_trainer_availability_trainer_start" in indexes


def test_pt_session_indexes():
    """PT sessions should support trainer and member lookups."""
    indexes = {
        index.name for index in PTSession.__table__.indexes if isinstance(index, Index)
    }

    assert "ix_pt_sessions_trainer_start" in indexes
    assert "ix_pt_sessions_member_start" in indexes


@pytest.fixture
def trainer(db_session):
    """Create a trainer for scheduling tests."""
    trainer = Trainer(
        first_name="Alex",
        last_name="Morgan",
        email="alex.morgan@example.com",
        specialization="Strength Training",
    )
    db_session.add(trainer)
    db_session.flush()
    return trainer


def test_add_trainer_availability(db_session, trainer):
    """A trainer should be able to register availability."""
    start = datetime(2026, 11, 12, 9, 0)
    end = datetime(2026, 11, 12, 11, 0)

    slot = add_trainer_availability(db_session, trainer.trainer_id, start, end)

    assert slot.availability_id is not None
    assert slot.trainer_id == trainer.trainer_id
    assert slot.start_time == start
    assert slot.end_time == end


def test_reject_overlapping_availability(db_session, trainer):
    """A trainer cannot register overlapping availability."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 12, 9, 0),
        datetime(2026, 11, 12, 11, 0),
    )

    with pytest.raises(ValueError, match="overlaps"):
        add_trainer_availability(
            db_session,
            trainer.trainer_id,
            datetime(2026, 11, 12, 10, 0),
            datetime(2026, 11, 12, 12, 0),
        )


def test_allow_adjacent_availability(db_session, trainer):
    """Adjacent availability intervals should be permitted."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 12, 9, 0),
        datetime(2026, 11, 12, 10, 0),
    )

    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 12, 10, 0),
        datetime(2026, 11, 12, 11, 0),
    )

    slots = get_trainer_availability(db_session, trainer.trainer_id)

    assert len(slots) == 2


def test_reject_invalid_availability_time(db_session, trainer):
    """End time must be later than start time."""
    with pytest.raises(ValueError, match="End time"):
        add_trainer_availability(
            db_session,
            trainer.trainer_id,
            datetime(2026, 11, 12, 11, 0),
            datetime(2026, 11, 12, 9, 0),
        )


def test_reject_nonexistent_trainer(db_session):
    """Availability cannot be added for a nonexistent trainer."""
    with pytest.raises(ValueError, match="does not exist"):
        add_trainer_availability(
            db_session,
            999999,
            datetime(2026, 11, 12, 9, 0),
            datetime(2026, 11, 12, 10, 0),
        )


def test_get_trainer_availability_ordered(db_session, trainer):
    """Availability should be returned in chronological order."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 13, 13, 0),
        datetime(2026, 11, 13, 15, 0),
    )

    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 13, 9, 0),
        datetime(2026, 11, 13, 11, 0),
    )

    slots = get_trainer_availability(db_session, trainer.trainer_id)

    assert len(slots) == 2
    assert slots[0].start_time < slots[1].start_time


@pytest.fixture
def db_session():
    """Provide an isolated PostgreSQL schema for each trainer test."""
    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL tests.")

    admin_engine = create_engine(database_url)

    if (
        admin_engine.dialect.name != "postgresql"
        or admin_engine.dialect.driver != "psycopg"
    ):
        admin_engine.dispose()
        pytest.fail("Trainer tests require PostgreSQL with psycopg.")

    schema = "test_trainer_" + uuid4().hex
    engine = None

    try:
        with admin_engine.begin() as connection:
            connection.execute(
                text("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public")
            )
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        engine = create_engine(
            database_url,
            connect_args={"options": f"-csearch_path={schema},public -ctimezone=UTC"},
        )

        Base.metadata.create_all(
            bind=engine,
            tables=[
                Member.__table__,
                FitnessGoal.__table__,
                HealthMetric.__table__,
                Trainer.__table__,
                TrainerAvailability.__table__,
                PTSession.__table__,
            ],
            checkfirst=False,
        )

        with Session(engine, expire_on_commit=False) as session:
            try:
                yield session
            finally:
                session.rollback()

    finally:
        if engine is not None:
            engine.dispose()

        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

        admin_engine.dispose()


@pytest.fixture
def member(db_session):
    """Create a real member for personal training tests."""
    member = Member(
        first_name="Jamie",
        last_name="Taylor",
        email="jamie.taylor@example.com",
        date_of_birth=date(2000, 1, 1),
    )

    db_session.add(member)
    db_session.flush()

    return member.member_id


def test_book_pt_session(db_session, trainer, member):
    """A member can book a PT session during trainer availability."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 14, 9),
        datetime(2026, 11, 14, 12),
    )

    booking = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 14, 10),
        datetime(2026, 11, 14, 11),
    )

    assert booking.session_id is not None
    assert booking.status == "scheduled"
    assert booking.member_id == member


def test_reject_booking_outside_availability(db_session, trainer, member):
    """Bookings must fall within a trainer's availability."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 14, 9),
        datetime(2026, 11, 14, 12),
    )

    with pytest.raises(ValueError, match="not available"):
        book_pt_session(
            db_session,
            member,
            trainer.trainer_id,
            datetime(2026, 11, 14, 12),
            datetime(2026, 11, 14, 13),
        )


def test_reject_overlapping_trainer_booking(db_session, trainer, member):
    """A trainer cannot have overlapping scheduled PT sessions."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 14, 9),
        datetime(2026, 11, 14, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 14, 9),
        datetime(2026, 11, 14, 10),
    )

    with pytest.raises(ValueError, match="trainer already"):
        book_pt_session(
            db_session,
            member,
            trainer.trainer_id,
            datetime(2026, 11, 14, 9, 30),
            datetime(2026, 11, 14, 10, 30),
        )


def test_reject_nonexistent_member_booking(db_session, trainer):
    """A booking must reference an existing member."""
    with pytest.raises(ValueError, match="Member .* does not exist"):
        book_pt_session(
            db_session,
            999999,
            trainer.trainer_id,
            datetime(2026, 11, 14, 9),
            datetime(2026, 11, 14, 10),
        )


def test_allow_adjacent_pt_bookings(db_session, trainer, member):
    """A trainer may accept back-to-back PT sessions."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 14, 9),
        datetime(2026, 11, 14, 12),
    )

    first = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 14, 9),
        datetime(2026, 11, 14, 10),
    )

    second = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 14, 10),
        datetime(2026, 11, 14, 11),
    )

    assert first.session_id != second.session_id


def test_reschedule_pt_session(db_session, trainer, member):
    """A scheduled session can be moved to another available time."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 13),
    )

    booking = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 10),
    )

    updated = reschedule_pt_session(
        db_session,
        booking.session_id,
        datetime(2026, 11, 15, 11),
        datetime(2026, 11, 15, 12),
    )

    assert updated.start_time == datetime(2026, 11, 15, 11)
    assert updated.end_time == datetime(2026, 11, 15, 12)


def test_cancel_pt_session(db_session, trainer, member):
    """Cancellation preserves the booking record."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 12),
    )

    booking = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 10),
    )

    cancelled = cancel_pt_session(db_session, booking.session_id)

    assert cancelled.status == "cancelled"
    assert db_session.get(PTSession, booking.session_id) is not None


def test_cancelled_booking_frees_time(db_session, trainer, member):
    """A cancelled session no longer blocks its time interval."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 12),
    )

    first = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 10),
    )

    cancel_pt_session(db_session, first.session_id)

    second = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 10),
    )

    assert second.session_id != first.session_id
    assert second.status == "scheduled"


def test_get_trainer_schedule(db_session, trainer, member):
    """A trainer's schedule should contain only active sessions."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 14),
    )

    first = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 10),
    )

    second = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 15, 12),
        datetime(2026, 11, 15, 13),
    )

    cancel_pt_session(db_session, first.session_id)

    schedule = get_trainer_schedule(db_session, trainer.trainer_id)

    assert len(schedule) == 1
    assert schedule[0].session_id == second.session_id


def test_reject_reschedule_outside_availability(db_session, trainer, member):
    """Rescheduling must respect the trainer's available hours."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 12),
    )

    booking = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 10),
    )

    with pytest.raises(ValueError, match="not available"):
        reschedule_pt_session(
            db_session,
            booking.session_id,
            datetime(2026, 11, 15, 13),
            datetime(2026, 11, 15, 14),
        )


def test_reject_rescheduling_cancelled_session(db_session, trainer, member):
    """Cancelled sessions cannot be rescheduled."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 12),
    )

    booking = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 15, 9),
        datetime(2026, 11, 15, 10),
    )

    cancel_pt_session(db_session, booking.session_id)

    with pytest.raises(ValueError, match="Only scheduled"):
        reschedule_pt_session(
            db_session,
            booking.session_id,
            datetime(2026, 11, 15, 10),
            datetime(2026, 11, 15, 11),
        )


def test_get_trainer_assigned_members(db_session, trainer, member):
    """A trainer can view members assigned to scheduled sessions."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 16, 9),
        datetime(2026, 11, 16, 12),
    )

    booking = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 16, 10),
        datetime(2026, 11, 16, 11),
    )

    assigned = get_trainer_assigned_members(db_session, trainer.trainer_id)

    assert len(assigned) == 1
    assert assigned[0]["member_id"] == member
    assert assigned[0]["first_name"] == "Jamie"
    assert assigned[0]["last_name"] == "Taylor"
    assert assigned[0]["session_id"] == booking.session_id


def test_cancelled_members_not_in_assignments(db_session, trainer, member):
    """Cancelled bookings do not appear in assigned members."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 16, 9),
        datetime(2026, 11, 16, 12),
    )

    booking = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 16, 10),
        datetime(2026, 11, 16, 11),
    )

    cancel_pt_session(db_session, booking.session_id)

    assigned = get_trainer_assigned_members(db_session, trainer.trainer_id)

    assert assigned == []


def test_reject_assigned_members_for_unknown_trainer(db_session):
    """An unknown trainer cannot retrieve assignments."""
    with pytest.raises(ValueError, match="does not exist"):
        get_trainer_assigned_members(db_session, 999999)


def test_database_rejects_overlapping_trainer_sessions(db_session, trainer, member):
    """PostgreSQL must prevent overlapping bookings for one trainer."""
    from sqlalchemy import text

    db_session.execute(
        text(
            """
            INSERT INTO pt_sessions
                (trainer_id, member_id, start_time, end_time, status)
            VALUES
                (:trainer_id, :member_id, :start_time, :end_time, 'scheduled')
            """
        ),
        {
            "trainer_id": trainer.trainer_id,
            "member_id": member,
            "start_time": datetime(2026, 11, 18, 9),
            "end_time": datetime(2026, 11, 18, 10),
        },
    )

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                """
                INSERT INTO pt_sessions
                    (trainer_id, member_id, start_time, end_time, status)
                VALUES
                    (:trainer_id, :member_id, :start_time, :end_time, 'scheduled')
                """
            ),
            {
                "trainer_id": trainer.trainer_id,
                "member_id": member,
                "start_time": datetime(2026, 11, 18, 9, 30),
                "end_time": datetime(2026, 11, 18, 10, 30),
            },
        )


def test_database_rejects_overlapping_member_sessions(db_session, member):
    """A member cannot have overlapping sessions with different trainers."""
    from sqlalchemy import text

    trainer_one = Trainer(
        first_name="Alex",
        last_name="Smith",
        email="alex@example.com",
        specialization="Strength",
    )
    trainer_two = Trainer(
        first_name="Morgan",
        last_name="Lee",
        email="morgan@example.com",
        specialization="Cardio",
    )

    db_session.add_all([trainer_one, trainer_two])
    db_session.flush()

    insert_sql = text(
        """
        INSERT INTO pt_sessions
            (trainer_id, member_id, start_time, end_time, status)
        VALUES
            (:trainer_id, :member_id, :start_time, :end_time, 'scheduled')
        """
    )

    db_session.execute(
        insert_sql,
        {
            "trainer_id": trainer_one.trainer_id,
            "member_id": member,
            "start_time": datetime(2026, 11, 18, 9),
            "end_time": datetime(2026, 11, 18, 10),
        },
    )

    with pytest.raises(IntegrityError):
        db_session.execute(
            insert_sql,
            {
                "trainer_id": trainer_two.trainer_id,
                "member_id": member,
                "start_time": datetime(2026, 11, 18, 9, 30),
                "end_time": datetime(2026, 11, 18, 10, 30),
            },
        )


def test_database_allows_adjacent_pt_sessions(db_session, trainer, member):
    """Back-to-back bookings must be allowed at the database level."""
    from sqlalchemy import text

    insert_sql = text(
        """
        INSERT INTO pt_sessions
            (trainer_id, member_id, start_time, end_time, status)
        VALUES
            (:trainer_id, :member_id, :start_time, :end_time, 'scheduled')
        """
    )

    db_session.execute(
        insert_sql,
        {
            "trainer_id": trainer.trainer_id,
            "member_id": member,
            "start_time": datetime(2026, 11, 18, 9),
            "end_time": datetime(2026, 11, 18, 10),
        },
    )

    db_session.execute(
        insert_sql,
        {
            "trainer_id": trainer.trainer_id,
            "member_id": member,
            "start_time": datetime(2026, 11, 18, 10),
            "end_time": datetime(2026, 11, 18, 11),
        },
    )

    count = db_session.scalar(
        text(
            """
            SELECT COUNT(*)
            FROM pt_sessions
            WHERE trainer_id = :trainer_id
              AND member_id = :member_id
            """
        ),
        {"trainer_id": trainer.trainer_id, "member_id": member},
    )

    assert count == 2


def test_search_assigned_members_case_insensitive(db_session, trainer, member):
    """Search should match assigned members regardless of case."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 20, 9),
        datetime(2026, 11, 20, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 20, 10),
        datetime(2026, 11, 20, 11),
    )

    results = get_trainer_assigned_members(db_session, trainer.trainer_id, "jAmIe")

    assert len(results) == 1
    assert results[0]["member_id"] == member


def test_search_assigned_members_full_name(db_session, trainer, member):
    """Search should support partial or full names."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 20, 9),
        datetime(2026, 11, 20, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 20, 10),
        datetime(2026, 11, 20, 11),
    )

    results = get_trainer_assigned_members(
        db_session, trainer.trainer_id, "JAMIE TAYLOR"
    )

    assert len(results) == 1
    assert results[0]["member_id"] == member


def test_search_assigned_members_no_match(db_session, trainer, member):
    """Search should return no results for an unmatched name."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 20, 9),
        datetime(2026, 11, 20, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 20, 10),
        datetime(2026, 11, 20, 11),
    )

    results = get_trainer_assigned_members(
        db_session, trainer.trainer_id, "Nonexistent"
    )

    assert results == []


def test_search_cannot_access_another_trainers_members(db_session, trainer, member):
    """A trainer must not see members assigned to another trainer."""
    from app.models.trainer import Trainer

    other_trainer = Trainer(
        first_name="Morgan",
        last_name="Smith",
        email="morgan.isolation@example.com",
        specialization="Strength",
    )
    db_session.add(other_trainer)
    db_session.flush()

    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 20, 9),
        datetime(2026, 11, 20, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 20, 10),
        datetime(2026, 11, 20, 11),
    )

    results = get_trainer_assigned_members(
        db_session,
        other_trainer.trainer_id,
        "Jamie",
    )

    assert results == []


def test_search_treats_wildcards_as_literal_characters(db_session, trainer, member):
    """SQL wildcard characters must be treated as literal input."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 20, 9),
        datetime(2026, 11, 20, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 20, 10),
        datetime(2026, 11, 20, 11),
    )

    assert get_trainer_assigned_members(db_session, trainer.trainer_id, "%") == []

    assert get_trainer_assigned_members(db_session, trainer.trainer_id, "_") == []


def test_assigned_members_are_unique(db_session, trainer, member):
    """Multiple sessions must not duplicate an assigned member."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 25, 9),
        datetime(2026, 11, 25, 14),
    )

    first = book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 25, 9),
        datetime(2026, 11, 25, 10),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 25, 11),
        datetime(2026, 11, 25, 12),
    )

    results = get_trainer_assigned_members(
        db_session,
        trainer.trainer_id,
    )

    assert len(results) == 1
    assert results[0]["member_id"] == member
    assert results[0]["session_id"] == first.session_id


def test_assigned_member_without_health_information(db_session, trainer, member):
    """Members without metrics or goals must remain visible."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 25, 9),
        datetime(2026, 11, 25, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 25, 10),
        datetime(2026, 11, 25, 11),
    )

    results = get_trainer_assigned_members(
        db_session,
        trainer.trainer_id,
    )

    assert len(results) == 1
    assert results[0]["latest_health_metric"] is None
    assert results[0]["active_goals"] == []


def test_assigned_member_returns_latest_health_metric(db_session, trainer, member):
    """Only the most recent health metric should be returned."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 25, 9),
        datetime(2026, 11, 25, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 25, 10),
        datetime(2026, 11, 25, 11),
    )

    older_metric = HealthMetric(
        member_id=member,
        recorded_at=datetime(2026, 11, 20, 9, tzinfo=UTC),
        weight_kg=Decimal("80.00"),
    )

    latest_metric = HealthMetric(
        member_id=member,
        recorded_at=datetime(2026, 11, 24, 9, tzinfo=UTC),
        weight_kg=Decimal("78.50"),
        height_cm=Decimal("180.00"),
        heart_rate_bpm=72,
    )

    db_session.add_all([older_metric, latest_metric])
    db_session.flush()

    results = get_trainer_assigned_members(
        db_session,
        trainer.trainer_id,
    )

    metric = results[0]["latest_health_metric"]

    assert metric["metric_id"] == latest_metric.metric_id
    assert metric["weight_kg"] == Decimal("78.50")
    assert metric["height_cm"] == Decimal("180.00")
    assert metric["heart_rate_bpm"] == 72


def test_assigned_member_returns_only_active_goals(db_session, trainer, member):
    """Completed and abandoned goals must not be displayed."""
    add_trainer_availability(
        db_session,
        trainer.trainer_id,
        datetime(2026, 11, 25, 9),
        datetime(2026, 11, 25, 12),
    )

    book_pt_session(
        db_session,
        member,
        trainer.trainer_id,
        datetime(2026, 11, 25, 10),
        datetime(2026, 11, 25, 11),
    )

    active_goal = FitnessGoal(
        member_id=member,
        target_weight_kg=Decimal("75.00"),
        baseline_weight_kg=Decimal("80.00"),
        status="active",
    )

    completed_goal = FitnessGoal(
        member_id=member,
        target_weight_kg=Decimal("82.00"),
        status="completed",
    )

    abandoned_goal = FitnessGoal(
        member_id=member,
        target_weight_kg=Decimal("70.00"),
        status="abandoned",
    )

    db_session.add_all([active_goal, completed_goal, abandoned_goal])
    db_session.flush()

    results = get_trainer_assigned_members(
        db_session,
        trainer.trainer_id,
    )

    goals = results[0]["active_goals"]

    assert len(goals) == 1
    assert goals[0]["goal_id"] == active_goal.goal_id
    assert goals[0]["target_weight_kg"] == Decimal("75.00")
    assert goals[0]["status"] == "active"


def test_unassigned_member_health_information_is_hidden(db_session, trainer, member):
    """A trainer must not receive an unassigned member's health data."""
    metric = HealthMetric(
        member_id=member,
        weight_kg=Decimal("78.50"),
    )

    goal = FitnessGoal(
        member_id=member,
        target_weight_kg=Decimal("75.00"),
        status="active",
    )

    db_session.add_all([metric, goal])
    db_session.flush()

    results = get_trainer_assigned_members(
        db_session,
        trainer.trainer_id,
        "Jamie",
    )

    assert results == []
