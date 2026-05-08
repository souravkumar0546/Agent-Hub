from datetime import datetime

from sqlalchemy import (
    Boolean, String, Integer, Float, Text, DateTime, ForeignKey, JSON,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CacmRun(Base):
    """One CACM (Continuous Audit & Continuous Monitoring) execution.

    Persists run metadata for a single KPI evaluation: who triggered it, which
    KPI, lifecycle status, and the rolled-up totals once it completes."""

    __tablename__ = "cacm_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kpi_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    process: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_exceptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exception_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    events = relationship(
        "CacmRunEvent",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="CacmRunEvent.seq",
    )
    exceptions = relationship(
        "CacmException", back_populates="run", cascade="all, delete-orphan"
    )


class CacmRunEvent(Base):
    """Ordered progress event emitted during a CACM run (extract, analyze, etc.)."""

    __tablename__ = "cacm_run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_cacm_event_run_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("cacm_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run = relationship("CacmRun", back_populates="events")


class CacmException(Base):
    """A single record flagged by a CACM run, with risk level and source payload."""

    __tablename__ = "cacm_exceptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("cacm_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    exception_no: Mapped[str] = mapped_column(String(40), nullable=False)
    risk: Mapped[str] = mapped_column(String(10), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    run = relationship("CacmRun", back_populates="exceptions")


class CacmSchedule(Base):
    """Scheduled recurring run of a single CACM KRI.

    One row per (org, process, KRI). Saving the same KRI again upserts
    frequency/time/next_run_at. The `kpi_type` is denormalized at create
    time so the scheduler doesn't depend on the catalog at fire time.
    """

    __tablename__ = "cacm_schedules"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "process_key", "kri_name",
            name="uq_cacm_schedule_org_process_kri",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    process_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kri_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kpi_type: Mapped[str] = mapped_column(String(80), nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    time_of_day: Mapped[str] = mapped_column(String(5), nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("cacm_runs.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=func.true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    last_run = relationship("CacmRun", foreign_keys=[last_run_id])
