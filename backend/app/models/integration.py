from datetime import datetime

from sqlalchemy import String, ForeignKey, JSON, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._base import TimestampMixin


class Integration(Base, TimestampMixin):
    """An external system connected to an Org (SuccessFactors, SMTP, Slack, …).

    `type` maps to the handler module under `app/integrations/<type>/`.
    `config` holds non-secret settings (URLs, tenant IDs).
    `credentials_encrypted` holds Fernet-encrypted JSON of any secrets;
    it must never be exposed on the API surface.
    """

    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("org_id", "type", "name", name="uq_integration_org_type_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="disconnected", nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
