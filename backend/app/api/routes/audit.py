from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_admin, OrgContext
from app.models import AuditLog


router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEntry(BaseModel):
    id: int
    action: str
    target_type: str | None = None
    target_id: str | None = None
    user_id: int | None = None
    department_id: int | None = None
    meta: dict = {}
    created_at: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuditEntry])
def list_audit(ctx: OrgContext = Depends(require_org_admin), db: Session = Depends(get_db), limit: int = 100):
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.org_id == ctx.org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AuditEntry(
            id=r.id,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            user_id=r.user_id,
            department_id=r.department_id,
            meta=r.meta or {},
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
