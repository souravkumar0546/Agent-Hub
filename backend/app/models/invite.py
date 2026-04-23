from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Invite(Base):
    """A pending invitation to join the platform (or a specific org).

    Flow:
      1. An admin creates an Invite row with a random `token` (URL-safe).
      2. The admin shares the link `/invite/<token>` with the invitee.
      3. The invitee opens the link, fills in a password, and POSTs to
         `/api/invites/<token>/accept`.
      4. That creates a `User` + `Membership` and stamps `accepted_at`.

    Invite.org_id is null for super-admin invites (which don't belong to
    any one org); otherwise it's the target org.
    """

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)  # SUPER_ADMIN | ORG_ADMIN | MEMBER
    org_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    token: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    org = relationship("Organization")
    invited_by = relationship("User")
