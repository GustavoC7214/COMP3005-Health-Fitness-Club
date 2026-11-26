"""Health and Fitness Club Management System entry point."""

import argparse

from sqlalchemy.exc import SQLAlchemyError

from app.members.member_cli import run_member_cli
from app.trainers.trainer_cli import run_trainer_cli


def show_main_menu() -> None:
    """Display the available management roles."""
    print("\n=== Health & Fitness Club Management ===")
    print("1. Member Management")
    print("2. Trainer Management")
    print("3. Administrative Management")
    print("0. Exit")


def run_main_menu() -> None:
    """Route users to the selected management menu."""
    while True:
        show_main_menu()

        try:
            choice = input("Select an option: ").strip()

            if choice == "0":
                print("Goodbye.")
                return

            if choice == "1":
                run_member_cli()

            elif choice == "2":
                run_trainer_cli()

            elif choice == "3":
                print("Administrative management is not yet integrated.")

            else:
                print("Invalid option.")

        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return


def main() -> int:
    """Initialize the database or launch the application."""
    parser = argparse.ArgumentParser(
        description="COMP 3005 Health & Fitness Club Management System"
    )

    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Create registered ORM tables and dashboard view",
    )

    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Insert explicit Member 1 demo data using ORM",
    )

    args = parser.parse_args()

    try:
        if args.init_db:
            from app.database.init_db import init_db

            init_db()

        if args.seed_demo:
            from app.database.connection import get_db_session
            from app.database.member_setup import seed_member_demo

            with get_db_session() as session:
                member_id = seed_member_demo(session)

            print(f"Demo member ID: {member_id}")

        if not args.init_db and not args.seed_demo:
            run_main_menu()

        return 0

    except (SQLAlchemyError, ValueError):
        print(
            "Setup failed. Check PostgreSQL, .env, "
            "and the setup instructions in README.md."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
