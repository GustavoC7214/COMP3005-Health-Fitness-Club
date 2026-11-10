"""Business logic for trainer availability and scheduling."""

from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.trainer import PTSession, Trainer, TrainerAvailability


def add_trainer_availability(
    session: Session,
    trainer_id: int,
    start_time: datetime,
    end_time: datetime,
) -> TrainerAvailability:
    """Add a non-overlapping availability interval for a trainer."""
    if start_time >= end_time:
        raise ValueError("End time must be after start time.")

    trainer = session.get(Trainer, trainer_id)
    if trainer is None:
        raise ValueError(f"Trainer {trainer_id} does not exist.")

    overlapping_slot = session.scalar(
        select(TrainerAvailability).where(
            TrainerAvailability.trainer_id == trainer_id,
            TrainerAvailability.start_time < end_time,
            TrainerAvailability.end_time > start_time,
        )
    )

    if overlapping_slot is not None:
        raise ValueError("The requested availability overlaps an existing interval.")

    availability = TrainerAvailability(
        trainer_id=trainer_id,
        start_time=start_time,
        end_time=end_time,
    )

    session.add(availability)
    session.flush()

    return availability


def get_trainer_availability(
    session: Session,
    trainer_id: int,
) -> list[TrainerAvailability]:
    """Return a trainer's availability ordered by starting time."""
    return list(
        session.scalars(
            select(TrainerAvailability)
            .where(TrainerAvailability.trainer_id == trainer_id)
            .order_by(TrainerAvailability.start_time)
        )
    )


def book_pt_session(
    session: Session,
    member_id: int,
    trainer_id: int,
    start_time: datetime,
    end_time: datetime,
) -> PTSession:
    """Book a PT session within a trainer's available hours."""
    if start_time >= end_time:
        raise ValueError("End time must be after start time.")

    # Serialize booking changes for this trainer.
    trainer = session.scalar(
        select(Trainer).where(Trainer.trainer_id == trainer_id).with_for_update()
    )
    if trainer is None:
        raise ValueError(f"Trainer {trainer_id} does not exist.")

    # The Member ORM model is not implemented yet.
    # Verify membership using the agreed shared table contract.
    member_exists = session.scalar(
        text("SELECT EXISTS(SELECT 1 FROM members WHERE member_id = :id)"),
        {"id": member_id},
    )
    if not member_exists:
        raise ValueError(f"Member {member_id} does not exist.")

    # A single availability interval must contain the entire booking.
    available_slot = session.scalar(
        select(TrainerAvailability).where(
            TrainerAvailability.trainer_id == trainer_id,
            TrainerAvailability.start_time <= start_time,
            TrainerAvailability.end_time >= end_time,
        )
    )
    if available_slot is None:
        raise ValueError("The trainer is not available during this time.")

    # Check for another active booking involving the trainer.
    trainer_conflict = session.scalar(
        select(PTSession).where(
            PTSession.trainer_id == trainer_id,
            PTSession.status == "scheduled",
            PTSession.start_time < end_time,
            PTSession.end_time > start_time,
        )
    )
    if trainer_conflict is not None:
        raise ValueError("The trainer already has a booking at this time.")

    # Check whether the member already has an active booking.
    member_conflict = session.scalar(
        select(PTSession).where(
            PTSession.member_id == member_id,
            PTSession.status == "scheduled",
            PTSession.start_time < end_time,
            PTSession.end_time > start_time,
        )
    )
    if member_conflict is not None:
        raise ValueError("The member already has a booking at this time.")

    booking = PTSession(
        member_id=member_id,
        trainer_id=trainer_id,
        start_time=start_time,
        end_time=end_time,
        status="scheduled",
    )

    session.add(booking)
    session.flush()

    return booking


