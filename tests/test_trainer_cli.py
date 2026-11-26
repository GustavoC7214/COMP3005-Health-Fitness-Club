"""Unit tests for the trainer command-line interface."""

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.trainers.schedule import ScheduleEntry
from app.trainers.trainer_cli import (
    read_datetime,
    read_integer,
    run_trainer_cli,
)


def test_read_integer():
    """Integer input should be parsed correctly."""
    with patch("builtins.input", return_value=" 42 "):
        assert read_integer("Trainer ID: ") == 42


def test_read_datetime():
    """Datetime input should explicitly request UTC."""
    with patch(
        "builtins.input",
        return_value="2026-11-17 10:30",
    ) as mock_input:
        result = read_datetime("Start time")

    assert result == datetime(2026, 11, 17, 10, 30)

    mock_input.assert_called_once_with("Start time (YYYY-MM-DD HH:MM, UTC): ")


def test_exit_trainer_menu():
    """Option zero should exit without opening a database session."""
    with (
        patch("builtins.input", return_value="0"),
        patch("app.trainers.trainer_cli.get_db_session") as mock_session,
    ):
        run_trainer_cli()

    mock_session.assert_not_called()


def test_invalid_menu_option(capsys):
    """Invalid options should be rejected without database access."""
    with (
        patch("builtins.input", side_effect=["99", "0"]),
        patch("app.trainers.trainer_cli.get_db_session") as mock_session,
    ):
        run_trainer_cli()

    assert "Invalid option." in capsys.readouterr().out
    mock_session.assert_not_called()


def test_add_availability_menu(capsys):
    """Option one should create trainer availability."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    availability = SimpleNamespace(availability_id=12)

    with (
        patch(
            "builtins.input",
            side_effect=[
                "1",
                "5",
                "2026-11-17 09:00",
                "2026-11-17 12:00",
                "0",
            ],
        ),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.add_trainer_availability",
            return_value=availability,
        ) as mock_add,
    ):
        run_trainer_cli()

    mock_add.assert_called_once_with(
        fake_session,
        5,
        datetime(2026, 11, 17, 9),
        datetime(2026, 11, 17, 12),
    )

    assert "Availability 12 created." in capsys.readouterr().out


def test_book_pt_session_menu(capsys):
    """Option three should call the booking service."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    booking = SimpleNamespace(session_id=21)

    with (
        patch(
            "builtins.input",
            side_effect=[
                "3",
                "5",
                "10",
                "2026-11-17 10:00",
                "2026-11-17 11:00",
                "0",
            ],
        ),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.book_pt_session",
            return_value=booking,
        ) as mock_book,
    ):
        run_trainer_cli()

    mock_book.assert_called_once_with(
        fake_session,
        10,
        5,
        datetime(2026, 11, 17, 10),
        datetime(2026, 11, 17, 11),
    )

    assert "PT session 21 booked." in capsys.readouterr().out


def test_invalid_trainer_id(capsys):
    """Invalid integer input should produce a readable error."""
    with (
        patch("builtins.input", side_effect=["1", "abc", "0"]),
        patch("app.trainers.trainer_cli.get_db_session"),
    ):
        run_trainer_cli()

    assert "Error:" in capsys.readouterr().out


def test_view_availability_menu(capsys):
    """Option two displays trainer availability."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    slot = SimpleNamespace(
        availability_id=7,
        start_time=datetime(2026, 11, 19, 9),
        end_time=datetime(2026, 11, 19, 12),
    )

    with (
        patch("builtins.input", side_effect=["2", "5", "0"]),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.get_trainer_availability",
            return_value=[slot],
        ) as mock_get,
    ):
        run_trainer_cli()

    mock_get.assert_called_once_with(fake_session, 5)
    output = capsys.readouterr().out

    assert "2026-11-19 09:00:00 UTC" in output
    assert "2026-11-19 12:00:00 UTC" in output


def test_reschedule_pt_session_menu(capsys):
    """Option four reschedules an existing PT session."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    booking = SimpleNamespace(session_id=21)

    with (
        patch(
            "builtins.input",
            side_effect=[
                "4",
                "21",
                "2026-11-19 13:00",
                "2026-11-19 14:00",
                "0",
            ],
        ),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.reschedule_pt_session",
            return_value=booking,
        ) as mock_reschedule,
    ):
        run_trainer_cli()

    mock_reschedule.assert_called_once_with(
        fake_session,
        21,
        datetime(2026, 11, 19, 13),
        datetime(2026, 11, 19, 14),
    )
    assert "PT session 21 rescheduled." in capsys.readouterr().out


def test_cancel_pt_session_menu(capsys):
    """Option five cancels an existing PT session."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    booking = SimpleNamespace(session_id=21)

    with (
        patch("builtins.input", side_effect=["5", "21", "0"]),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.cancel_pt_session",
            return_value=booking,
        ) as mock_cancel,
    ):
        run_trainer_cli()

    mock_cancel.assert_called_once_with(fake_session, 21)
    assert "PT session 21 cancelled." in capsys.readouterr().out


def test_view_trainer_schedule_menu(capsys):
    """Option six displays scheduled PT sessions."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    booking = SimpleNamespace(
        session_id=21,
        member_id=10,
        start_time=datetime(2026, 11, 19, 10),
        end_time=datetime(2026, 11, 19, 11),
    )

    with (
        patch("builtins.input", side_effect=["6", "5", "0"]),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.get_trainer_schedule",
            return_value=[booking],
        ) as mock_schedule,
    ):
        run_trainer_cli()

    mock_schedule.assert_called_once_with(fake_session, 5)
    output = capsys.readouterr().out
    assert "Session 21" in output
    assert "Member 10" in output
    assert "2026-11-19 10:00:00 UTC" in output
    assert "2026-11-19 11:00:00 UTC" in output


