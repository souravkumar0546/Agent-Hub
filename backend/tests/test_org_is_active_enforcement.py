"""H3 — `get_org_context` refuses to mint a context for inactive orgs.

Security rationale: suspending a tenant (`Organization.is_active = False`)
must actually deny access to every protected endpoint on that tenant. Prior
to this fix the flag was purely cosmetic — reported via `OrgOut` to the
frontend but never enforced on the server.

These tests exercise `get_org_context` as a plain Python function. That
means no TestClient, no HTTP layer, no auth stack — just the dependency's
core contract. We do need a live Postgres (the models use pg-specific
ENUMs), so the module is skipped when `DATABASE_URL` isn't reachable.
"""
from __future__ import annotations

import os
import secrets

import pytest
from fastapi import HTTPException


# --- DB connectivity check (skip the module cleanly on a stale dev box) ----

def _db_reachable() -> bool:
    try:
        from sqlalchemy import text
        from app.core.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="H3 tests need a live DB; skipping (start Postgres and retry).",
)


# --- Fixtures --------------------------------------------------------------

@pytest.fixture(scope="module")
def db_session():
    from app.core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded(db_session):
    """Seed one active + one inactive org with a member in each. Cleanup on teardown.

    We suffix every identifier with random bytes so parallel / repeat runs
    don't collide with leftover rows (and so a failed test leaving rows
    behind doesn't poison the next run on unique-constraint errors).
    """
    from app.core.security import hash_password
    from app.models import Membership, Organization, User
    from app.models.membership import OrgRole

    tag = secrets.token_hex(3)
    inactive_org = Organization(
        name=f"H3 Inactive {tag}",
        slug=f"h3-inactive-{tag}",
        is_active=False,
    )
    active_org = Organization(
        name=f"H3 Active {tag}",
        slug=f"h3-active-{tag}",
        is_active=True,
    )
    db_session.add_all([inactive_org, active_org])
    db_session.flush()

    user = User(
        email=f"h3-test-{tag}@example.com",
        name=f"H3 Test {tag}",
        password_hash=hash_password("S3cureP@ssword!"),
    )
    db_session.add(user)
    db_session.flush()

    db_session.add_all([
        Membership(user_id=user.id, org_id=inactive_org.id, role=OrgRole.MEMBER),
        Membership(user_id=user.id, org_id=active_org.id, role=OrgRole.MEMBER),
    ])
    db_session.commit()

    rec = {
        "user_id": user.id,
        "inactive_org_id": inactive_org.id,
        "active_org_id": active_org.id,
    }
    try:
        yield rec
    finally:
        # Explicit cleanup — cascade deletes would handle most of this but
        # being explicit keeps test noise contained to the rows we created.
        db_session.query(Membership).filter(Membership.user_id == rec["user_id"]).delete()
        db_session.query(User).filter(User.id == rec["user_id"]).delete()
        db_session.query(Organization).filter(
            Organization.id.in_([rec["inactive_org_id"], rec["active_org_id"]])
        ).delete()
        db_session.commit()


# --- Tests -----------------------------------------------------------------

def test_inactive_org_rejected_for_regular_member(db_session, seeded):
    """Member of an inactive org cannot resolve an OrgContext for it."""
    from app.api.deps import get_org_context
    from app.models import User

    user = db_session.get(User, seeded["user_id"])
    assert user.is_super_admin is False, "test precondition: user must NOT be super admin"

    with pytest.raises(HTTPException) as exc_info:
        get_org_context(
            x_org_id=seeded["inactive_org_id"],
            user=user,
            db=db_session,
        )
    assert exc_info.value.status_code == 403
    # Deliberately generic message — don't leak "suspended" vs "not found".
    assert "not available" in exc_info.value.detail.lower()


def test_inactive_org_also_blocks_super_admin(db_session, seeded):
    """The escape hatch is the platform super-admin routes, NOT impersonation
    via X-Org-Id. A super admin who wants to touch a suspended tenant must
    reactivate it first."""
    from app.api.deps import get_org_context
    from app.models import User

    user = db_session.get(User, seeded["user_id"])
    user.is_super_admin = True
    db_session.commit()
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_org_context(
                x_org_id=seeded["inactive_org_id"],
                user=user,
                db=db_session,
            )
        assert exc_info.value.status_code == 403
    finally:
        user.is_super_admin = False
        db_session.commit()


def test_active_org_still_resolves(db_session, seeded):
    """Regression guard: the happy path keeps working. The gate is narrow."""
    from app.api.deps import get_org_context
    from app.models import User

    user = db_session.get(User, seeded["user_id"])
    ctx = get_org_context(
        x_org_id=seeded["active_org_id"],
        user=user,
        db=db_session,
    )
    assert ctx.org_id == seeded["active_org_id"]
    assert ctx.membership is not None
    assert ctx.membership.user_id == seeded["user_id"]


def test_nonexistent_org_id_rejected_even_for_super_admin(db_session, seeded):
    """Latent bug this fix also closes: a super admin sending a bogus
    X-Org-Id previously slipped past the membership check and left the
    downstream handlers with a dangling `ctx.org_id` that didn't map to a
    row. Treat missing and inactive identically."""
    from app.api.deps import get_org_context
    from app.models import User

    user = db_session.get(User, seeded["user_id"])
    user.is_super_admin = True
    db_session.commit()
    try:
        # Pick an id that cannot exist in the DB.
        bogus_id = 2**31 - 1
        with pytest.raises(HTTPException) as exc_info:
            get_org_context(x_org_id=bogus_id, user=user, db=db_session)
        assert exc_info.value.status_code == 403
    finally:
        user.is_super_admin = False
        db_session.commit()


def test_no_header_still_yields_orgless_context(db_session, seeded):
    """Sanity: when `X-Org-Id` isn't set at all, we return a context with
    `org_id=None` and don't try to load any Organization row. Platform
    super-admin flows rely on this shape."""
    from app.api.deps import get_org_context
    from app.models import User

    user = db_session.get(User, seeded["user_id"])
    ctx = get_org_context(x_org_id=None, user=user, db=db_session)
    assert ctx.org_id is None
    assert ctx.membership is None
