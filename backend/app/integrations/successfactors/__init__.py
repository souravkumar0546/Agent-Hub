"""SAP SuccessFactors — test-connection handler.

Strategy: attempt an OAuth client-credentials exchange at
`{base_url}/oauth/token` using the configured client ID + secret, then
call `/odata/v2/User?$top=1&$format=json` with the bearer token.

Any 2xx from the OData call → connected.
401/403 → the tenant is reachable but the credentials are wrong.
DNS / timeout / 5xx → surface the error text.

This deliberately uses plain httpx (no SF SDK) because SF's SOAP/OAuth
flow is simple and we don't want another heavy dep for a health check.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
import urllib.error
import json
import socket


_TIMEOUT = 10  # seconds — health checks must not block the request thread long


def _fetch(url: str, *, data=None, headers=None, method: str = "GET") -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b""
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        raise RuntimeError(f"network error: {e}")


def test_connection(config: dict, credentials: dict) -> tuple[bool, str | None]:
    base_url = (config.get("base_url") or "").rstrip("/")
    if not base_url:
        return False, "Base URL is required"

    client_id = credentials.get("client_id") or ""
    client_secret = credentials.get("client_secret") or ""
    if not client_id or not client_secret:
        return False, "Client ID and client secret are required"

    # 1. OAuth token exchange.
    token_url = f"{base_url}/oauth/token"
    payload = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "company_id": config.get("company_id") or "",
    }).encode("utf-8")

    try:
        status, body = _fetch(
            token_url, data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
    except RuntimeError as e:
        return False, str(e)

    if status != 200:
        snippet = body.decode("utf-8", errors="replace")[:300]
        return False, f"OAuth {status} from {token_url}: {snippet}"

    try:
        access_token = json.loads(body).get("access_token")
    except json.JSONDecodeError:
        return False, "OAuth response was not valid JSON"
    if not access_token:
        return False, "OAuth response missing access_token"

    # 2. Hit a cheap OData endpoint.
    odata_url = f"{base_url}/odata/v2/User?$top=1&$format=json"
    try:
        status, body = _fetch(
            odata_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    except RuntimeError as e:
        return False, str(e)

    if 200 <= status < 300:
        return True, None

    snippet = body.decode("utf-8", errors="replace")[:300]
    return False, f"OData {status} from /User: {snippet}"
