"""Unit tests for the Oracle EBS R12 test_connection handler.

We monkey-patch `urllib.request.urlopen` so the tests never touch the
network. Each scenario the production handler claims to cover is pinned
down here:

  * 200 from /webservices/rest/ping → success, no warning
  * 204 from /ping → success, no warning
  * 401/403 from /ping → success-with-warning (reachable but unauthenticated)
  * timeout / connection refused → failure
  * unexpected status → failure
  * https-only enforcement
  * missing base_url
  * OAuth2 mode: 200 from /oauth/token → success
  * OAuth2 mode: 401 from /oauth/token → "credentials rejected"
  * OAuth2 mode without client_id/secret → failure
  * SSRF info-leak guard: response bodies must NOT appear in error strings

No DB, no network — pure stdlib monkeypatching.
"""

from __future__ import annotations

import io
import socket
import urllib.error
from contextlib import contextmanager

import pytest

from app.integrations.oracle_ebs_r12 import test_connection as oracle_test_connection


# ── monkeypatch helpers ──────────────────────────────────────────────────────


class _FakeResp:
    """Mimics the contextmanager returned by urllib.request.urlopen."""

    def __init__(self, status: int, body: bytes = b""):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


@contextmanager
def _patched_urlopen(monkeypatch, responder):
    """Replace urllib.request.urlopen with `responder(req, timeout)`.

    The responder is called once per request and may either return a
    _FakeResp (success or non-2xx-via-HTTPError), or raise an exception.
    """
    calls: list[dict] = []

    def fake(req, timeout=None):
        calls.append({"url": req.full_url, "method": req.get_method(), "timeout": timeout})
        return responder(req, timeout)

    monkeypatch.setattr("urllib.request.urlopen", fake)
    yield calls


# ── basic-mode happy paths ───────────────────────────────────────────────────


@pytest.mark.parametrize("ping_status", [200, 204])
def test_basic_mode_ping_success(monkeypatch, ping_status: int) -> None:
    """200 / 204 from /ping → connected, no warning."""
    def responder(req, timeout):
        assert req.get_method() == "HEAD"
        assert req.full_url.endswith("/webservices/rest/ping")
        assert timeout == 10
        return _FakeResp(ping_status)

    with _patched_urlopen(monkeypatch, responder) as calls:
        ok, err = oracle_test_connection(
            {"base_url": "https://ebs.example.com:8001", "auth_mode": "basic"},
            {},
        )
    assert ok is True
    assert err is None
    assert len(calls) == 1


@pytest.mark.parametrize("auth_status", [401, 403])
def test_basic_mode_ping_auth_required_returns_warning(monkeypatch, auth_status: int) -> None:
    """401/403 → success-with-warning (reachable, creds not validated)."""
    def responder(req, timeout):
        # urllib raises HTTPError for 4xx/5xx; the fp is required for `.read()`.
        raise urllib.error.HTTPError(
            req.full_url, auth_status, "Unauthorized", hdrs={}, fp=io.BytesIO(b"<html>auth</html>"),
        )

    with _patched_urlopen(monkeypatch, responder):
        ok, err = oracle_test_connection(
            {"base_url": "https://ebs.example.com", "auth_mode": "basic"},
            {},
        )
    assert ok is True
    assert err is not None
    assert "credentials not yet validated" in err
    # SSRF info-leak guard: response body must NOT appear in the error.
    assert "<html>" not in err
    assert "auth</html>" not in err


# ── basic-mode failure paths ─────────────────────────────────────────────────


def test_timeout_is_failure(monkeypatch) -> None:
    """socket.timeout during the ping → fail."""
    def responder(req, timeout):
        raise socket.timeout("timed out")

    with _patched_urlopen(monkeypatch, responder):
        ok, err = oracle_test_connection(
            {"base_url": "https://ebs.example.com", "auth_mode": "basic"},
            {},
        )
    assert ok is False
    assert err is not None
    assert "timed out" in err
    # Hostname should be surfaced for operator clarity, but never a body.
    assert "ebs.example.com" in err


def test_connection_refused_is_failure(monkeypatch) -> None:
    """URLError (DNS / refused / TLS) → fail."""
    def responder(req, timeout):
        raise urllib.error.URLError("[Errno 61] Connection refused")

    with _patched_urlopen(monkeypatch, responder):
        ok, err = oracle_test_connection(
            {"base_url": "https://ebs.example.com", "auth_mode": "basic"},
            {},
        )
    assert ok is False
    assert "could not reach" in err
    assert "Connection refused" in err


