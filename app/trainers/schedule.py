"""Shared representation of trainer schedule entries."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.models.trainer import PTSession


def to_utc(value: datetime) -> datetime:
    """Interpret naive scheduling timestamps as UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def to_naive_utc(value: datetime) -> datetime:
    """Normalize a timestamp to naive UTC for database storage."""
    return to_utc(value).replace(tzinfo=None)


def format_schedule_time(value: datetime) -> str:
    """Display a scheduling timestamp explicitly in UTC."""
    return to_utc(value).strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass(frozen=True)
class ScheduleEntry:
    """One personal training session or group fitness class."""

    entry_type: Literal["pt_session", "group_class"]
    entry_id: int
    start_time: datetime
    end_time: datetime
    description: str


def build_trainer_schedule(
    pt_sessions: list[PTSession],
    group_classes: list[ScheduleEntry] | None = None,
) -> list[ScheduleEntry]:
    """Combine PT sessions and group classes in chronological order."""
    entries = [
        ScheduleEntry(
            entry_type="pt_session",
            entry_id=pt.session_id,
            start_time=pt.start_time,
            end_time=pt.end_time,
            description=f"Member {pt.member_id}",
        )
        for pt in pt_sessions
    ]

    if group_classes is not None:
        entries.extend(group_classes)

    return sorted(
        entries,
        key=lambda entry: (
            to_utc(entry.start_time),
            to_utc(entry.end_time),
            entry.entry_type,
            entry.entry_id,
        ),
    )
