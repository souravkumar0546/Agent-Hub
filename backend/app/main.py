from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Populate os.environ from backend/.env BEFORE any module that reads env at
# import time. Ported DMAhub services use os.getenv(...) directly (rather
# than our pydantic-settings object), so without this call they get empty
# strings for AZURE_OPENAI_ENDPOINT / MODEL / KEY — which blows up as
# "Request URL is missing an http:// or https:// protocol" on the first
# Azure call. Our own code reads from `settings` and is unaffected.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from app.api.deps import require_org
from app.api.routes import agents as agents_routes
from app.api.routes import assistant as assistant_routes
from app.api.routes import audit as audit_routes
from app.api.routes import auth as auth_routes
from app.api.routes import departments as dept_routes
from app.api.routes import integrations as integrations_routes
from app.api.routes import invites as invites_routes
from app.api.routes import me as me_routes
from app.api.routes import members as member_routes
from app.api.routes import org_dashboard as org_dashboard_routes
from app.api.routes import orgs as orgs_routes
from app.api.routes import platform as platform_routes
from app.api.routes import public as public_routes
from app.api.routes import runs as runs_routes
from app.dma.routes import (
    classification as dma_classification,
    classify as dma_classify,
    dedup_group as dma_dedup,
    enrichment as dma_enrichment,
    lookup as dma_lookup,
    master_builder as dma_master_builder,
)
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import User


def _ensure_bootstrap_super_admin(db: Session) -> None:
    """Guarantee the platform super admin exists so the app is loginable on
    a fresh database. This is the only startup-side bootstrap we still run —
    we used to also seed the Syngene demo org + its departments / agents /
    integration, but that's been removed so deleting orgs actually sticks.
    """
    email = settings.bootstrap_super_admin_email.lower()
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        db.add(User(
            email=email,
            name=settings.bootstrap_super_admin_name,
            password_hash=hash_password(settings.bootstrap_super_admin_password),
            is_super_admin=True,
        ))
    elif not user.is_super_admin:
        # If the row drifted to `is_super_admin=False` (manual edit, downgrade,
        # etc.) flip it back — otherwise nobody can reach the Platform view.
        # Password is intentionally NOT reset here; existing users keep theirs.
        user.is_super_admin = True
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic — run `alembic upgrade head` before first start.
    # We only verify the DB looks migrated; we don't run migrations automatically
    # (auto-migration on startup is a production footgun).
    insp = inspect(engine)
    if not insp.has_table("alembic_version"):
        raise RuntimeError(
            "Database is not initialized. Run `alembic upgrade head` from backend/ "
            "before starting the app."
        )

    db = SessionLocal()
    try:
        _ensure_bootstrap_super_admin(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Uniqus Hub API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


api_prefix = "/api"
app.include_router(auth_routes.router, prefix=api_prefix)
app.include_router(orgs_routes.router, prefix=api_prefix)
app.include_router(dept_routes.router, prefix=api_prefix)
app.include_router(member_routes.router, prefix=api_prefix)
app.include_router(agents_routes.router, prefix=api_prefix)
app.include_router(audit_routes.router, prefix=api_prefix)
app.include_router(platform_routes.router, prefix=api_prefix)
app.include_router(runs_routes.agent_runs_router, prefix=api_prefix)
app.include_router(runs_routes.runs_router, prefix=api_prefix)
app.include_router(integrations_routes.router, prefix=api_prefix)
app.include_router(assistant_routes.router, prefix=api_prefix)
app.include_router(me_routes.router, prefix=api_prefix)
app.include_router(org_dashboard_routes.router, prefix=api_prefix)
# Invite flow — 3 routers share the same module; different prefixes.
app.include_router(invites_routes.public_router, prefix=api_prefix)
app.include_router(invites_routes.platform_router, prefix=api_prefix)
app.include_router(invites_routes.org_router, prefix=api_prefix)

# Pre-login branding lookup — unauthenticated, constant-time. Powers the
# email-first login page so we can show the org's name/logo before the
# user has a session.
app.include_router(public_routes.public_router, prefix=api_prefix)

# DMAhub agents — mounted under /api/dma/* behind org-scoped auth.
dma_prefix = f"{api_prefix}/dma"
dma_auth = [Depends(require_org)]
app.include_router(dma_classification.router, prefix=dma_prefix, dependencies=dma_auth)
app.include_router(dma_classify.router, prefix=dma_prefix, dependencies=dma_auth)
app.include_router(dma_dedup.router, prefix=dma_prefix, dependencies=dma_auth)
app.include_router(dma_enrichment.router, prefix=dma_prefix, dependencies=dma_auth)
app.include_router(dma_lookup.router, prefix=dma_prefix, dependencies=dma_auth)
app.include_router(dma_master_builder.router, prefix=dma_prefix, dependencies=dma_auth)
