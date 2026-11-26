"""Register all ORM models with the shared SQLAlchemy Base."""

from app.models.member import FitnessGoal, HealthMetric, Member
from app.models.member_attendance import ClassAttendance, GroupClass
from app.models.trainer import PTSession, Trainer, TrainerAvailability

__all__ = [
    "ClassAttendance",
    "FitnessGoal",
    "GroupClass",
    "HealthMetric",
    "Member",
    "PTSession",
    "Trainer",
    "TrainerAvailability",
]
