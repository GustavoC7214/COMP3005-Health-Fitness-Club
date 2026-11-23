"""Register Member 1 models with the shared Base.

When merging feature/trainers, retain BOTH its imports and these imports.
"""

from app.models.member import FitnessGoal, HealthMetric, Member
from app.models.member_attendance import ClassAttendance, GroupClass

__all__ = ["ClassAttendance", "FitnessGoal", "GroupClass", "HealthMetric", "Member"]