def test_unexpected_status_is_failure(monkeypatch) -> None:
    """Non-200/204/401/403 status → fail with status code, no body leak."""
    def responder(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 503, "Service Unavailable",
            hdrs={}, fp=io.BytesIO(b"backend pool exhausted"),
        )

    with _patched_urlopen(monkeypatch, responder):
        ok, err = oracle_test_connection(
            {"base_url": "https://ebs.example.com", "auth_mode": "basic"},
            {},
        )
    assert ok is False
    assert "503" in err
    assert "Service Unavailable" in err
    assert "backend pool exhausted" not in err  # response body never echoed


# ── input validation ─────────────────────────────────────────────────────────


def test_missing_base_url_is_failure() -> None:
    ok, err = oracle_test_connection({"auth_mode": "basic"}, {})
    assert ok is False
    assert "Base URL is required" in err


def test_http_scheme_rejected() -> None:
    """Plain http:// must be rejected — production R12 deployments are TLS only."""
    ok, err = oracle_test_connection(
        {"base_url": "http://ebs.example.com", "auth_mode": "basic"},
        {},
    )
    assert ok is False
    assert "https" in err.lower()


# ── oauth2 mode ──────────────────────────────────────────────────────────────


def test_oauth2_mode_token_endpoint_success(monkeypatch) -> None:
    """OAuth2: ping 200 + /oauth/token 200 → connected."""
    def responder(req, timeout):
        if req.full_url.endswith("/webservices/rest/ping"):
            assert req.get_method() == "HEAD"
            return _FakeResp(200)
        if req.full_url.endswith("/oauth/token"):
            assert req.get_method() == "POST"
            # Body must be x-www-form-urlencoded with grant_type=client_credentials.
            assert b"grant_type=client_credentials" in req.data
            assert b"client_id=cid" in req.data
            assert b"client_secret=secret" in req.data
            return _FakeResp(200, b'{"access_token": "should-not-be-stored"}')
        raise AssertionError(f"unexpected url {req.full_url}")

    with _patched_urlopen(monkeypatch, responder) as calls:
        ok, err = oracle_test_connection(
            {
                "base_url": "https://ebs.example.com",
                "auth_mode": "oauth2",
                "client_id": "cid",
            },
            {"client_secret": "secret"},
        )
    assert ok is True
    assert err is None
    assert len(calls) == 2  # ping + token


def test_oauth2_mode_token_endpoint_401(monkeypatch) -> None:
    """OAuth2: ping 200 but /oauth/token 401 → credentials rejected."""
    def responder(req, timeout):
        if req.full_url.endswith("/webservices/rest/ping"):
            return _FakeResp(200)
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized",
            hdrs={}, fp=io.BytesIO(b'{"error": "invalid_client"}'),
        )

    with _patched_urlopen(monkeypatch, responder):
        ok, err = oracle_test_connection(
            {
                "base_url": "https://ebs.example.com",
                "auth_mode": "oauth2",
                "client_id": "cid",
            },
            {"client_secret": "wrong"},
        )
    assert ok is False
    assert "credentials rejected" in err
    # Body must not be echoed.
    assert "invalid_client" not in err


def test_oauth2_mode_missing_client_credentials_is_failure(monkeypatch) -> None:
    """auth_mode=oauth2 + no client_id/secret → fail before hitting the network."""
    # Patch urlopen to assert it's never called past the ping (we still ping first).
    def responder(req, timeout):
        if req.full_url.endswith("/webservices/rest/ping"):
            return _FakeResp(200)
        raise AssertionError("must not call /oauth/token without credentials")

    with _patched_urlopen(monkeypatch, responder):
        ok, err = oracle_test_connection(
            {"base_url": "https://ebs.example.com", "auth_mode": "oauth2"},
            {},  # no client_secret
        )
    assert ok is False
    assert "client_id" in err and "client_secret" in err


# ── catalog wiring sanity ────────────────────────────────────────────────────


def test_catalog_registers_oracle_ebs_r12() -> None:
    """The registry actually exposes the new connector."""
    from app.integrations import get_def, get_test_handler

    d = get_def("oracle_ebs_r12")
    assert d is not None
    assert d.implemented is True
    assert d.category == "ERP"
    handler = get_test_handler("oracle_ebs_r12")
    assert handler is oracle_test_connection

    keys = [f.key for f in d.fields]
    assert keys == [
        "base_url", "responsibility", "username", "password",
        "auth_mode", "client_id", "client_secret", "module",
    ]
    cred_keys = {f.key for f in d.fields if f.group == "credentials"}
    assert cred_keys == {"password", "client_secret"}

    select_fields = {f.key: (f.options, f.default) for f in d.fields if f.type == "select"}
    assert select_fields == {
        "auth_mode": (("basic", "oauth2"), "basic"),
        "module": (("gl", "ap", "ar", "inv", "po", "hrms", "none"), "none"),
    }
