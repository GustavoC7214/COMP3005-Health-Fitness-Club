"""Run after merging Member 2's real PTSession/Trainer models; no shadow models."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

import app.models.trainer as trainer_models
from app.members.member_queries import DashboardIntegrations
from app.members.member_service import get_member_dashboard, register_member


def test_upcoming_sessions_use_real_trainer_orm(m1_session, m1_engine):
    pt = getattr(trainer_models, "PTSession", None)
    trainer = getattr(trainer_models, "Trainer", None)
    if pt is None or trainer is None:
        pytest.skip(
            "Merge feature/trainers before running the real PT dashboard integration test."
        )
    # feature/trainers requires btree_gist for its own exclusion constraints.
    # The local test DB user must have extension privileges (or preinstall it).
    with m1_engine.begin() as connection:
        connection.execute(
            text("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public")
        )
    trainer.__table__.create(m1_engine)
    pt.__table__.create(m1_engine)
    member = register_member(
        m1_session,
        first_name="A",
        last_name="B",
        email="a@example.com",
        date_of_birth="2000-01-01",
    )
    other = register_member(
        m1_session,
        first_name="C",
        last_name="D",
        email="c@example.com",
        date_of_birth="2000-01-01",
    )
    coach = trainer(
        first_name="Coach",
        last_name="One",
        email="coach@example.com",
        specialization="General",
    )
    m1_session.add(coach)
    m1_session.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    for member_id, offset, status in [
        (member.member_id, 1, "scheduled"),
        (member.member_id, 2, "cancelled"),
        (member.member_id, -1, "scheduled"),
        (member.member_id, 3, "completed"),
        (other.member_id, 4, "scheduled"),
    ]:
        m1_session.add(
            pt(
                member_id=member_id,
                trainer_id=coach.trainer_id,
                start_time=now + timedelta(days=offset),
                end_time=now + timedelta(days=offset, hours=1),
                status=status,
            )
        )
    m1_session.flush()
    # No silent timezone guess for Member 2's naive TIMESTAMP columns.
    pending = get_member_dashboard(m1_session, member.member_id)
    assert pending.upcoming_sessions is None
    result = get_member_dashboard(
        m1_session,
        member.member_id,
        integrations=DashboardIntegrations(pt_session_timezone="UTC"),
    )
    assert len(result.upcoming_sessions) == 1
    assert result.upcoming_sessions[0].trainer_id == coach.trainer_id
