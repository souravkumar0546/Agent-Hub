"""Oracle E-Business Suite R12 — test-connection handler.

Strategy:
  1. Validate the configured `base_url` parses cleanly and is `https://`.
  2. HEAD `{base_url}/webservices/rest/ping` (10s timeout). EBS R12 exposes
     this REST ping endpoint for health checks.
       - 200/204 → connected.
       - 401/403 → reachable but credentials weren't validated yet (the
         ping endpoint is sometimes unauthenticated). Returned as a
         success-with-warning.
       - timeout / connection refused / DNS fail → fail.
       - anything else → fail with status code only.
  3. When `auth_mode == "oauth2"`, additionally POST to
     `{base_url}/oauth/token` with `grant_type=client_credentials`. The
     token isn't stored — we just check the endpoint accepted the
     credentials. 200 → confirmed; 401 → "credentials rejected by Oracle
     OAuth endpoint."

Security note (intentional):
  Response bodies are NEVER echoed in error messages — only HTTP status
  codes + standard reasons. This is a deliberate decision to avoid the
  SSRF info-leak class flagged elsewhere in the production review where
  test-connection handlers can be coerced into pinging internal hosts and
  reflecting their responses back to the caller.

Stdlib only (urllib) — no new deps.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from typing import Optional


_TIMEOUT = 10  # seconds — health checks must not block the request thread long


# ── helpers ──────────────────────────────────────────────────────────────────


def _validate_https_url(raw: str) -> tuple[Optional[urllib.parse.ParseResult], Optional[str]]:
    """Parse + sanity-check a base URL. Returns (parsed, error)."""
    if not raw:
        return None, "Base URL is required"
    try:
        parsed = urllib.parse.urlparse(raw)
    except (ValueError, TypeError):
        return None, "Base URL could not be parsed"
    if parsed.scheme.lower() != "https":
        return None, "Base URL must use https://"
    if not parsed.netloc:
        return None, "Base URL is missing host"
    return parsed, None


def _status_phrase(code: int) -> str:
    """Standard reason for a status code, or 'HTTP {code}' as a fallback."""
    try:
        return f"{code} {HTTPStatus(code).phrase}"
    except ValueError:
        return f"HTTP {code}"


def _request(url: str, *, method: str, data: Optional[bytes] = None,
             headers: Optional[dict] = None) -> tuple[Optional[int], Optional[str]]:
    """Issue a request; return (status_code, network_error).

    Exactly one of the two is set. Response bodies are deliberately
    discarded — see the module docstring for the rationale.
    """
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status, None
    except urllib.error.HTTPError as e:
        # HTTPError is "the server answered, but with an error code." Treat
        # it as a real status — body is dropped on purpose.
        return e.code, None
    except socket.timeout:
        return None, "connection timed out"
    except urllib.error.URLError as e:
        # DNS fail, conn refused, TLS fail. `e.reason` is usually a small
        # OSError-ish value safe to surface (no response body involved).
        return None, f"network error: {e.reason}"
    except (TimeoutError, OSError) as e:
        return None, f"network error: {e}"


# ── public entry point ──────────────────────────────────────────────────────


def test_connection(config: dict, credentials: dict) -> tuple[bool, str | None]:
    raw_url = (config.get("base_url") or "").rstrip("/")
    parsed, err = _validate_https_url(raw_url)
    if err:
        return False, err
    base_url = raw_url  # already stripped, already validated

    # 1. Ping the EBS REST health endpoint.
    ping_url = f"{base_url}/webservices/rest/ping"
    status, net_err = _request(ping_url, method="HEAD")
    if net_err is not None:
        return False, f"could not reach Oracle EBS at {parsed.netloc}: {net_err}"

    if status in (200, 204):
        ping_ok = True
        warning: str | None = None
    elif status in (401, 403):
        ping_ok = True
        warning = (
            f"Oracle EBS reachable ({_status_phrase(status)} from /webservices/rest/ping) "
            f"— credentials not yet validated. Provide username/password and re-test."
        )
    else:
        return False, f"Oracle EBS ping returned {_status_phrase(status)}"

    # 2. OAuth-mode: confirm client_credentials work against the OAM bridge.
    auth_mode = (config.get("auth_mode") or "basic").lower()
    if auth_mode == "oauth2":
        client_id = (config.get("client_id") or "").strip()
        client_secret = (credentials.get("client_secret") or "").strip()
        if not client_id or not client_secret:
            return False, (
                "OAuth2 mode selected but client_id and/or client_secret are missing"
            )

        token_url = f"{base_url}/oauth/token"
        payload = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode("utf-8")
        status, net_err = _request(
            token_url, method="POST", data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if net_err is not None:
            return False, f"could not reach Oracle OAuth endpoint: {net_err}"

        if status == 200:
            return True, warning  # propagate any ping warning, may be None
        if status == 401:
            return False, "credentials rejected by Oracle OAuth endpoint"
        return False, f"Oracle OAuth endpoint returned {_status_phrase(status)}"

    # 3. Basic mode: ping result is the answer.
    return ping_ok, warning
