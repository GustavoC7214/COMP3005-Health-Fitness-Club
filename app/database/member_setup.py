"""Install the Member 1 view using the existing engine, and optional ORM demo data."""

from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def install_member_view(bind: Engine) -> None:
    sql = (Path(__file__).resolve().parents[2] / "sql" / "views.sql").read_text(
        encoding="utf-8"
    )
    with bind.begin() as connection:
        connection.execute(text(sql))


def seed_member_demo(session: Session) -> int:
    """Explicit opt-in demo fixture. Never used as dashboard fallback data."""
    from app.database.attendance_setup import seed_attendance_demo
    from app.members.member_service import (
        create_fitness_goal,
        record_health_metric,
        register_member,
    )
    from app.models.member import Member

    existing = session.scalar(
        select(Member).where(Member.email == "member1.demo@example.com")
    )
    if existing:
        seed_attendance_demo(session, existing.member_id)
        return existing.member_id
    member = register_member(
        session,
        first_name="Demo",
        last_name="Member",
        email="member1.demo@example.com",
        date_of_birth="2000-01-01",
        gender="Prefer not to say",
        phone="613-555-0100",
    )
    record_health_metric(
        session, member.member_id, weight_kg="80", height_cm="175", heart_rate_bpm=70
    )
    create_fitness_goal(session, member.member_id, target_weight_kg="75")
    record_health_metric(
        session, member.member_id, weight_kg="78", height_cm="175", heart_rate_bpm=68
    )
    seed_attendance_demo(session, member.member_id)
    return member.member_id
