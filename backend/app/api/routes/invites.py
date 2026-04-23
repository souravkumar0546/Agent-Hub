"""Invite flow — admins create invites, invitees accept them.

Three callers, three creation paths:
  - `POST /api/platform/invites`     — super admin invites an ORG_ADMIN for
                                         an existing org (no email sent yet
                                         — we return the invite URL and the
                                         admin shares it however).
  - `POST /api/members/invites`      — org admin invites a MEMBER of their org.
  - `POST /api/invites/{token}/accept` — public: the invitee accepts by
                                         setting a password. Creates User +
                                         Membership, returns a login JWT.

In production, `POST /.../invites` should trigger an email send via the org's
configured SMTP integration. For now we surface the invite URL back to the
creator so they can share it manually. Email wiring is tracked in the
production-hardening backlog.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    OrgContext,
    get_db,
    require_org_admin,
    require_super_admin,
)
from app.core.security import create_access_token, hash_password
from app.models import (
    AuditLog,
    Department,
    DepartmentMembership,
    Invite,
    Membership,
    Organization,
    User,
)
from app.models.membership import OrgRole


# Separate routers so they mount under different prefixes but share the
# same accept/list/revoke logic.
public_router = APIRouter(prefix="/invites", tags=["invites"])
platform_router = APIRouter(prefix="/platform", tags=["invites"])
org_router = APIRouter(prefix="/members", tags=["invites"])


INVITE_TTL_DAYS = 14


# ── Schemas ─────────────────────────────────────────────────────────────

class OrgInviteBody(BaseModel):
    email: EmailStr
    name: str
    org_id: int
    role: str = Field(default="ORG_ADMIN", pattern="^(ORG_ADMIN|MEMBER)$")


class MemberInviteBody(BaseModel):
    email: EmailStr
    name: str
    role: str = Field(default="MEMBER", pattern="^(ORG_ADMIN|MEMBER)$")
    department_ids: list[int] = []


class AcceptBody(BaseModel):
    password: str = Field(min_length=8)


# ── Helpers ─────────────────────────────────────────────────────────────

def _new_token() -> str:
    # 32 bytes → 43 url-safe chars. Plenty of entropy, readable in URLs.
    return secrets.token_urlsafe(32)


def _invite_url(token: str) -> str:
    # Relative — front-end joins it with the host it's served on. Avoids
    # hardcoding a public URL the backend doesn't actually know.
    return f"/invite/{token}"


def _invite_out(inv: Invite, include_url: bool = False) -> dict:
    org_name = inv.org.name if inv.org else None
    data = {
        "id": inv.id,
        "email": inv.email,
        "name": inv.name,
        "role": inv.role,
        "org_id": inv.org_id,
        "org_name": org_name,
        "invited_by": inv.invited_by.name if inv.invited_by else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
        "revoked_at": inv.revoked_at.isoformat() if inv.revoked_at else None,
    }
    if include_url:
        data["invite_url"] = _invite_url(inv.token)
        data["token"] = inv.token
    return data


def _check_email_free(db: Session, email: str) -> None:
    email = email.lower()
    if db.query(User).filter(User.email == email).one_or_none():
        raise HTTPException(status_code=409, detail="User with this email already exists")
    if (
        db.query(Invite)
        .filter(
            Invite.email == email,
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
        )
        .first()
    ):
        raise HTTPException(status_code=409, detail="An outstanding invite already exists for this email")


# ── POST /api/platform/invites  (super admin → ORG_ADMIN) ────────────────

@platform_router.post("/invites", status_code=status.HTTP_201_CREATED)
def super_admin_invite(
    body: OrgInviteBody,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    org = db.get(Organization, body.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Org not found")
    _check_email_free(db, body.email)

    invite = Invite(
        email=body.email.lower(),
        name=body.name,
        role=body.role,
        org_id=body.org_id,
        invited_by_user_id=None,  # super admin; could wire via dep if we want to track
        token=_new_token(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    db.add(AuditLog(
        org_id=body.org_id,
        user_id=None,
        action="invite.create",
        target_type="invite",
        target_id=str(invite.id),
        meta={"email": body.email, "role": body.role, "invited_by": "super_admin"},
    ))
    db.commit()
    return _invite_out(invite, include_url=True)


# ── POST /api/members/invites  (org admin → MEMBER) ─────────────────────

@org_router.post("/invites", status_code=status.HTTP_201_CREATED)
def org_admin_invite(
    body: MemberInviteBody,
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _check_email_free(db, body.email)

    # Validate departments belong to this org (silently drop mismatches).
    dept_rows = (
        db.query(Department)
        .filter(Department.org_id == ctx.org_id, Department.id.in_(body.department_ids))
        .all()
    )
    dept_ids = [d.id for d in dept_rows]

    invite = Invite(
        email=body.email.lower(),
        name=body.name,
        role=body.role,
        org_id=ctx.org_id,
        invited_by_user_id=ctx.user.id,
        token=_new_token(),
        meta={"department_ids": dept_ids},
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action="invite.create",
        target_type="invite",
        target_id=str(invite.id),
        meta={"email": body.email, "role": body.role, "dept_ids": dept_ids},
    ))
    db.commit()
    return _invite_out(invite, include_url=True)


# ── GET /api/invites/{token}  (public — invite preview) ─────────────────

@public_router.get("/{token}")
def fetch_invite(token: str, db: Session = Depends(get_db)):
    inv = db.query(Invite).filter(Invite.token == token).one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    now = datetime.now(timezone.utc)
    expires_at = inv.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    status_str = "pending"
    if inv.accepted_at is not None:
        status_str = "accepted"
    elif inv.revoked_at is not None:
        status_str = "revoked"
    elif expires_at is not None and expires_at < now:
        status_str = "expired"

    data = _invite_out(inv)
    data["status"] = status_str
    return data


# ── POST /api/invites/{token}/accept  (public — signup via invite) ──────

@public_router.post("/{token}/accept")
def accept_invite(token: str, body: AcceptBody, db: Session = Depends(get_db)):
    inv = db.query(Invite).filter(Invite.token == token).one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invite not found")

    now = datetime.now(timezone.utc)
    expires_at = inv.expires_at.replace(tzinfo=timezone.utc) if inv.expires_at and inv.expires_at.tzinfo is None else inv.expires_at
    if inv.accepted_at is not None:
        raise HTTPException(status_code=410, detail="Invite already accepted")
    if inv.revoked_at is not None:
        raise HTTPException(status_code=410, detail="Invite revoked")
    if expires_at and expires_at < now:
        raise HTTPException(status_code=410, detail="Invite expired")

    # Create the User (or reuse if we've since imported them some other way).
    user = db.query(User).filter(User.email == inv.email.lower()).one_or_none()
    if user is None:
        user = User(
            email=inv.email.lower(),
            name=inv.name,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        db.flush()

    # Super-admin invites (no org_id) set the platform flag. Everything else
    # creates a Membership.
    if inv.org_id is None and inv.role.upper() == "SUPER_ADMIN":
        user.is_super_admin = True
    else:
        if inv.org_id is None:
            raise HTTPException(status_code=400, detail="Invite has no target org")
        role = OrgRole.ORG_ADMIN if inv.role.upper() == "ORG_ADMIN" else OrgRole.MEMBER
        existing_mem = (
            db.query(Membership)
            .filter(Membership.user_id == user.id, Membership.org_id == inv.org_id)
            .one_or_none()
        )
        if existing_mem is None:
            mem = Membership(user_id=user.id, org_id=inv.org_id, role=role)
            db.add(mem)
            db.flush()
            # Link departments if the invite specified any.
            dept_ids = (inv.meta or {}).get("department_ids") or []
            for did in dept_ids:
                db.add(DepartmentMembership(membership_id=mem.id, department_id=did))

    inv.accepted_at = now
    db.add(AuditLog(
        org_id=inv.org_id,
        user_id=user.id,
        action="invite.accept",
        target_type="invite",
        target_id=str(inv.id),
        meta={"email": user.email, "role": inv.role},
    ))
    db.commit()

    token_jwt = create_access_token(user.id, extra={"email": user.email})
    return {
        "access_token": token_jwt,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "org_id": inv.org_id,
    }


# ── List / revoke — admins only ─────────────────────────────────────────

@org_router.get("/invites")
def list_org_invites(
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Invite)
        .filter(Invite.org_id == ctx.org_id)
        .order_by(Invite.created_at.desc())
        .all()
    )
    return [_invite_out(r, include_url=True) for r in rows]


@platform_router.get("/invites")
def list_platform_invites(
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(Invite).order_by(Invite.created_at.desc()).all()
    return [_invite_out(r, include_url=True) for r in rows]


@public_router.delete("/{invite_id}")
def revoke_invite(
    invite_id: int,
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    inv = db.get(Invite, invite_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    # ORG_ADMINs can only revoke their own org's invites. Super admin may
    # use this too (is_org_admin=True via our deps).
    if inv.org_id is not None and inv.org_id != ctx.org_id and not ctx.user.is_super_admin:
        raise HTTPException(status_code=403, detail="Invite belongs to a different org")
    if inv.accepted_at is not None:
        raise HTTPException(status_code=410, detail="Already accepted; cannot revoke")
    inv.revoked_at = datetime.now(timezone.utc)
    db.add(AuditLog(
        org_id=inv.org_id,
        user_id=ctx.user.id,
        action="invite.revoke",
        target_type="invite",
        target_id=str(inv.id),
        meta={"email": inv.email},
    ))
    db.commit()
    return {"status": "revoked"}
