from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import TimestampMixin


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # URL to a brand logo. Shown in the top bar and sidebar. Kept as a URL so
    # admins can drop in an external asset today; swap for object-storage
    # upload later when we need per-tenant asset hosting.
    logo_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    memberships = relationship("Membership", back_populates="org", cascade="all, delete-orphan")
    departments = relationship("Department", back_populates="org", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="org", cascade="all, delete-orphan")
