from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import Membership, Organization, User
from app.models.membership import OrgRole


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    token = _bearer_token(authorization)
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


class OrgContext:
    def __init__(self, user: User, membership: Membership | None, org_id: int | None):
        self.user = user
        self.membership = membership
        self.org_id = org_id

    @property
    def role(self) -> OrgRole | None:
        return self.membership.role if self.membership else None

    @property
    def is_org_admin(self) -> bool:
        return self.user.is_super_admin or (self.membership is not None and self.membership.role == OrgRole.ORG_ADMIN)


def get_org_context(
    x_org_id: Annotated[int | None, Header()] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgContext:
    """Resolve which org the current request is acting on.

    Regular users must supply `X-Org-Id` matching one of their memberships.
    SUPER_ADMIN may pass any org id (support / impersonation).

    H3 gate: the target org must exist **and** be active. A suspended
    (`Organization.is_active=False`) tenant is off-limits to everyone who
    comes through this dependency — including super admins impersonating
    via X-Org-Id. The escape hatch for reactivation is the platform
    super-admin routes (see `require_super_admin` in `platform.py`), which
    don't depend on `get_org_context` and can therefore reach inactive orgs
    to flip the flag back. Any new code path that needs to touch a
    suspended org must do so through those platform routes, not by
    attempting to mint a context.

    We also reject non-existent `x_org_id` here (same generic message) so a
    bogus id doesn't slip past for super admins and then NPE downstream
    when a handler tries to load the org row.
    """
    if x_org_id is None:
        return OrgContext(user=user, membership=None, org_id=None)

    # Gate 1: org exists and is active. Deliberately reuses the same error
    # message for "missing" vs "suspended" so we don't hand an enumerator
    # an oracle for org id existence.
    org = db.get(Organization, x_org_id)
    if org is None or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is not available",
        )

    # Gate 2: caller is either a member of this org OR a super admin.
    membership = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.org_id == x_org_id, Membership.is_active.is_(True))
        .one_or_none()
    )

    if membership is None and not user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")

    return OrgContext(user=user, membership=membership, org_id=x_org_id)


def require_org(ctx: OrgContext = Depends(get_org_context)) -> OrgContext:
    if ctx.org_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Org-Id header required")
    return ctx


def require_org_admin(ctx: OrgContext = Depends(require_org)) -> OrgContext:
    if not ctx.is_org_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ORG_ADMIN required")
    return ctx


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SUPER_ADMIN required")
    return user
