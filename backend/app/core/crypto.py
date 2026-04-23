"""Symmetric encryption for integration credentials.

Credentials are stored as a Fernet-encrypted JSON blob. The key comes from
`INTEGRATIONS_SECRET_KEY` in .env (a Fernet key — 32 url-safe base64 bytes).

For dev convenience, if the var is missing we fall back to a deterministic
derived key from `JWT_SECRET` so the app still starts and encrypts. In prod,
set `INTEGRATIONS_SECRET_KEY` explicitly.
"""

from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _derive_dev_key() -> bytes:
    """Deterministic 32-byte Fernet key derived from JWT_SECRET.

    Only used when INTEGRATIONS_SECRET_KEY isn't set — enough to keep
    dev secrets off the wire, not enough for prod (kept separate from
    JWT signing anyway via SHA-256).
    """
    digest = hashlib.sha256(f"sah-integrations:{settings.jwt_secret}".encode()).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    raw = getattr(settings, "integrations_secret_key", "") or ""
    if raw:
        # Caller may pass the URL-safe base64 key directly.
        try:
            return Fernet(raw.encode() if isinstance(raw, str) else raw)
        except Exception:
            # Accept a plain-text secret too — derive a Fernet key from it.
            digest = hashlib.sha256(raw.encode()).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    return Fernet(_derive_dev_key())


def encrypt_credentials(credentials: dict | None) -> str:
    """JSON-serialize + Fernet-encrypt. Returns a str safe to store in a text column."""
    if not credentials:
        return ""
    token = _fernet().encrypt(json.dumps(credentials, ensure_ascii=False).encode("utf-8"))
    return token.decode("ascii")


def decrypt_credentials(token: str | None) -> dict:
    """Reverse of `encrypt_credentials`. Returns {} for empty / invalid tokens."""
    if not token:
        return {}
    try:
        raw = _fernet().decrypt(token.encode("ascii"))
    except InvalidToken:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}
