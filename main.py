"""Member 1 entry point; other role menus remain owned by teammates."""

import argparse

from sqlalchemy.exc import SQLAlchemyError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="COMP 3005 Member Management & Health Tracking"
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
            from app.members.member_cli import run_member_cli

            run_member_cli()
        return 0
    except (SQLAlchemyError, ValueError):
        print(
            "Setup failed. Check PostgreSQL, .env, and the setup instructions in README.md."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
