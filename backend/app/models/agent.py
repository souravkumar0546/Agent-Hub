from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, JSON, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import TimestampMixin


class Agent(Base, TimestampMixin):
    """An agent granted to an org by the platform, possibly installed by its admin.

    Two independent permission flags now gate access:

    - `granted_by_platform` — super admin flips this. Controls whether the org
      can see / install the agent at all. Revoking cascades to `is_enabled`.
    - `is_enabled` — org admin flips this. Only meaningful once granted. False
      means the agent is "available but not installed" for this org's members.

    `type` maps to the code module under `app/agents/`."""

    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("org_id", "type", name="uq_agent_org_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(400), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Super-admin gate: must be True before org admin can install.
    granted_by_platform: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Org-admin gate: True means members of the org can actually use the agent
    # (subject to the optional department scope in `AgentDepartment`).
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    org = relationship("Organization", back_populates="agents")
    departments = relationship("AgentDepartment", back_populates="agent", cascade="all, delete-orphan")


class AgentDepartment(Base):
    """Which departments in the org can access this agent. Empty = org-wide."""

    __tablename__ = "agent_departments"
    __table_args__ = (UniqueConstraint("agent_id", "department_id", name="uq_agentdept"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=False
    )

    agent = relationship("Agent", back_populates="departments")
    department = relationship("Department")


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    parent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    input: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
