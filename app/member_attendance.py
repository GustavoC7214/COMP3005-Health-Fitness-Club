"""Minimal course/attendance data needed by the Member 1 dashboard.

These are shared data entities, not a class scheduling or administration UI.
Other modules can reuse them or supply their own dashboard reader.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.member import Member


class GroupClass(Base):
    __tablename__ = "group_classes"

    class_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled", server_default="scheduled"
    )
    attendance: Mapped[list["ClassAttendance"]] = relationship(
        back_populates="group_class", passive_deletes="all"
    )

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_group_classes_name"),
        CheckConstraint("end_time > start_time", name="ck_group_classes_time"),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_group_classes_status",
        ),
    )


class ClassAttendance(Base):
    __tablename__ = "class_attendance"

    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.member_id", ondelete="RESTRICT"), primary_key=True
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("group_classes.class_id", ondelete="RESTRICT"), primary_key=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="registered", server_default="registered"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    member: Mapped[Member] = relationship()
    group_class: Mapped[GroupClass] = relationship(back_populates="attendance")

    __table_args__ = (
        CheckConstraint(
            "status IN ('registered', 'attended', 'absent', 'cancelled')",
            name="ck_class_attendance_status",
        ),
        Index("ix_class_attendance_member_status", "member_id", "status"),
        Index("ix_class_attendance_class", "class_id"),
    )
