"""SQLAlchemy ORM models for trainers and personal training scheduling."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Trainer(Base):
    """A trainer employed by the fitness club."""

    __tablename__ = "trainers"

    trainer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    specialization: Mapped[str] = mapped_column(String(255), nullable=False)

    availability_slots: Mapped[list["TrainerAvailability"]] = relationship(
        back_populates="trainer",
        cascade="all, delete-orphan",
    )

    pt_sessions: Mapped[list["PTSession"]] = relationship(
        back_populates="trainer",
    )


class TrainerAvailability(Base):
    """A time interval during which a trainer is available."""

    __tablename__ = "trainer_availability"

    availability_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    trainer: Mapped["Trainer"] = relationship(
        back_populates="availability_slots",
    )

    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_trainer_availability_valid_time",
        ),
        ExcludeConstraint(
            ("trainer_id", "="),
            (text("tsrange(start_time, end_time, '[)')"), "&&"),
            name="ex_trainer_availability_no_overlap",
            using="gist",
        ),
        Index(
            "ix_trainer_availability_trainer_start",
            "trainer_id",
            "start_time",
        ),
    )


class PTSession(Base):
    """A personal training session booked by a club member."""

    __tablename__ = "pt_sessions"

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id"),
        nullable=False,
    )
    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.member_id"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="scheduled",
    )

    trainer: Mapped["Trainer"] = relationship(
        back_populates="pt_sessions",
    )

    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_pt_session_valid_time",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_pt_session_status",
        ),
        Index(
            "ix_pt_sessions_trainer_start",
            "trainer_id",
            "start_time",
        ),
        Index(
            "ix_pt_sessions_member_start",
            "member_id",
            "start_time",
        ),
        ExcludeConstraint(
            ("trainer_id", "="),
            (text("tsrange(start_time, end_time, '[)')"), "&&"),
            where=text("status = 'scheduled'"),
            name="ex_pt_sessions_trainer_no_overlap",
            using="gist",
        ),
        ExcludeConstraint(
            ("member_id", "="),
            (text("tsrange(start_time, end_time, '[)')"), "&&"),
            where=text("status = 'scheduled'"),
            name="ex_pt_sessions_member_no_overlap",
            using="gist",
        ),
    )