def reschedule_pt_session(
    session: Session,
    session_id: int,
    new_start_time: datetime,
    new_end_time: datetime,
) -> PTSession:
    """Reschedule an existing PT session."""
    if new_start_time >= new_end_time:
        raise ValueError("End time must be after start time.")

    booking = session.get(PTSession, session_id)
    if booking is None:
        raise ValueError(f"PT session {session_id} does not exist.")

    if booking.status != "scheduled":
        raise ValueError("Only scheduled PT sessions can be rescheduled.")

    # Lock the trainer row to coordinate concurrent scheduling.
    session.scalar(
        select(Trainer)
        .where(Trainer.trainer_id == booking.trainer_id)
        .with_for_update()
    )

    available_slot = session.scalar(
        select(TrainerAvailability).where(
            TrainerAvailability.trainer_id == booking.trainer_id,
            TrainerAvailability.start_time <= new_start_time,
            TrainerAvailability.end_time >= new_end_time,
        )
    )
    if available_slot is None:
        raise ValueError("The trainer is not available during this time.")

    trainer_conflict = session.scalar(
        select(PTSession).where(
            PTSession.trainer_id == booking.trainer_id,
            PTSession.session_id != session_id,
            PTSession.status == "scheduled",
            PTSession.start_time < new_end_time,
            PTSession.end_time > new_start_time,
        )
    )
    if trainer_conflict is not None:
        raise ValueError("The trainer already has a booking at this time.")

    member_conflict = session.scalar(
        select(PTSession).where(
            PTSession.member_id == booking.member_id,
            PTSession.session_id != session_id,
            PTSession.status == "scheduled",
            PTSession.start_time < new_end_time,
            PTSession.end_time > new_start_time,
        )
    )
    if member_conflict is not None:
        raise ValueError("The member already has a booking at this time.")

    booking.start_time = new_start_time
    booking.end_time = new_end_time

    session.flush()
    return booking


def cancel_pt_session(session: Session, session_id: int) -> PTSession:
    """Cancel an existing scheduled PT session."""
    booking = session.get(PTSession, session_id)

    if booking is None:
        raise ValueError(f"PT session {session_id} does not exist.")

    if booking.status != "scheduled":
        raise ValueError("Only scheduled PT sessions can be cancelled.")

    booking.status = "cancelled"
    session.flush()

    return booking


def get_trainer_schedule(
    session: Session,
    trainer_id: int,
) -> list[PTSession]:
    """Retrieve a trainer's scheduled PT sessions chronologically."""
    return list(
        session.scalars(
            select(PTSession)
            .where(
                PTSession.trainer_id == trainer_id,
                PTSession.status == "scheduled",
            )
            .order_by(PTSession.start_time)
        )
    )


def get_trainer_assigned_members(
    session: Session,
    trainer_id: int,
    search_name: str | None = None,
) -> list[dict]:
    """Return a trainer's assigned members, optionally filtered by name."""
    trainer = session.get(Trainer, trainer_id)
    if trainer is None:
        raise ValueError(f"Trainer {trainer_id} does not exist.")

    query = """
        SELECT
            m.member_id,
            m.first_name,
            m.last_name,
            p.session_id,
            p.start_time,
            p.end_time
        FROM pt_sessions AS p
        JOIN members AS m
            ON p.member_id = m.member_id
        WHERE p.trainer_id = :trainer_id
          AND p.status = 'scheduled'
    """

    parameters = {"trainer_id": trainer_id}

    if search_name is not None and search_name.strip():
        query += r"""
        AND (
            m.first_name ILIKE :search_pattern ESCAPE '\'
            OR m.last_name ILIKE :search_pattern ESCAPE '\'
            OR CONCAT(m.first_name, ' ', m.last_name)
                ILIKE :search_pattern ESCAPE '\'
        )
        """
        escaped_name = (
            search_name.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        parameters["search_pattern"] = f"%{escaped_name}%"

    query += """
        ORDER BY p.start_time, p.session_id
    """

    results = session.execute(text(query), parameters)

    return [dict(row) for row in results.mappings()]
