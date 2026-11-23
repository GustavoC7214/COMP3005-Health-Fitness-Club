"""Member 1 entities; all use the team's existing declarative Base."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Member(Base):
    __tablename__ = "members"

    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    fitness_goals: Mapped[list["FitnessGoal"]] = relationship(
        back_populates="member",
        passive_deletes="all",
    )
    health_metrics: Mapped[list["HealthMetric"]] = relationship(
        back_populates="member",
        passive_deletes="all",
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_members_email"),
        CheckConstraint("length(trim(first_name)) > 0", name="ck_members_first_name"),
        CheckConstraint("length(trim(last_name)) > 0", name="ck_members_last_name"),
        CheckConstraint(
            "email = lower(trim(email)) AND email ~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$'",
            name="ck_members_email",
        ),
        CheckConstraint("date_of_birth <= CURRENT_DATE", name="ck_members_birth_date"),
        CheckConstraint(
            "gender IS NULL OR length(trim(gender)) > 0", name="ck_members_gender"
        ),
        CheckConstraint(
            "phone IS NULL OR length(trim(phone)) > 0", name="ck_members_phone"
        ),
    )


class FitnessGoal(Base):
    """A target weight, with an optional starting-weight snapshot."""

    __tablename__ = "fitness_goals"

    goal_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.member_id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    baseline_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    member: Mapped[Member] = relationship(back_populates="fitness_goals")

    __table_args__ = (
        CheckConstraint(
            "target_weight_kg > 0 AND target_weight_kg <= 500", name="ck_goals_target"
        ),
        CheckConstraint(
            "baseline_weight_kg IS NULL OR (baseline_weight_kg > 0 AND baseline_weight_kg <= 500)",
            name="ck_goals_baseline",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')", name="ck_goals_status"
        ),
        CheckConstraint(
            "target_date IS NULL OR target_date >= CAST(created_at AT TIME ZONE 'UTC' AS date)",
            name="ck_goals_date",
        ),
        Index("ix_fitness_goals_member_status", "member_id", "status"),
    )


class HealthMetric(Base):
    """One timestamped observation. Member services only append these rows."""

    __tablename__ = "health_metrics"

    metric_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.member_id", ondelete="RESTRICT"),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    member: Mapped[Member] = relationship(back_populates="health_metrics")

    __table_args__ = (
        CheckConstraint(
            "weight_kg IS NOT NULL OR height_cm IS NOT NULL OR heart_rate_bpm IS NOT NULL",
            name="ck_metrics_nonempty",
        ),
        CheckConstraint(
            "weight_kg IS NULL OR (weight_kg > 0 AND weight_kg <= 500)",
            name="ck_metrics_weight",
        ),
        CheckConstraint(
            "height_cm IS NULL OR (height_cm > 0 AND height_cm <= 300)",
            name="ck_metrics_height",
        ),
        CheckConstraint(
            "heart_rate_bpm IS NULL OR (heart_rate_bpm > 0 AND heart_rate_bpm <= 300)",
            name="ck_metrics_heart_rate",
        ),
        Index(
            "ix_health_metrics_member_latest",
            "member_id",
            text("recorded_at DESC"),
            text("metric_id DESC"),
        ),
    )
