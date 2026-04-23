import enum

from sqlalchemy import Boolean, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import TimestampMixin


class OrgRole(str, enum.Enum):
    ORG_ADMIN = "ORG_ADMIN"
    MEMBER = "MEMBER"


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[OrgRole] = mapped_column(Enum(OrgRole, name="org_role"), nullable=False, default=OrgRole.MEMBER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="memberships")
    org = relationship("Organization", back_populates="memberships")
    dept_memberships = relationship(
        "DepartmentMembership", back_populates="membership", cascade="all, delete-orphan"
    )


class DepartmentMembership(Base, TimestampMixin):
    __tablename__ = "department_memberships"
    __table_args__ = (UniqueConstraint("membership_id", "department_id", name="uq_deptmem_mem_dept"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    is_head: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    membership = relationship("Membership", back_populates="dept_memberships")
    department = relationship("Department")
