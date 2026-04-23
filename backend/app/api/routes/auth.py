from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_org_context, OrgContext
from app.core.security import create_access_token, verify_password
from app.models import DepartmentMembership, Membership, Organization, User
from app.schemas.auth import (
    DepartmentSummary,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OrgSummary,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _build_me(db: Session, user: User, current_org_id: int | None = None) -> MeResponse:
    memberships = (
        db.query(Membership).filter(Membership.user_id == user.id, Membership.is_active.is_(True)).all()
    )
    orgs = [
        OrgSummary(
            id=m.org.id, name=m.org.name, slug=m.org.slug,
            role=m.role.value, logo_url=m.org.logo_url,
        )
        for m in memberships
    ]

    default_org_id = current_org_id
    if default_org_id is None and memberships:
        default_org_id = memberships[0].org_id

    current_role: str | None = None
    departments: list[DepartmentSummary] = []
    if default_org_id is not None:
        current_mem = next((m for m in memberships if m.org_id == default_org_id), None)
        if current_mem:
            current_role = current_mem.role.value
            dms = (
                db.query(DepartmentMembership)
                .filter(DepartmentMembership.membership_id == current_mem.id)
                .all()
            )
            departments = [
                DepartmentSummary(
                    id=dm.department.id,
                    name=dm.department.name,
                    slug=dm.department.slug,
                    is_head=dm.is_head,
                )
                for dm in dms
            ]
        elif user.is_super_admin:
            # Super admin impersonating an org they're not a member of.
            # Surface a synthetic org entry so the frontend's brand/topbar
            # lookups (which key off user.current_org_id → user.orgs) have
            # a match; otherwise the sidebar and topbar fall back to the
            # platform branding even after the admin has opened a tenant.
            imp_org = db.get(Organization, default_org_id)
            if imp_org is not None and not any(o.id == imp_org.id for o in orgs):
                orgs.append(OrgSummary(
                    id=imp_org.id,
                    name=imp_org.name,
                    slug=imp_org.slug,
                    role="SUPER_ADMIN",
                    logo_url=imp_org.logo_url,
                ))
            current_role = "SUPER_ADMIN"

    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_super_admin=user.is_super_admin,
        orgs=orgs,
        current_org_id=default_org_id,
        current_org_role=current_role,
        departments=departments,
    )


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.email == req.email.lower()).one_or_none()
    if not user or not user.is_active or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user.id, extra={"email": user.email})
    return LoginResponse(access_token=token, user=_build_me(db, user))


@router.get("/me", response_model=MeResponse)
def me(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> MeResponse:
    return _build_me(db, ctx.user, ctx.org_id)
