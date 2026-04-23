from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org, require_org_admin, OrgContext
from app.models import (
    AgentDepartment,
    AuditLog,
    Department,
    DepartmentMembership,
)
from app.schemas.common import DepartmentCreate, DepartmentOut


router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(ctx: OrgContext = Depends(require_org), db: Session = Depends(get_db)):
    depts = db.query(Department).filter(Department.org_id == ctx.org_id).order_by(Department.name).all()
    return [DepartmentOut.model_validate(d) for d in depts]


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    exists = (
        db.query(Department)
        .filter(Department.org_id == ctx.org_id, Department.slug == payload.slug)
        .one_or_none()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="slug already exists")
    dept = Department(org_id=ctx.org_id, name=payload.name, slug=payload.slug, description=payload.description)
    db.add(dept)
    db.flush()
    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action="department.create",
        target_type="department",
        target_id=str(dept.id),
        meta={"name": dept.name, "slug": dept.slug},
    ))
    db.commit()
    db.refresh(dept)
    return DepartmentOut.model_validate(dept)


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dept_id: int,
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Delete a department. FKs to member / agent links are CASCADE so users stay
    in the org but lose this tag; agents scoped only to this dept fall back to
    org-wide visibility once all their other dept links are gone. Knowledge and
    run history keep their rows with `department_id` set to NULL."""
    dept = db.get(Department, dept_id)
    if dept is None or dept.org_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    # Snapshot link counts so the audit entry is useful forensically even once
    # the CASCADEs wipe the rows.
    member_count = (
        db.query(func.count(DepartmentMembership.id))
        .filter(DepartmentMembership.department_id == dept.id)
        .scalar() or 0
    )
    agent_link_count = (
        db.query(func.count(AgentDepartment.id))
        .filter(AgentDepartment.department_id == dept.id)
        .scalar() or 0
    )

    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action="department.delete",
        target_type="department",
        target_id=str(dept.id),
        meta={
            "name": dept.name,
            "slug": dept.slug,
            "removed_member_links": member_count,
            "removed_agent_links": agent_link_count,
        },
    ))
    db.delete(dept)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
