"""CLI recovery and commit behavior; PostgreSQL CLI flow uses m1_engine."""

from contextlib import contextmanager
from unittest.mock import Mock

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.members import member_cli as cli


def feed(monkeypatch, answers):
    responses = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))


def test_cli_recovers_from_invalid_menu(monkeypatch, capsys):
    feed(monkeypatch, ["bad", "0"])
    cli.run_member_cli()
    assert "Select 0, 1, 2, 3, or 4." in capsys.readouterr().out


def test_cli_handles_input_error(monkeypatch, capsys):
    @contextmanager
    def fake_session():
        yield Mock()

    monkeypatch.setattr(cli, "get_db_session", fake_session)
    feed(monkeypatch, ["3", "not-an-id", "0"])
    cli.run_member_cli()
    assert "positive integer ID" in capsys.readouterr().out


def test_cli_does_not_report_success_before_commit(monkeypatch, capsys):
    @contextmanager
    def failing_commit():
        yield Mock()
        raise OperationalError("COMMIT", {}, Exception("connection lost"))

    monkeypatch.setattr(cli, "get_db_session", failing_commit)
    monkeypatch.setattr(cli, "_register", lambda session: "Registered member 1.")
    feed(monkeypatch, ["1", "0"])
    cli.run_member_cli()
    output = capsys.readouterr().out
    assert "Database operation failed" in output
    assert "Registered member 1." not in output


def test_cli_all_four_operations_on_postgresql(monkeypatch, capsys, m1_engine):
    from app.database import connection

    monkeypatch.setattr(
        connection, "SessionLocal", sessionmaker(bind=m1_engine, expire_on_commit=False)
    )
    # IDs start at 1 in this test's isolated schema. Duplicate registration fails,
    # rolls back, and the remaining member operations continue successfully.
    feed(
        monkeypatch,
        [
            "1",
            "Benson",
            "Li",
            "b@example.com",
            "2000-01-01",
            "",
            "",
            "1",
            "Benson",
            "Li",
            "B@example.com",
            "2000-01-01",
            "",
            "",
            "2",
            "1",
            "1",
            "first_name",
            "Updated",
            "3",
            "1",
            "1",
            "80",
            "175",
            "70",
            "",
            "2",
            "1",
            "2",
            "75",
            "",
            "3",
            "1",
            "1",
            "78",
            "",
            "",
            "",
            "3",
            "1",
            "2",
            "4",
            "1",
            "0",
        ],
    )
    cli.run_member_cli()
    output = capsys.readouterr().out
    assert "already registered" in output
    assert "Profile updated." in output
    assert "Dashboard: Updated Li" in output
    assert "40.00%" in output
    assert "Past group classes attended: 0" in output
