"""Member-only CLI: four operations with profile/goal and health submenus."""

import os

from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import get_db_session
from app.members.member_queries import DashboardIntegrations
from app.members.member_service import (
    create_fitness_goal,
    get_fitness_goals,
    get_health_history,
    get_member_dashboard,
    record_health_metric,
    register_member,
    update_fitness_goal,
    update_profile,
)


def _id(prompt="Member ID: ") -> int:
    try:
        return int(input(prompt).strip())
    except ValueError as exc:
        raise ValueError("Enter a positive integer ID.") from exc


def _optional(prompt):
    return input(prompt).strip() or None


def _show_metrics(metric):
    print(
        f"Record {metric.metric_id} at {metric.recorded_at.isoformat()} | "
        f"weight (kg): {metric.weight_kg if metric.weight_kg is not None else 'not measured'} | "
        f"height (cm): {metric.height_cm if metric.height_cm is not None else 'not measured'} | "
        f"heart rate (bpm): {metric.heart_rate_bpm if metric.heart_rate_bpm is not None else 'not measured'}"
    )


def _register(session):
    member = register_member(
        session,
        first_name=input("First name: "),
        last_name=input("Last name: "),
        email=input("Email: "),
        date_of_birth=input("Date of birth (YYYY-MM-DD): "),
        gender=_optional("Gender (optional): "),
        phone=_optional("Phone (optional): "),
    )
    return (
        f"Registered member {member.member_id}: {member.first_name} {member.last_name}."
    )


def _profile(session):
    member_id = _id()
    print(
        "1. Update personal details\n2. Create weight goal\n3. Update goal\n4. List goals"
    )
    choice = input("Profile action: ").strip()
    if choice == "1":
        fields = (
            "first_name",
            "last_name",
            "email",
            "date_of_birth",
            "gender",
            "phone",
        )
        print("Fields: " + ", ".join(fields))
        field = input("Field to update: ").strip()
        if field not in fields:
            raise ValueError("Select a listed profile field.")
        value = input("New value (blank clears optional gender/phone): ")
        update_profile(session, member_id, **{field: value})
        return "Profile updated."
    if choice == "2":
        goal = create_fitness_goal(
            session,
            member_id,
            target_weight_kg=input("Target weight (kg): "),
            target_date=_optional("Target date (YYYY-MM-DD, optional): "),
        )
        return f"Created goal {goal.goal_id}."
    if choice == "3":
        goal_id = _id("Goal ID: ")
        field = input("Field (target_weight_kg, target_date, status): ").strip()
        value = input("New value (status: active/completed/abandoned): ").strip()
        update_fitness_goal(session, member_id, goal_id, **{field: value or None})
        return "Goal updated."
    if choice == "4":
        goals = get_fitness_goals(session, member_id)
        if not goals:
            print("No fitness goals recorded.")
        for goal in goals:
            print(
                f"Goal {goal.goal_id}: target {goal.target_weight_kg} kg, {goal.status}, due {goal.target_date or 'not set'}"
            )
        return None
    raise ValueError("Select a listed profile action.")


def _health(session):
    member_id = _id()
    choice = input("1. Add measurement\n2. View history\nHealth action: ").strip()
    if choice == "1":
        metric = record_health_metric(
            session,
            member_id,
            weight_kg=_optional("Weight (kg, optional): "),
            height_cm=_optional("Height (cm, optional): "),
            heart_rate_bpm=_optional("Heart rate (bpm, optional): "),
            recorded_at=_optional("Timestamp (ISO 8601 with offset; blank = now): "),
        )
        return f"Added health record {metric.metric_id}; earlier entries are preserved."
    if choice == "2":
        history = get_health_history(session, member_id)
        if not history:
            print("No health measurements recorded.")
        for metric in history:
            _show_metrics(metric)
        return None
    raise ValueError("Select a listed health action.")


def _dashboard(session, integrations):
    dashboard = get_member_dashboard(session, _id(), integrations=integrations)
    print(f"Dashboard: {dashboard.member.first_name} {dashboard.member.last_name}")
    if dashboard.latest_metric:
        _show_metrics(dashboard.latest_metric)
    else:
        print("No health measurements recorded.")
    if not dashboard.goals:
        print("No active fitness goals.")
    for progress in dashboard.goals:
        percent = (
            f"{progress.progress_percent}%"
            if progress.progress_percent is not None
            else "unavailable (starting or current weight missing)"
        )
        print(
            f"Goal {progress.goal.goal_id}: target {progress.goal.target_weight_kg} kg; current {progress.current_weight_kg}; progress {percent}"
        )
    count = dashboard.past_class_count
    print(
        f"Past group classes attended: {count if count is not None else 'not integrated'}"
    )
    if dashboard.upcoming_sessions is None:
        print("Upcoming PT sessions: not integrated")
    elif not dashboard.upcoming_sessions:
        print("No upcoming PT sessions.")
    else:
        for booking in dashboard.upcoming_sessions:
            print(
                f"PT {booking.session_id}, trainer {booking.trainer_id}: {booking.start_time.isoformat()} - {booking.end_time.isoformat()}"
            )
    for note in dashboard.integration_notes:
        print(note)


def run_member_cli(*, integrations: DashboardIntegrations | None = None):
    integrations = integrations or DashboardIntegrations(
        pt_session_timezone=os.getenv("PT_SESSION_TIMEZONE"),
    )
    while True:
        print("\n=== Member Management & Health Tracking ===")
        print(
            "1. User Registration\n2. Profile Management\n3. Health History\n4. Member Dashboard\n0. Exit"
        )
        try:
            choice = input("Select an operation: ").strip()
            if choice == "0":
                return
            if choice not in {"1", "2", "3", "4"}:
                print("Select 0, 1, 2, 3, or 4.")
                continue
            message = None
            with get_db_session() as session:
                if choice == "1":
                    message = _register(session)
                elif choice == "2":
                    message = _profile(session)
                elif choice == "3":
                    message = _health(session)
                else:
                    _dashboard(session, integrations)
            # Only report writes as successful AFTER the shared context commits.
            if message:
                print(message)
        except ValueError as exc:
            print(f"Error: {exc}")
        except SQLAlchemyError:
            print(
                "Database operation failed. Check PostgreSQL/.env and run python main.py --init-db."
            )
        except (EOFError, KeyboardInterrupt):
            print("\nMember menu closed.")
            return


if __name__ == "__main__":
    run_member_cli()
