"""Tests for the unified trainer schedule representation."""

from datetime import UTC, datetime, timedelta, timezone

from app.models.trainer import PTSession
from app.trainers.schedule import (
    ScheduleEntry,
    build_trainer_schedule,
    format_schedule_time,
    to_naive_utc,
    to_utc,
)


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


def test_to_utc_with_naive_timestamp():
    value = datetime(2026, 11, 20, 10)

    assert to_utc(value) == datetime(2026, 11, 20, 10, tzinfo=UTC)


def test_to_utc_with_utc_timestamp():
    value = datetime(2026, 11, 20, 10, tzinfo=UTC)

    assert to_utc(value) == value


def test_to_utc_with_non_utc_timestamp():
    eastern = timezone(timedelta(hours=-5))

    value = datetime(2026, 11, 20, 10, tzinfo=eastern)

    assert to_utc(value) == datetime(2026, 11, 20, 15, tzinfo=UTC)


def test_format_naive_schedule_timestamp():
    value = datetime(2026, 11, 20, 10)

    assert format_schedule_time(value) == ("2026-11-20 10:00:00 UTC")


def test_format_aware_schedule_timestamp():
    eastern = timezone(timedelta(hours=-5))

    value = datetime(2026, 11, 20, 10, tzinfo=eastern)

    assert format_schedule_time(value) == ("2026-11-20 15:00:00 UTC")


def test_build_schedule_with_mixed_timezone_timestamps():
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
        start_time=datetime(2026, 11, 20, 9, tzinfo=UTC),
        end_time=datetime(2026, 11, 20, 10, tzinfo=UTC),
        description="Morning Yoga",
    )

    result = build_trainer_schedule([pt], [group_class])

    assert len(result) == 2
    assert result[0].entry_type == "group_class"
    assert result[1].entry_type == "pt_session"


def test_build_schedule_orders_by_actual_instant():
    eastern = timezone(timedelta(hours=-5))

    pt = PTSession(
        session_id=1,
        trainer_id=2,
        member_id=3,
        start_time=datetime(2026, 11, 20, 12),
        end_time=datetime(2026, 11, 20, 13),
        status="scheduled",
    )

    group_class = ScheduleEntry(
        entry_type="group_class",
        entry_id=5,
        start_time=datetime(2026, 11, 20, 9, tzinfo=eastern),
        end_time=datetime(2026, 11, 20, 10, tzinfo=eastern),
        description="Morning Yoga",
    )

    result = build_trainer_schedule([pt], [group_class])

    assert len(result) == 2
    assert result[0].entry_type == "pt_session"
    assert result[1].entry_type == "group_class"


def test_to_naive_utc_with_naive_timestamp():
    value = datetime(2026, 11, 20, 10)

    result = to_naive_utc(value)

    assert result == value
    assert result.tzinfo is None


def test_to_naive_utc_with_utc_timestamp():
    value = datetime(2026, 11, 20, 10, tzinfo=UTC)

    result = to_naive_utc(value)

    assert result == datetime(2026, 11, 20, 10)
    assert result.tzinfo is None


def test_to_naive_utc_with_non_utc_timestamp():
    eastern = timezone(timedelta(hours=-5))
    value = datetime(2026, 11, 20, 10, tzinfo=eastern)

    result = to_naive_utc(value)

    assert result == datetime(2026, 11, 20, 15)
    assert result.tzinfo is None


def test_to_naive_utc_crosses_date_boundary():
    eastern = timezone(timedelta(hours=-5))
    value = datetime(2026, 11, 20, 23, tzinfo=eastern)

    result = to_naive_utc(value)

    assert result == datetime(2026, 11, 21, 4)
    assert result.tzinfo is None
