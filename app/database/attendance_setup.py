"""ORM data-entry helpers for course imports and the explicit demo seed.

These are not exposed in the member menu: members cannot mark themselves present.
The caller owns the transaction, as with the existing member services.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.member_attendance import ClassAttendance, GroupClass
from app.utils.validators import ValidationError, positive_id, required_text


def _timestamp(value, label):
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError as exc:
        raise ValidationError(
            f"{label} must be ISO 8601 with a timezone offset."
        ) from exc
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise ValidationError(f"{label} requires a timezone offset.")
    return result.astimezone(UTC)


def create_group_class(
    session: Session, *, name, start_time, end_time, status="scheduled"
) -> GroupClass:
    name = required_text(name, "Class name", 150)
    start = _timestamp(start_time, "Class start")
    end = _timestamp(end_time, "Class end")
    if end <= start:
        raise ValidationError("Class end must be after its start.")
    if status not in ("scheduled", "completed", "cancelled"):
        raise ValidationError(
            "Class status must be scheduled, completed, or cancelled."
        )
    group_class = GroupClass(name=name, start_time=start, end_time=end, status=status)
    session.add(group_class)
    session.flush()
    return group_class


def set_class_attendance(
    session: Session, member_id: int, class_id: int, *, status="registered"
) -> ClassAttendance:
    positive_id(member_id)
    positive_id(class_id, "Class ID")
    if status not in ("registered", "attended", "absent", "cancelled"):
        raise ValidationError(
            "Attendance status must be registered, attended, absent, or cancelled."
        )
    if session.get(Member, member_id) is None:
        raise ValidationError(f"Member {member_id} does not exist.")
    group_class = session.get(GroupClass, class_id)
    if group_class is None:
        raise ValidationError(f"Class {class_id} does not exist.")
    if status == "attended":
        if group_class.status == "cancelled":
            raise ValidationError("A cancelled class cannot be marked attended.")
        if group_class.end_time >= datetime.now(UTC):
            raise ValidationError("Mark attendance after the class has ended.")
    attendance = session.get(ClassAttendance, (member_id, class_id))
    if attendance is None:
        attendance = ClassAttendance(
            member_id=member_id, class_id=class_id, status=status
        )
        session.add(attendance)
    else:
        attendance.status = status
        attendance.recorded_at = datetime.now(UTC)
    session.flush()
    return attendance


def seed_attendance_demo(session: Session, member_id: int) -> None:
    """Idempotent, opt-in persisted fixtures: 2 attended; 1 absent; 1 future.

    Reserved names identify only these demonstration fixtures. The dashboard always
    queries stored rows, including when these fixtures are not installed.
    """
    now = datetime.now(UTC)
    for title, days, class_status, attendance_status in (
        ("Member1 demo - Yoga", -4, "completed", "attended"),
        ("Member1 demo - Strength", -3, "completed", "attended"),
        ("Member1 demo - Mobility", -2, "completed", "absent"),
        ("Member1 demo - Upcoming", 7, "scheduled", "registered"),
    ):
        group_class = session.scalar(
            select(GroupClass)
            .where(GroupClass.name == title)
            .order_by(GroupClass.class_id)
            .limit(1)
        )
        if group_class is None:
            start = now + timedelta(days=days)
            group_class = create_group_class(
                session,
                name=title,
                start_time=start,
                end_time=start + timedelta(hours=1),
                status=class_status,
            )
        if session.get(ClassAttendance, (member_id, group_class.class_id)) is None:
            set_class_attendance(
                session, member_id, group_class.class_id, status=attendance_status
            )
