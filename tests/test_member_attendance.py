"""Real attendance filtering, default dashboard wiring, and ORM input checks."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.attendance_setup import create_group_class, set_class_attendance
from app.database.member_setup import seed_member_demo
from app.members.member_queries import (
    DashboardIntegrations,
    count_past_attended_classes,
)
from app.members.member_service import get_member_dashboard, register_member
from app.models.member_attendance import ClassAttendance, GroupClass
from app.utils.validators import ValidationError


def member(session, email="attendance@example.com"):
    return register_member(
        session,
        first_name="Demo",
        last_name="Attendance",
        email=email,
        date_of_birth="2000-01-01",
    )


def course(session, *, days=-2, status="completed", name="Yoga"):
    start = datetime.now(UTC) + timedelta(days=days)
    return create_group_class(
        session,
        name=name,
        start_time=start,
        end_time=start + timedelta(hours=1),
        status=status,
    )


def test_default_attendance_reader_is_installed():
    assert DashboardIntegrations().past_class_count is count_past_attended_classes


@pytest.mark.parametrize("count", [0, 2, 18])
def test_reader_returns_actual_scalar_result(count):
    session = Mock()
    session.scalar.return_value = count
    assert count_past_attended_classes(session, 7, datetime.now(UTC)) == count
    session.scalar.assert_called_once()


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"name": "x" * 151},
        {"start_time": "bad"},
        {"end_time": "2020-01-01T11:00:00"},
        {"end_time": "2020-01-01T09:00:00Z"},
        {"end_time": "2020-01-01T10:00:00Z"},
        {"status": "invalid"},
    ],
)
def test_invalid_class_rejected_before_session_write(changes):
    values = {
        "name": "Yoga",
        "start_time": "2020-01-01T10:00:00Z",
        "end_time": "2020-01-01T11:00:00Z",
    }
    values.update(changes)
    session = Mock()
    with pytest.raises(ValidationError):
        create_group_class(session, **values)
    session.add.assert_not_called()


@pytest.mark.parametrize(
    "member_id,class_id,status",
    [
        (0, 1, "attended"),
        (1, -1, "attended"),
        (True, 1, "attended"),
        (1, 1, "invalid"),
    ],
)
def test_invalid_attendance_rejected_before_session_write(member_id, class_id, status):
    session = Mock()
    with pytest.raises(ValidationError):
        set_class_attendance(session, member_id, class_id, status=status)
    session.add.assert_not_called()


def test_dashboard_default_counts_only_selected_members_past_attendance(m1_session):
    a = member(m1_session)
    b = member(m1_session, "other.attendance@example.com")
    for days, class_status, attendance_status, owner in [
        (-4, "completed", "attended", a),
        (-3, "scheduled", "attended", a),  # ended classes need not be manually closed
        (-2, "completed", "registered", a),
        (-2, "completed", "absent", a),
        (-2, "completed", "cancelled", a),
        (-2, "cancelled", "attended", a),
        (2, "scheduled", "attended", a),
        (-2, "completed", "attended", b),
    ]:
        c = course(m1_session, days=days, status=class_status)
        # Import data may be inconsistent; the read must still exclude it.
        m1_session.add(
            ClassAttendance(
                member_id=owner.member_id, class_id=c.class_id, status=attendance_status
            )
        )
    m1_session.flush()
    dashboard = get_member_dashboard(m1_session, a.member_id)
    assert dashboard.past_class_count == 2
    assert not any("Class attendance" in note for note in dashboard.integration_notes)
    assert get_member_dashboard(m1_session, b.member_id).past_class_count == 1


def test_count_uses_end_time_not_start_and_excludes_exact_cutoff(m1_session):
    a = member(m1_session)
    cutoff = datetime.now(UTC)
    for delta in (-1, 0, 1):
        c = create_group_class(
            m1_session,
            name="Boundary",
            start_time=cutoff - timedelta(hours=2),
            end_time=cutoff + timedelta(seconds=delta),
        )
        m1_session.add(
            ClassAttendance(
                member_id=a.member_id, class_id=c.class_id, status="attended"
            )
        )
    m1_session.flush()
    assert count_past_attended_classes(m1_session, a.member_id, cutoff) == 1


def test_attendance_updates_one_membership_and_persists(m1_session, m1_engine):
    a = member(m1_session)
    c = course(m1_session)
    set_class_attendance(m1_session, a.member_id, c.class_id)
    set_class_attendance(m1_session, a.member_id, c.class_id, status="attended")
    set_class_attendance(m1_session, a.member_id, c.class_id, status="attended")
    member_id = a.member_id
    m1_session.commit()
    with Session(m1_engine) as other:
        assert other.scalar(select(func.count()).select_from(ClassAttendance)) == 1
        assert get_member_dashboard(other, member_id).past_class_count == 1


def test_data_helpers_reject_missing_entities_future_and_cancelled_classes(m1_session):
    a = member(m1_session)
    c = course(m1_session)
    with pytest.raises(ValidationError):
        set_class_attendance(m1_session, 999999, c.class_id)
    with pytest.raises(ValidationError):
        set_class_attendance(m1_session, a.member_id, 999999)
    for c in (course(m1_session, days=1), course(m1_session, status="cancelled")):
        with pytest.raises(ValidationError):
            set_class_attendance(m1_session, a.member_id, c.class_id, status="attended")


def test_database_rejects_duplicate_member_class_pair(m1_session):
    a = member(m1_session)
    c = course(m1_session)
    set_class_attendance(m1_session, a.member_id, c.class_id, status="attended")
    m1_session.commit()
    m1_session.add(
        ClassAttendance(member_id=a.member_id, class_id=c.class_id, status="attended")
    )
    with pytest.raises(IntegrityError):
        m1_session.flush()
    m1_session.rollback()


def test_demo_attendance_is_persisted_idempotent_and_separate_from_new_members(
    m1_session,
):
    demo = seed_member_demo(m1_session)
    assert seed_member_demo(m1_session) == demo
    assert m1_session.scalar(select(func.count()).select_from(GroupClass)) == 4
    assert m1_session.scalar(select(func.count()).select_from(ClassAttendance)) == 4
    assert get_member_dashboard(m1_session, demo).past_class_count == 2
    new_member = member(m1_session)
    assert get_member_dashboard(m1_session, new_member.member_id).past_class_count == 0
