"""Tests for the unified trainer schedule representation."""

from datetime import datetime

from app.models.trainer import PTSession
from app.trainers.schedule import ScheduleEntry, build_trainer_schedule


def test_build_schedule_with_pt_sessions():
    pt = PTSession(
        session_id=1,
        trainer_id=2,
        member_id=3,
        start_time=datetime(2026, 11, 20, 10),
        end_time=datetime(2026, 11, 20, 11),
        status="scheduled",
    )

    result = build_trainer_schedule([pt])

    assert len(result) == 1
    assert result[0].entry_type == "pt_session"
    assert result[0].entry_id == 1
    assert result[0].description == "Member 3"


def test_build_schedule_with_group_classes():
    group_class = ScheduleEntry(
        entry_type="group_class",
        entry_id=5,
        start_time=datetime(2026, 11, 20, 9),
        end_time=datetime(2026, 11, 20, 10),
        description="Morning Yoga",
    )

    result = build_trainer_schedule([], [group_class])

    assert result == [group_class]


def test_build_schedule_chronological_order():
    pt = PTSession(
        session_id=1,
        trainer_id=2,
        member_id=3,
        start_time=datetime(2026, 11, 20, 11),
        end_time=datetime(2026, 11, 20, 12),
        status="scheduled",
    )

    group_class = ScheduleEntry(
        entry_type="group_class",
        entry_id=5,
        start_time=datetime(2026, 11, 20, 9),
        end_time=datetime(2026, 11, 20, 10),
        description="Morning Yoga",
    )

    result = build_trainer_schedule([pt], [group_class])

    assert len(result) == 2
    assert result[0].entry_type == "group_class"
    assert result[1].entry_type == "pt_session"


def test_build_empty_schedule():
    assert build_trainer_schedule([]) == []
