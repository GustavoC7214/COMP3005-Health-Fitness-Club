"""Member 1 business operations using SQLAlchemy ORM.

Services flush but never commit: the caller owns the transaction. Use the
team's get_db_session() in the CLI or other application entry points.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.members import member_queries as queries
from app.members.member_queries import DashboardIntegrations, UpcomingSession
from app.models.member import FitnessGoal, HealthMetric, Member
from app.utils import validators as validate
from app.utils.validators import ValidationError


class MemberNotFoundError(ValueError):
    pass


class GoalNotFoundError(ValueError):
    pass


class DuplicateEmailError(ValueError):
    pass


def _flush(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        # UniqueConstraint, not a pre-check, arbitrates concurrent registrations.
        if (
            getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == "uq_members_email"
        ):
            raise DuplicateEmailError(
                "This email address is already registered."
            ) from exc
        raise


def get_member(session: Session, member_id: int) -> Member:
    member = queries.find_member(session, validate.positive_id(member_id))
    if member is None:
        raise MemberNotFoundError(f"Member {member_id} does not exist.")
    return member


def _profile_values(values: dict) -> dict:
    cleaners = {
        "first_name": lambda v: validate.required_text(v, "First name", 100),
        "last_name": lambda v: validate.required_text(v, "Last name", 100),
        "email": validate.email_address,
        "date_of_birth": validate.birth_date,
        "gender": lambda v: validate.optional_text(v, "Gender", 50),
        "phone": lambda v: validate.optional_text(v, "Phone", 30),
    }
    unknown = values.keys() - cleaners.keys()
    if unknown:
        raise ValidationError(
            f"Unknown profile field(s): {', '.join(sorted(unknown))}."
        )
    return {key: cleaners[key](value) for key, value in values.items()}


def register_member(
    session: Session,
    *,
    first_name,
    last_name,
    email,
    date_of_birth,
    gender=None,
    phone=None,
) -> Member:
    member = Member(
        **_profile_values(
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "date_of_birth": date_of_birth,
                "gender": gender,
                "phone": phone,
            }
        )
    )
    session.add(member)
    _flush(session)
    return member


def update_profile(session: Session, member_id: int, **changes) -> Member:
    member = get_member(session, member_id)
    if not changes:
        raise ValidationError("Supply at least one profile field to update.")
    # Validate the entire request before mutating any ORM object.
    cleaned = _profile_values(changes)
    for key, value in cleaned.items():
        setattr(member, key, value)
    _flush(session)
    return member


def _target_date(value, earliest):
    if value is None:
        return None
    result = validate.calendar_date(value, "Target date")
    if result < earliest:
        raise ValidationError("Target date cannot precede the goal's creation date.")
    return result


def create_fitness_goal(
    session: Session, member_id: int, *, target_weight_kg, target_date=None
) -> FitnessGoal:
    get_member(session, member_id)
    target = validate.measurement(target_weight_kg, "Target weight (kg)", 500)
    deadline = _target_date(target_date, datetime.now(UTC).date())
    baseline = queries.latest_weight(session, member_id)
    goal = FitnessGoal(
        member_id=member_id,
        target_weight_kg=target,
        target_date=deadline,
        baseline_weight_kg=baseline.weight_kg if baseline else None,
    )
    session.add(goal)
    _flush(session)
    return goal


def update_fitness_goal(
    session: Session, member_id: int, goal_id: int, **changes
) -> FitnessGoal:
    get_member(session, member_id)
    validate.positive_id(goal_id, "Goal ID")
    goal = session.scalar(
        select(FitnessGoal).where(
            FitnessGoal.goal_id == goal_id,
            FitnessGoal.member_id == member_id,
        )
    )
    if goal is None:
        raise GoalNotFoundError(
            f"Goal {goal_id} does not belong to member {member_id}."
        )
    if not changes or changes.keys() - {"target_weight_kg", "target_date", "status"}:
        raise ValidationError("Update target_weight_kg, target_date, or status.")
    cleaned = {}
    if "target_weight_kg" in changes:
        cleaned["target_weight_kg"] = validate.measurement(
            changes["target_weight_kg"], "Target weight (kg)", 500
        )
    if "target_date" in changes:
        cleaned["target_date"] = _target_date(
            changes["target_date"], goal.created_at.astimezone(UTC).date()
        )
    if "status" in changes:
        if changes["status"] not in ("active", "completed", "abandoned"):
            raise ValidationError(
                "Goal status must be active, completed, or abandoned."
            )
        cleaned["status"] = changes["status"]
    for key, value in cleaned.items():
        setattr(goal, key, value)
    _flush(session)
    return goal


def get_fitness_goals(session: Session, member_id: int) -> list[FitnessGoal]:
    get_member(session, member_id)
    return queries.member_goals(session, member_id)


def record_health_metric(
    session: Session,
    member_id: int,
    *,
    weight_kg=None,
    height_cm=None,
    heart_rate_bpm=None,
    recorded_at=None,
) -> HealthMetric:
    get_member(session, member_id)
    if weight_kg is None and height_cm is None and heart_rate_bpm is None:
        raise ValidationError("Supply at least one health measurement.")
    metric = HealthMetric(
        member_id=member_id,
        weight_kg=validate.measurement(weight_kg, "Weight (kg)", 500)
        if weight_kg is not None
        else None,
        height_cm=validate.measurement(height_cm, "Height (cm)", 300)
        if height_cm is not None
        else None,
        heart_rate_bpm=validate.heart_rate(heart_rate_bpm)
        if heart_rate_bpm is not None
        else None,
        recorded_at=validate.metric_timestamp(recorded_at),
    )
    session.add(metric)
    _flush(session)
    return metric


def get_health_history(session: Session, member_id: int) -> list[HealthMetric]:
    get_member(session, member_id)
    return queries.health_history(session, member_id)


@dataclass(frozen=True)
class GoalProgress:
    goal: FitnessGoal
    current_weight_kg: Decimal | None
    progress_percent: Decimal | None


@dataclass(frozen=True)
class MemberDashboard:
    member: Member
    latest_metric: HealthMetric | None
    goals: list[GoalProgress]
    past_class_count: int | None
    upcoming_sessions: list[UpcomingSession] | None
    integration_notes: tuple[str, ...]


def _progress(goal: FitnessGoal, current: Decimal | None) -> GoalProgress:
    baseline = goal.baseline_weight_kg
    percent = None
    if current is not None and baseline is not None:
        distance = goal.target_weight_kg - baseline
        if distance == 0:
            percent = Decimal(100) if current == baseline else Decimal(0)
        else:
            percent = max(
                Decimal(0), min(Decimal(100), (current - baseline) / distance * 100)
            )
        percent = percent.quantize(Decimal("0.01"))
    return GoalProgress(goal, current, percent)


def get_member_dashboard(
    session: Session,
    member_id: int,
    *,
    integrations: DashboardIntegrations | None = None,
) -> MemberDashboard:
    member = get_member(session, member_id)
    integrations = integrations or DashboardIntegrations()
    # Limited SQLAlchemy Core use for the PostgreSQL view; entity reads/writes
    # elsewhere use ORM select/get/add/attribute assignment.
    summary = (
        session.execute(
            select(queries.dashboard_view).where(
                queries.dashboard_view.c.member_id == member_id,
            )
        )
        .mappings()
        .one()
    )
    latest = (
        session.get(HealthMetric, summary["latest_metric_id"])
        if summary["latest_metric_id"]
        else None
    )
    goals = [
        _progress(goal, summary["latest_weight_kg"])
        for goal in queries.member_goals(session, member_id, active_only=True)
    ]
    notes = []
    now = datetime.now(UTC)
    count = None
    if integrations.past_class_count is None:
        notes.append(
            "Class attendance is not integrated: awaiting the class/attendance model and read query."
        )
    else:
        count = integrations.past_class_count(session, member_id, now)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(
                "Attendance query must return a nonnegative integer from PostgreSQL."
            )
    upcoming, note = queries.upcoming_pt_sessions(
        session, member_id, now, integrations.pt_session_timezone
    )
    if note:
        notes.append(note)
    return MemberDashboard(member, latest, goals, count, upcoming, tuple(notes))
