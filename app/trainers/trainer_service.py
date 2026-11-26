"""Business logic for trainer availability and scheduling."""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.members.member_queries import member_goals
from app.models.member import HealthMetric, Member
from app.models.trainer import PTSession, Trainer, TrainerAvailability
from app.trainers.schedule import to_naive_utc


def add_trainer_availability(
    session: Session,
    trainer_id: int,
    start_time: datetime,
    end_time: datetime,
) -> TrainerAvailability:
    """Add a non-overlapping availability interval for a trainer."""
    start_time = to_naive_utc(start_time)
    end_time = to_naive_utc(end_time)

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
    start_time = to_naive_utc(start_time)
    end_time = to_naive_utc(end_time)

    if start_time >= end_time:
        raise ValueError("End time must be after start time.")

    # Serialize booking changes for this trainer.
    trainer = session.scalar(
        select(Trainer).where(Trainer.trainer_id == trainer_id).with_for_update()
    )
    if trainer is None:
        raise ValueError(f"Trainer {trainer_id} does not exist.")

    member = session.get(Member, member_id)

    if member is None:
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
    new_start_time = to_naive_utc(new_start_time)
    new_end_time = to_naive_utc(new_end_time)

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
    """Return assigned members with their latest metrics and active goals."""
    trainer = session.get(Trainer, trainer_id)

    if trainer is None:
        raise ValueError(f"Trainer {trainer_id} does not exist.")

    query = (
        select(Member, PTSession)
        .join(
            PTSession,
            PTSession.member_id == Member.member_id,
        )
        .where(
            PTSession.trainer_id == trainer_id,
            PTSession.status == "scheduled",
        )
    )

    if search_name is not None and search_name.strip():
        escaped_name = (
            search_name.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        pattern = f"%{escaped_name}%"

        query = query.where(
            or_(
                Member.first_name.ilike(pattern, escape="\\"),
                Member.last_name.ilike(pattern, escape="\\"),
                func.concat(
                    Member.first_name,
                    " ",
                    Member.last_name,
                ).ilike(pattern, escape="\\"),
            )
        )

    query = query.order_by(
        PTSession.start_time,
        PTSession.session_id,
    )

    results = []
    seen_members = set()

    for member, booking in session.execute(query):
        if member.member_id in seen_members:
            continue

        seen_members.add(member.member_id)

        latest_metric = session.scalar(
            select(HealthMetric)
            .where(HealthMetric.member_id == member.member_id)
            .order_by(
                HealthMetric.recorded_at.desc(),
                HealthMetric.metric_id.desc(),
            )
            .limit(1)
        )

        active_goals = member_goals(
            session,
            member.member_id,
            active_only=True,
        )

        results.append(
            {
                "member_id": member.member_id,
                "first_name": member.first_name,
                "last_name": member.last_name,
                "session_id": booking.session_id,
                "start_time": booking.start_time,
                "end_time": booking.end_time,
                "latest_health_metric": (
                    {
                        "metric_id": latest_metric.metric_id,
                        "recorded_at": latest_metric.recorded_at,
                        "weight_kg": latest_metric.weight_kg,
                        "height_cm": latest_metric.height_cm,
                        "heart_rate_bpm": latest_metric.heart_rate_bpm,
                    }
                    if latest_metric is not None
                    else None
                ),
                "active_goals": [
                    {
                        "goal_id": goal.goal_id,
                        "target_weight_kg": goal.target_weight_kg,
                        "baseline_weight_kg": goal.baseline_weight_kg,
                        "target_date": goal.target_date,
                        "status": goal.status,
                    }
                    for goal in active_goals
                ],
            }
        )

    return results
