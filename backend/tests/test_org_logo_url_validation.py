"""Pydantic-level unit tests for the `logo_url` stored-XSS guard (Critical C7).

The frontend renders `org.logo_url` verbatim into `<a href>` and `<img src>`
on the Settings page, so any scheme other than http(s) is a stored-XSS
vector. These tests pin down the validator behaviour so a future refactor
can't silently regress it.

No DB or network required — we import the request-body schemas and feed
them strings. Pydantic raises `ValidationError` when `_validate_logo_url`
rejects the input.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.routes.orgs import OrgPatch
from app.api.routes.platform import OrgCreate


# --- Rejections -----------------------------------------------------------

@pytest.mark.parametrize(
    "malicious",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",           # case-insensitive reject
        "  javascript:alert(1)  ",       # tolerate leading/trailing space
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "about:blank",
        "mailto:admin@example.com",
        "tel:+15555550100",
        "ftp://example.com/logo.png",    # real scheme but not whitelisted
        "blob:https://evil.example/uuid",
    ],
)
def test_orgpatch_rejects_unsafe_schemes(malicious: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        OrgPatch(logo_url=malicious)
    # The validator-authored message should name the scheme guard so an API
    # client sees a useful failure reason. (Separately from C7: FastAPI's
    # default 422 response body echoes the raw input via `ctx.input`; that
    # payload-reflection is a broader platform concern we address with a
    # global validation-error handler, not inside this validator.)
    msg = str(exc_info.value).lower()
    assert "http://" in msg and "https://" in msg


def test_orgpatch_rejects_missing_host() -> None:
    with pytest.raises(ValidationError):
        OrgPatch(logo_url="https://")


def test_orgpatch_rejects_overlong_url() -> None:
    # MAX_LOGO_URL_LENGTH is 2000; 3000 chars should be rejected.
    too_long = "https://example.com/" + ("a" * 3000)
    with pytest.raises(ValidationError):
        OrgPatch(logo_url=too_long)


def test_orgcreate_rejects_javascript_scheme() -> None:
    # Same guard has to hold on the super-admin org-create path — otherwise
    # a hostile new-tenant payload could plant the XSS before any admin
    # logs in.
    with pytest.raises(ValidationError):
        OrgCreate(
            name="Test Co",
            slug="test-co",
            admin_email="admin@example.com",
            admin_name="Test Admin",
            admin_password="Str0ngP@ssword!",
            logo_url="javascript:alert(1)",
        )


# --- Acceptances -----------------------------------------------------------

def test_accepts_valid_https_url() -> None:
    body = OrgPatch(logo_url="https://example.com/logo.png")
    assert body.logo_url == "https://example.com/logo.png"


def test_accepts_valid_http_url() -> None:
    # Plain http:// is allowed by policy — prod deployments can (and should)
    # enforce https at the ingress, but the app layer doesn't hard-fail
    # on it. Useful for on-prem/intranet logos served over HTTP.
    body = OrgPatch(logo_url="http://intranet.corp.local/logo.png")
    assert body.logo_url == "http://intranet.corp.local/logo.png"


def test_trims_surrounding_whitespace() -> None:
    body = OrgPatch(logo_url="  https://example.com/logo.png  ")
    assert body.logo_url == "https://example.com/logo.png"


def test_empty_or_whitespace_becomes_none() -> None:
    # Existing UX: passing "" from the frontend means "clear the logo".
    assert OrgPatch(logo_url="").logo_url is None
    assert OrgPatch(logo_url="   ").logo_url is None


def test_omitting_field_is_none() -> None:
    body = OrgPatch()
    assert body.logo_url is None
    # And crucially, the route uses model_fields_set to tell "omitted" from
    # "explicitly cleared"; make sure the alias didn't break that.
    assert "logo_url" not in body.model_fields_set

    cleared = OrgPatch(logo_url="")
    assert cleared.logo_url is None
    assert "logo_url" in cleared.model_fields_set
