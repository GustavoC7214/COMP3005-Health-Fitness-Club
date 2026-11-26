"""Tests for the main application and role menu integration."""

from contextlib import contextmanager
from unittest.mock import patch

from main import main, run_main_menu


def test_main_menu_exit(capsys):
    """Option zero exits the application."""
    with patch("builtins.input", return_value="0"):
        run_main_menu()

    assert "Goodbye." in capsys.readouterr().out


def test_main_menu_member_role():
    """Option one opens the member menu."""
    with (
        patch("builtins.input", side_effect=["1", "0"]),
        patch("main.run_member_cli") as mock_member,
        patch("main.run_trainer_cli") as mock_trainer,
    ):
        run_main_menu()

    mock_member.assert_called_once_with()
    mock_trainer.assert_not_called()


def test_main_menu_trainer_role():
    """Option two opens the trainer menu."""
    with (
        patch("builtins.input", side_effect=["2", "0"]),
        patch("main.run_member_cli") as mock_member,
        patch("main.run_trainer_cli") as mock_trainer,
    ):
        run_main_menu()

    mock_trainer.assert_called_once_with()
    mock_member.assert_not_called()


def test_main_menu_admin_placeholder(capsys):
    """The admin role remains unavailable until integrated."""
    with patch("builtins.input", side_effect=["3", "0"]):
        run_main_menu()

    assert "Administrative management is not yet integrated." in capsys.readouterr().out


def test_main_menu_invalid_option(capsys):
    """Invalid role selections should be rejected."""
    with patch("builtins.input", side_effect=["99", "0"]):
        run_main_menu()

    assert "Invalid option." in capsys.readouterr().out


def test_main_menu_switch_between_roles():
    """Users can return from one role and enter another."""
    with (
        patch("builtins.input", side_effect=["1", "2", "1", "0"]),
        patch("main.run_member_cli") as mock_member,
        patch("main.run_trainer_cli") as mock_trainer,
    ):
        run_main_menu()

    assert mock_member.call_count == 2
    mock_trainer.assert_called_once_with()


def test_main_menu_keyboard_interrupt(capsys):
    """Keyboard interruption should exit gracefully."""
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        run_main_menu()

    assert "Goodbye." in capsys.readouterr().out


def test_main_menu_end_of_input(capsys):
    """End of input should exit gracefully."""
    with patch("builtins.input", side_effect=EOFError):
        run_main_menu()

    assert "Goodbye." in capsys.readouterr().out


def test_main_default_launches_menu():
    """Running without arguments launches the role menu."""
    with (
        patch("sys.argv", ["main.py"]),
        patch("main.run_main_menu") as mock_menu,
    ):
        result = main()

    assert result == 0
    mock_menu.assert_called_once_with()


def test_main_init_db():
    """Database initialization must remain available."""
    with (
        patch("sys.argv", ["main.py", "--init-db"]),
        patch("app.database.init_db.init_db") as mock_init,
        patch("main.run_main_menu") as mock_menu,
    ):
        result = main()

    assert result == 0
    mock_init.assert_called_once_with()
    mock_menu.assert_not_called()


def test_main_seed_demo(capsys):
    """Member demo data seeding must remain available."""
    fake_session = object()

    @contextmanager
    def fake_db_session():
        yield fake_session

    with (
        patch("sys.argv", ["main.py", "--seed-demo"]),
        patch(
            "app.database.connection.get_db_session",
            side_effect=fake_db_session,
        ),
        patch(
            "app.database.member_setup.seed_member_demo",
            return_value=42,
        ) as mock_seed,
        patch("main.run_main_menu") as mock_menu,
    ):
        result = main()

    assert result == 0
    mock_seed.assert_called_once_with(fake_session)
    mock_menu.assert_not_called()
    assert "Demo member ID: 42" in capsys.readouterr().out


def test_main_setup_failure(capsys):
    """Setup errors should return a nonzero exit status."""
    with (
        patch("sys.argv", ["main.py", "--init-db"]),
        patch(
            "app.database.init_db.init_db",
            side_effect=ValueError("Setup error"),
        ),
    ):
        result = main()

    assert result == 1
    assert "Setup failed." in capsys.readouterr().out
