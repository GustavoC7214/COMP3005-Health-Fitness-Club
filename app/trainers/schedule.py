"""Shared representation of trainer schedule entries."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.models.trainer import PTSession


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
            entry.start_time,
            entry.end_time,
            entry.entry_type,
            entry.entry_id,
        ),
    )
