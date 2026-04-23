"""Integrations — catalog browse, CRUD, and connection test.

Route layout:
  GET    /api/integrations/catalog     — static catalog (any org member)
  GET    /api/integrations             — list configured (any org member)
  POST   /api/integrations             — create (ORG_ADMIN)
  PATCH  /api/integrations/{id}        — update (ORG_ADMIN)
  DELETE /api/integrations/{id}        — remove (ORG_ADMIN)
  POST   /api/integrations/{id}/test   — run the per-type health check (ORG_ADMIN)

Secrets are never returned on the wire. The GET shape returns
`has_credentials: bool` and `credential_keys: [...]` so the UI can render
"●●●● · Replace" instead of the real values.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_db, require_org, require_org_admin, OrgContext
from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.integrations import CATALOG, get_def, get_test_handler
from app.models import AuditLog, Integration


router = APIRouter(prefix="/integrations", tags=["integrations"])


# ── schemas ──────────────────────────────────────────────────────────────────


class IntegrationCreate(BaseModel):
    type: str
    name: str
    config: dict[str, Any] = {}
    credentials: dict[str, Any] = {}


class IntegrationUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    credentials: dict[str, Any] | None = None  # full replace if provided


def _out(i: Integration) -> dict[str, Any]:
    creds = decrypt_credentials(i.credentials_encrypted)
    definition = get_def(i.type)
    return {
        "id": i.id,
        "type": i.type,
        "name": i.name,
        "status": i.status,
        "config": i.config or {},
        "has_credentials": bool(creds),
        "credential_keys": sorted(list(creds.keys())),  # names only, never values
        "last_tested_at": i.last_tested_at.isoformat() if i.last_tested_at else None,
        "last_error": i.last_error,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
        "display": {
            "name": definition.name if definition else i.type,
            "description": definition.description if definition else "",
            "icon": definition.icon if definition else "plug",
            "category": definition.category if definition else "General",
            "implemented": bool(definition and definition.implemented),
        },
    }


def _audit(db: DbSession, ctx: OrgContext, action: str, integration: Integration, meta: dict | None = None) -> None:
    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action=action,
        target_type="integration",
        target_id=str(integration.id),
        meta={"type": integration.type, "name": integration.name, **(meta or {})},
    ))
    db.commit()


# ── catalog ──────────────────────────────────────────────────────────────────


@router.get("/catalog")
def catalog(_: OrgContext = Depends(require_org)):
    return [
        {
            "type": d.type,
            "name": d.name,
            "description": d.description,
            "icon": d.icon,
            "category": d.category,
            "implemented": d.implemented,
            "fields": d.schema(),
        }
        for d in CATALOG
    ]


# ── list / get ───────────────────────────────────────────────────────────────


@router.get("")
def list_integrations(ctx: OrgContext = Depends(require_org), db: DbSession = Depends(get_db)):
    rows = db.query(Integration).filter(Integration.org_id == ctx.org_id).order_by(Integration.id).all()
    return [_out(i) for i in rows]


@router.get("/{integration_id}")
def get_integration(
    integration_id: int,
    ctx: OrgContext = Depends(require_org),
    db: DbSession = Depends(get_db),
):
    i = db.get(Integration, integration_id)
    if i is None or i.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Integration not found")
    return _out(i)


# ── create / update / delete ─────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
def create_integration(
    payload: IntegrationCreate,
    ctx: OrgContext = Depends(require_org_admin),
    db: DbSession = Depends(get_db),
):
    definition = get_def(payload.type)
    if definition is None:
        raise HTTPException(status_code=400, detail=f"Unknown integration type: {payload.type}")

    existing = (
        db.query(Integration)
        .filter(
            Integration.org_id == ctx.org_id,
            Integration.type == payload.type,
            Integration.name == payload.name,
        )
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=409, detail="An integration with that type + name already exists")

    i = Integration(
        org_id=ctx.org_id,
        type=payload.type,
        name=payload.name or definition.name,
        status="disconnected",
        config=payload.config or {},
        credentials_encrypted=encrypt_credentials(payload.credentials),
    )
    db.add(i)
    db.commit()
    db.refresh(i)
    _audit(db, ctx, "integration.create", i)
    return _out(i)


@router.patch("/{integration_id}")
def update_integration(
    integration_id: int,
    payload: IntegrationUpdate,
    ctx: OrgContext = Depends(require_org_admin),
    db: DbSession = Depends(get_db),
):
    i = db.get(Integration, integration_id)
    if i is None or i.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Integration not found")

    changed: list[str] = []
    if payload.name is not None and payload.name != i.name:
        i.name = payload.name
        changed.append("name")
    if payload.config is not None:
        i.config = payload.config
        changed.append("config")
    if payload.credentials is not None:
        # Empty dict rotates creds to nothing; non-empty replaces them entirely.
        i.credentials_encrypted = encrypt_credentials(payload.credentials)
        # Mark as disconnected — a retest should confirm the new creds work.
        i.status = "disconnected"
        i.last_error = None
        changed.append("credentials")

    db.commit()
    db.refresh(i)
    _audit(db, ctx, "integration.update", i, {"changed": changed})
    return _out(i)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_integration(
    integration_id: int,
    ctx: OrgContext = Depends(require_org_admin),
    db: DbSession = Depends(get_db),
):
    i = db.get(Integration, integration_id)
    if i is None or i.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Integration not found")
    snapshot = {"type": i.type, "name": i.name}
    db.delete(i)
    db.commit()
    # Write audit after commit (target row is gone; keep the metadata).
    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action="integration.delete",
        target_type="integration",
        target_id=str(integration_id),
        meta=snapshot,
    ))
    db.commit()
    return None


# ── test ─────────────────────────────────────────────────────────────────────


@router.post("/{integration_id}/test")
def test_integration(
    integration_id: int,
    ctx: OrgContext = Depends(require_org_admin),
    db: DbSession = Depends(get_db),
):
    i = db.get(Integration, integration_id)
    if i is None or i.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Integration not found")

    handler = get_test_handler(i.type)
    if handler is None:
        i.status = "error"
        i.last_error = "Connection test not implemented yet for this integration type"
        i.last_tested_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(i)
        _audit(db, ctx, "integration.test", i, {"ok": False, "reason": "not_implemented"})
        return {"ok": False, "error": i.last_error, "integration": _out(i)}

    creds = decrypt_credentials(i.credentials_encrypted)
    try:
        ok, err = handler(i.config or {}, creds)
    except Exception as e:  # handlers must not kill the request
        ok, err = False, f"handler crashed: {e}"

    i.status = "connected" if ok else "error"
    i.last_error = None if ok else (err or "unknown error")
    i.last_tested_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(i)
    _audit(db, ctx, "integration.test", i, {"ok": ok, "error": err if not ok else None})
    return {"ok": ok, "error": err, "integration": _out(i)}
