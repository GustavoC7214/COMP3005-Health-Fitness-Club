"""Command-line interface for trainer operations."""

from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import get_db_session
from app.trainers.schedule import build_trainer_schedule
from app.trainers.trainer_service import (
    add_trainer_availability,
    book_pt_session,
    cancel_pt_session,
    get_trainer_assigned_members,
    get_trainer_availability,
    get_trainer_schedule,
    reschedule_pt_session,
)


def read_integer(prompt: str) -> int:
    """Read an integer from the user."""
    return int(input(prompt).strip())


def read_datetime(prompt: str) -> datetime:
    """Read a date and time in ISO format."""
    return datetime.strptime(
        input(f"{prompt} (YYYY-MM-DD HH:MM): ").strip(),
        "%Y-%m-%d %H:%M",
    )


def show_menu() -> None:
    """Display trainer operations."""
    print("\n=== Trainer Management ===")
    print("1. Add trainer availability")
    print("2. View trainer availability")
    print("3. Book personal training session")
    print("4. Reschedule personal training session")
    print("5. Cancel personal training session")
    print("6. View trainer schedule")
    print("7. View assigned members")
    print("0. Return to main menu")


def run_trainer_cli() -> None:
    """Run the trainer management menu."""
    while True:
        show_menu()
        choice = input("Select an option: ").strip()

        if choice == "0":
            return

        if choice not in {"1", "2", "3", "4", "5", "6", "7"}:
            print("Invalid option.")
            continue

        try:
            with get_db_session() as session:
                if choice == "1":
                    trainer_id = read_integer("Trainer ID: ")
                    start = read_datetime("Start time")
                    end = read_datetime("End time")

                    availability = add_trainer_availability(
                        session, trainer_id, start, end
                    )
                    print(f"Availability {availability.availability_id} created.")

                elif choice == "2":
                    trainer_id = read_integer("Trainer ID: ")
                    slots = get_trainer_availability(session, trainer_id)

                    if not slots:
                        print("No availability found.")

                    for slot in slots:
                        print(
                            f"{slot.availability_id}: "
                            f"{slot.start_time} - {slot.end_time}"
                        )

                elif choice == "3":
                    trainer_id = read_integer("Trainer ID: ")
                    member_id = read_integer("Member ID: ")
                    start = read_datetime("Start time")
                    end = read_datetime("End time")

                    booking = book_pt_session(
                        session, member_id, trainer_id, start, end
                    )
                    print(f"PT session {booking.session_id} booked.")

                elif choice == "4":
                    session_id = read_integer("PT session ID: ")
                    start = read_datetime("New start time")
                    end = read_datetime("New end time")

                    booking = reschedule_pt_session(session, session_id, start, end)
                    print(f"PT session {booking.session_id} rescheduled.")

                elif choice == "5":
                    session_id = read_integer("PT session ID: ")
                    booking = cancel_pt_session(session, session_id)
                    print(f"PT session {booking.session_id} cancelled.")

                elif choice == "6":
                    trainer_id = read_integer("Trainer ID: ")
                    bookings = get_trainer_schedule(session, trainer_id)
                    schedule = build_trainer_schedule(bookings)

                    if not schedule:
                        print("No scheduled activities.")

                    for entry in schedule:
                        activity = (
                            "PT Session"
                            if entry.entry_type == "pt_session"
                            else "Group Class"
                        )

                        print(
                            f"{activity} {entry.entry_id}: "
                            f"{entry.description}, "
                            f"{entry.start_time} - {entry.end_time}"
                        )

                elif choice == "7":
                    trainer_id = read_integer("Trainer ID: ")
                    search_name = input(
                        "Search member name (leave blank for all): "
                    ).strip()

                    members = get_trainer_assigned_members(
                        session,
                        trainer_id,
                        search_name or None,
                    )

                    if not members:
                        print("No assigned members.")

                    for member in members:
                        print(
                            f"{member['first_name']} "
                            f"{member['last_name']} "
                            f"(Member {member['member_id']}), "
                            f"Session {member['session_id']}: "
                            f"{member['start_time']} - "
                            f"{member['end_time']}"
                        )

        except (ValueError, OverflowError) as exc:
            print(f"Error: {exc}")
        except SQLAlchemyError as exc:
            print(f"Database operation failed: {exc}")


if __name__ == "__main__":
    run_trainer_cli()
