"""SQLAlchemy ORM models.

These mirror the migrations in ``database/migrations``. The analytics layer
reads through the views using Core SQL rather than the ORM (aggregate queries
are clearer and faster expressed directly), so these models exist mainly for:

* the classifier's writes to ``work_item_capability``,
* taxonomy reads,
* work-item lookups,
* giving tests a way to create/inspect rows.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MemoCodeMaster(Base):
    __tablename__ = "memo_code_master"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TimeCodeMaster(Base):
    __tablename__ = "time_code_master"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WorklogRecord(Base):
    """Owned by the time-logging widget. READ-ONLY from this application."""

    __tablename__ = "worklog_record"

    worklog_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    work_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    work_item_type: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    memo_code: Mapped[str] = mapped_column(
        String(100), ForeignKey("memo_code_master.code"), nullable=False
    )
    time_code: Mapped[str] = mapped_column(
        String(100), ForeignKey("time_code_master.code"), nullable=False
    )
    time_code_source: Mapped[str] = mapped_column(String(100), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    modified_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_system: Mapped[str | None] = mapped_column(String(100))
    external_record_id: Mapped[str | None] = mapped_column(String(100))
    sync_status: Mapped[str] = mapped_column(String(100), nullable=False)
    last_sync_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkItem(Base):
    __tablename__ = "work_item"

    work_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
    work_item_type: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    iteration_path: Mapped[str | None] = mapped_column(String(1000))
    area_path: Mapped[str | None] = mapped_column(String(1000))
    created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modified_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    capabilities: Mapped[list["WorkItemCapability"]] = relationship(
        back_populates="work_item", cascade="all, delete-orphan"
    )


class Capability(Base):
    __tablename__ = "capability"

    capability_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sub_capabilities: Mapped[list["SubCapability"]] = relationship(
        back_populates="capability"
    )


class SubCapability(Base):
    __tablename__ = "sub_capability"
    __table_args__ = (UniqueConstraint("capability_id", "name"),)

    sub_capability_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    capability_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("capability.capability_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    capability: Mapped[Capability] = relationship(back_populates="sub_capabilities")


class WorkItemCapability(Base):
    __tablename__ = "work_item_capability"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_wic_confidence"),
    )

    work_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("work_item.work_item_id"), primary_key=True
    )
    capability: Mapped[str] = mapped_column(
        String(255), ForeignKey("capability.name"), primary_key=True
    )
    sub_capability: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    classified_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_human_reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    override_capability: Mapped[str | None] = mapped_column(String(255))
    override_sub_capability: Mapped[str | None] = mapped_column(String(255))

    work_item: Mapped[WorkItem] = relationship(back_populates="capabilities")

    @property
    def effective_capability(self) -> str:
        return self.override_capability or self.capability

    @property
    def effective_sub_capability(self) -> str | None:
        return self.override_sub_capability or self.sub_capability
