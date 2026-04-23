from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserAgent(Base):
    """A user's pick from their org's installed agents.

    The existence of a row = "agent X is in user U's personal workspace in org O".
    The platform catalog is in code (`app.agents.CATALOG`).
    The org-installed subset is `Agent` rows with `is_enabled=True`.
    The user-picked subset is these rows.

    Scoping note: `(user_id, agent_id)` is globally unique; we store `org_id`
    for efficient list-by-org queries (a user could be in multiple orgs, each
    with independent picks of their own Agent rows).
    """

    __tablename__ = "user_agents"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_id", name="uq_user_agent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    user = relationship("User")
    org = relationship("Organization")
    agent = relationship("Agent")
