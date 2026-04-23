from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org, require_org_admin, OrgContext
from app.core.security import hash_password
from app.models import Department, DepartmentMembership, Membership, User
from app.models.membership import OrgRole
from app.schemas.common import IdName, InviteRequest, MemberOut


router = APIRouter(prefix="/members", tags=["members"])


def _member_out(m: Membership) -> MemberOut:
    depts = [
        IdName(id=dm.department.id, name=dm.department.name, slug=dm.department.slug)
        for dm in m.dept_memberships
    ]
    return MemberOut(
        user_id=m.user.id,
        email=m.user.email,
        name=m.user.name,
        role=m.role.value,
        departments=depts,
    )


@router.get("", response_model=list[MemberOut])
def list_members(ctx: OrgContext = Depends(require_org), db: Session = Depends(get_db)):
    mems = (
        db.query(Membership)
        .filter(Membership.org_id == ctx.org_id, Membership.is_active.is_(True))
        .all()
    )
    return [_member_out(m) for m in mems]


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def invite_member(
    payload: InviteRequest,
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    email = payload.email.lower()
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        user = User(
            email=email,
            name=payload.name,
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        db.flush()

    existing = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.org_id == ctx.org_id)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member")

    try:
        role = OrgRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    mem = Membership(user_id=user.id, org_id=ctx.org_id, role=role)
    db.add(mem)
    db.flush()

    if payload.department_ids:
        depts = (
            db.query(Department)
            .filter(Department.org_id == ctx.org_id, Department.id.in_(payload.department_ids))
            .all()
        )
        for d in depts:
            db.add(DepartmentMembership(membership_id=mem.id, department_id=d.id))

    db.commit()
    db.refresh(mem)
    return _member_out(mem)