def test_view_assigned_members_menu(capsys):
    """Option seven displays members assigned to a trainer."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    assigned_member = {
        "member_id": 10,
        "first_name": "Jamie",
        "last_name": "Taylor",
        "session_id": 21,
        "start_time": datetime(2026, 11, 19, 10),
        "end_time": datetime(2026, 11, 19, 11),
        "latest_health_metric": None,
        "active_goals": [],
    }

    with (
        patch("builtins.input", side_effect=["7", "5", "", "0"]),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.get_trainer_assigned_members",
            return_value=[assigned_member],
        ) as mock_members,
    ):
        run_trainer_cli()

    mock_members.assert_called_once_with(fake_session, 5, None)
    output = capsys.readouterr().out
    assert "Jamie Taylor" in output
    assert "Member 10" in output
    assert "Session 21" in output
    assert "No health metrics recorded." in output
    assert "No active fitness goals." in output
    assert "2026-11-19 10:00:00 UTC" in output
    assert "2026-11-19 11:00:00 UTC" in output


def test_search_assigned_members_menu(capsys):
    """Option seven passes a member-name filter to the service."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    with (
        patch(
            "builtins.input",
            side_effect=["7", "5", "JAMIE", "0"],
        ),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.get_trainer_assigned_members",
            return_value=[],
        ) as mock_members,
    ):
        run_trainer_cli()

    mock_members.assert_called_once_with(fake_session, 5, "JAMIE")
    assert "No assigned members." in capsys.readouterr().out


def test_view_mixed_trainer_schedule_menu(capsys):
    """Trainer schedule displays both PT sessions and group classes."""
    from contextlib import contextmanager
    from unittest.mock import patch

    from app.trainers.trainer_cli import run_trainer_cli

    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    pt_entry = ScheduleEntry(
        entry_type="pt_session",
        entry_id=1,
        start_time=datetime(2026, 11, 20, 10),
        end_time=datetime(2026, 11, 20, 11),
        description="Member 3",
    )

    class_entry = ScheduleEntry(
        entry_type="group_class",
        entry_id=5,
        start_time=datetime(2026, 11, 20, 9),
        end_time=datetime(2026, 11, 20, 10),
        description="Morning Yoga",
    )

    with (
        patch(
            "builtins.input",
            side_effect=["6", "2", "0"],
        ),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.get_trainer_schedule",
            return_value=[],
        ),
        patch(
            "app.trainers.trainer_cli.build_trainer_schedule",
            return_value=[class_entry, pt_entry],
        ),
    ):
        run_trainer_cli()

    output = capsys.readouterr().out

    assert "Group Class 5" in output
    assert "Morning Yoga" in output
    assert "PT Session 1" in output
    assert "Member 3" in output

    assert output.index("Group Class 5") < output.index("PT Session 1")


def test_view_assigned_member_health_information(capsys):
    """Option seven displays health metrics and active fitness goals."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    assigned_member = {
        "member_id": 10,
        "first_name": "Jamie",
        "last_name": "Taylor",
        "session_id": 21,
        "start_time": datetime(2026, 11, 25, 10),
        "end_time": datetime(2026, 11, 25, 11),
        "latest_health_metric": {
            "metric_id": 1,
            "recorded_at": datetime(2026, 11, 24, 9),
            "weight_kg": 78.5,
            "height_cm": 180,
            "heart_rate_bpm": 72,
        },
        "active_goals": [
            {
                "goal_id": 1,
                "target_weight_kg": 75,
                "baseline_weight_kg": 80,
                "target_date": None,
                "status": "active",
            }
        ],
    }

    with (
        patch(
            "builtins.input",
            side_effect=["7", "5", "Jamie", "0"],
        ),
        patch(
            "app.trainers.trainer_cli.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.trainers.trainer_cli.get_trainer_assigned_members",
            return_value=[assigned_member],
        ) as mock_members,
    ):
        run_trainer_cli()

    mock_members.assert_called_once_with(
        fake_session,
        5,
        "Jamie",
    )

    output = capsys.readouterr().out

    assert "Jamie Taylor" in output
    assert "Latest health metrics:" in output
    assert "Weight: 78.5 kg" in output
    assert "Height: 180 cm" in output
    assert "Heart rate: 72 bpm" in output
    assert "Active fitness goals:" in output
    assert "Target weight: 75 kg" in output
    assert "Baseline weight: 80 kg" in output


def test_trainer_menu_displays_timezone(capsys):
    """The trainer menu should identify the scheduling timezone."""
    with patch("builtins.input", return_value="0"):
        run_trainer_cli()

    output = capsys.readouterr().out

    assert "All scheduling times are in UTC." in output
