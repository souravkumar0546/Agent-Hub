from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org, require_org_admin, OrgContext
from app.models import AuditLog, Organization
from app.schemas.common import OrgOut
from app.schemas.validators import LogoUrl


router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.get("/current", response_model=OrgOut)
def current_org(
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> OrgOut:
    org = db.get(Organization, ctx.org_id)
    return OrgOut.model_validate(org)


class OrgPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    # Pass "" (empty string) or whitespace to clear an existing logo; omit to
    # leave alone. Any set value must be http:// or https:// — see
    # `app.schemas.validators._validate_logo_url` for why (stored-XSS
    # protection against `javascript:` / `data:` URLs that would render into
    # `<a href>` on the Settings page).
    logo_url: LogoUrl = None


@router.patch("/current", response_model=OrgOut)
def update_current_org(
    body: OrgPatch,
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrgOut:
    """Update the current org. ORG_ADMIN only.

    `name` and `logo_url` are editable. Slug stays fixed because it's used in
    routing and integration keying.
    """
    org = db.get(Organization, ctx.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Org not found")

    changes = {}
    if body.name is not None and body.name != org.name:
        changes["name"] = {"from": org.name, "to": body.name}
        org.name = body.name

    # `logo_url` normalises empty / whitespace to None via the validator, so we
    # can't distinguish "omitted" from "sent as '' to clear" by looking at the
    # value alone — check `model_fields_set` to see if the caller actually
    # supplied the field.
    if "logo_url" in body.model_fields_set:
        new_url = body.logo_url  # already validated and trimmed (or None)
        if new_url != org.logo_url:
            changes["logo_url"] = {"from": org.logo_url, "to": new_url}
            org.logo_url = new_url

    if changes:
        db.add(AuditLog(
            org_id=ctx.org_id,
            user_id=ctx.user.id,
            action="org.update",
            target_type="organization",
            target_id=str(org.id),
            meta=changes,
        ))
    db.commit()
    db.refresh(org)
    return OrgOut.model_validate(org)
