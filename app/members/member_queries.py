"""Read-only member queries and explicit cross-module dashboard interfaces."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import import_module
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import column, func, inspect, select, table
from sqlalchemy.orm import Session

from app.models.member import FitnessGoal, HealthMetric, Member
from app.models.member_attendance import ClassAttendance, GroupClass

# A view is deliberately not registered as a table in Base.metadata: create_all
# must never try to create a physical member_dashboard table.
dashboard_view = table(
    "member_dashboard",
    *[
        column(name)
        for name in (
            "member_id",
            "latest_metric_id",
            "recorded_at",
            "weight_kg",
            "height_cm",
            "heart_rate_bpm",
            "active_goal_count",
            "latest_weight_kg",
            "weight_recorded_at",
        )
    ],
)


def find_member(session: Session, member_id: int) -> Member | None:
    return session.get(Member, member_id)


def health_history(session: Session, member_id: int) -> list[HealthMetric]:
    return list(
        session.scalars(
            select(HealthMetric)
            .where(HealthMetric.member_id == member_id)
            .order_by(HealthMetric.recorded_at.desc(), HealthMetric.metric_id.desc())
        )
    )


def latest_weight(session: Session, member_id: int) -> HealthMetric | None:
    return session.scalar(
        select(HealthMetric)
        .where(
            HealthMetric.member_id == member_id,
            HealthMetric.weight_kg.is_not(None),
        )
        .order_by(HealthMetric.recorded_at.desc(), HealthMetric.metric_id.desc())
        .limit(1)
    )


def member_goals(
    session: Session, member_id: int, *, active_only: bool = False
) -> list[FitnessGoal]:
    query = select(FitnessGoal).where(FitnessGoal.member_id == member_id)
    if active_only:
        query = query.where(FitnessGoal.status == "active")
    return list(
        session.scalars(query.order_by(FitnessGoal.created_at, FitnessGoal.goal_id))
    )


@dataclass(frozen=True)
class UpcomingSession:
    session_id: int
    trainer_id: int
    start_time: datetime
    end_time: datetime


def past_attended_class_count_statement(member_id: int, as_of: datetime):
    """A selected member's distinct, actually attended classes ended before as_of."""
    return (
        select(func.count(ClassAttendance.class_id.distinct()))
        .select_from(ClassAttendance)
        .join(GroupClass, GroupClass.class_id == ClassAttendance.class_id)
        .where(
            ClassAttendance.member_id == member_id,
            ClassAttendance.status == "attended",
            GroupClass.status != "cancelled",
            GroupClass.end_time < as_of,
        )
    )


def count_past_attended_classes(
    session: Session, member_id: int, as_of: datetime
) -> int:
    return session.scalar(past_attended_class_count_statement(member_id, as_of))


@dataclass(frozen=True)
class DashboardIntegrations:
    # Working default, overridable when the team integrates another class schema.
    past_class_count: Callable[[Session, int, datetime], int] | None = (
        count_past_attended_classes
    )
    # The existing trainer branch uses TIMESTAMP WITHOUT TIME ZONE. Its timezone
    # must be agreed explicitly before those values can be interpreted.
    pt_session_timezone: str | None = None


def upcoming_pt_sessions(
    session: Session,
    member_id: int,
    as_of: datetime,
    naive_timezone: str | None,
) -> tuple[list[UpcomingSession] | None, str | None]:
    """Use Member 2's actual ORM model if merged and its table is installed."""
    module = import_module("app.models.trainer")
    model = getattr(module, "PTSession", None)
    if model is None:
        return (
            None,
            "PT sessions are not integrated: Member 2's PTSession model is not merged.",
        )
    if not inspect(session.connection()).has_table(
        model.__tablename__, schema=model.__table__.schema
    ):
        return (
            None,
            "PTSession is registered but its PostgreSQL table is not installed.",
        )
    aware = model.__table__.c.start_time.type.timezone
    if not aware:
        if not naive_timezone:
            return (
                None,
                "Confirm Member 2's timestamp timezone and set PT_SESSION_TIMEZONE.",
            )
        try:
            zone = UTC if naive_timezone == "UTC" else ZoneInfo(naive_timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(
                "PT_SESSION_TIMEZONE must be a valid IANA timezone, e.g. UTC."
            ) from exc
        cutoff = as_of.astimezone(zone).replace(tzinfo=None)
    else:
        zone = UTC
        cutoff = as_of
    rows = session.scalars(
        select(model)
        .where(
            model.member_id == member_id,
            model.status == "scheduled",
            model.start_time > cutoff,
        )
        .order_by(model.start_time, model.session_id)
    )

    def localized(value):
        return value if value.tzinfo else value.replace(tzinfo=zone)

    return [
        UpcomingSession(
            row.session_id,
            row.trainer_id,
            localized(row.start_time),
            localized(row.end_time),
        )
        for row in rows
    ], None
