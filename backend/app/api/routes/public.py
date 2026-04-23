"""Unauthenticated read-only endpoints for the pre-login flow.

The login page needs a way to look up an organisation's branding (name +
logo) *before* the user has a session, so we can render the right tenant's
login screen. That lookup can't sit behind auth — chicken / egg. Hence this
module.

Security constraints:

* The only data this router may ever return is org-level *public* metadata
  — `name`, `logo_url`. Never return internal ids, slugs, user lists, role
  info, counts, etc. An unauthenticated enumerator can't be allowed to
  build a tenant inventory.
* Responses must be roughly constant-time. Without that, an attacker can
  enumerate which emails are registered (a known email hits the membership
  lookup path, an unknown one short-circuits → DB-latency oracle). We pad
  every response to a fixed floor.
* 404s are NOT used to signal "email not found". The endpoint returns 200
  with `{name: null, logo_url: null}` for both "no such user" and "user
  exists but has no active membership". Combined with the timing pad, that
  means unknown emails and known-but-orgless emails are indistinguishable
  from the client.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Membership, Organization, User


public_router = APIRouter(prefix="/public", tags=["public"])


class OrgBranding(BaseModel):
    """Everything (and only) what the login page needs.

    `name` and `logo_url` identify the tenant; `user_display_name` powers
    the personalised greeting on the password step.

    Tradeoff note on `user_display_name`: returning this field means a
    pre-auth caller who types any email can learn the name of the real
    person behind it (if they're in an active org). That's the same
    pattern Microsoft 365, Google Workspace, and Slack expose, and it's
    marginally more leaky than returning `{name, logo_url}` alone (which
    already confirms "this email belongs to a known tenant"). We accept
    that tradeoff so the login greeting reflects the identity stored on
    the user record instead of an email-derived guess that falls apart
    on concatenated local-parts like `souravkumar@`.

    Every field is nullable — the frontend falls back cleanly when any
    is absent (unknown email, inactive org, missing display_name, etc).
    """
    name: Optional[str] = None
    logo_url: Optional[str] = None
    user_display_name: Optional[str] = None


# Minimum wall-clock time we guarantee for every call. Anything faster
# than this gets padded up to the floor. Chosen to be noticeably larger
# than the fastest possible DB round-trip (~1 ms local, ~5 ms over a
# cloud network) while still feeling snappy to a human user.
_TIMING_FLOOR_MS = 200


@public_router.get("/orgs/for-email", response_model=OrgBranding)
async def org_for_email(
    # Deliberately NOT typed as `EmailStr`. Strict Pydantic validation
    # (e.g. rejecting `foo@bar.invalid` with a 422) returns *before* the
    # timing pad runs, which would leak "this address is syntactically
    # invalid" via response time. Accepting plain `str` and doing a loose
    # sanity check ourselves keeps every call on the same code path and
    # guaranteed-slow floor.
    email: str = Query(..., description="Work email the user typed at step 1 of login."),
    db: Session = Depends(get_db),
) -> OrgBranding:
    """Return the org's brand info for a typed email, or blanks on miss.

    Resolution order:
      1. Sanity-check the input looks vaguely email-shaped (has `@`, no
         whitespace, within length bounds). Malformed → blanks.
      2. Look up a `User` with this email (lowercased — matches how login
         normalises).
      3. Find the user's first active `Membership` and return that org's
         name + logo.
      4. If the user has no active memberships, or doesn't exist at all,
         return `{name: None, logo_url: None}`.

    Every path — malformed input, unknown user, known user without an
    active org, known user with an org — lands on the same timing floor
    so an enumerator can't distinguish them.
    """
    started = time.monotonic()
    branding = OrgBranding()

    try:
        # Permissive check: the value must contain exactly one `@`, no
        # whitespace, and be within a reasonable length. Anything else →
        # blanks, but we still pad to the floor before returning.
        normalised = (email or "").strip().lower()
        looks_like_email = (
            1 < len(normalised) <= 320
            and normalised.count("@") == 1
            and " " not in normalised
            and "\t" not in normalised
        )
        if looks_like_email:
            user = (
                db.query(User)
                .filter(User.email == normalised, User.is_active.is_(True))
                .one_or_none()
            )
            if user is not None:
                membership = (
                    db.query(Membership)
                    .filter(
                        Membership.user_id == user.id,
                        Membership.is_active.is_(True),
                    )
                    .order_by(Membership.id.asc())  # stable order — oldest membership wins
                    .first()
                )
                if membership is not None:
                    org = (
                        db.query(Organization)
                        .filter(
                            Organization.id == membership.org_id,
                            Organization.is_active.is_(True),
                        )
                        .one_or_none()
                    )
                    if org is not None:
                        # Only attach the display name when the whole happy
                        # path resolves (valid user + active membership +
                        # active org). Intentionally sending only
                        # `user.name` — never email, role, or any other
                        # column — the greeting needs nothing else.
                        branding = OrgBranding(
                            name=org.name,
                            logo_url=org.logo_url,
                            user_display_name=(user.name or None),
                        )
    except Exception:
        # Never leak why a branding lookup failed. The login page can cope
        # with a blank response and will render generic branding.
        branding = OrgBranding()

    # Pad to the timing floor. Do NOT short-circuit when already over the
    # floor — that's the point; slow paths are allowed to be slow.
    elapsed_ms = (time.monotonic() - started) * 1000
    if elapsed_ms < _TIMING_FLOOR_MS:
        await asyncio.sleep((_TIMING_FLOOR_MS - elapsed_ms) / 1000)

    return branding
