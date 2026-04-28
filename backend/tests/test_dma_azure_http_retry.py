"""Unit tests for the DMA Azure-OpenAI retry wrapper.

The wrapper exists because the DMA services (classification, dedup, …)
talk to Azure OpenAI via raw httpx and used to surface transient 500s
to the user as ``"AI call failed (Server error '500 Internal Server
Error' for url '…')"``. We now retry 429/5xx and connection-level
flakes with exponential backoff before giving up.

These tests use a stub `_FakeAsyncClient` injected via the helper's
``client_factory`` seam, so nothing touches the network or env. The
fake stays minimal — it queues responses (or raises an exception) per
``post()`` call so each test can script the exact retry pattern it's
verifying.
"""

from __future__ import annotations

import asyncio
from typing import Iterable

import httpx
import pytest

from app.dma.services import _azure_http
from app.dma.services._azure_http import post_chat_completion


# ── env defaults so _azure_cfg() doesn't reject the request ──────────────────


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Make config look valid for every test by default. Tests that
    care about missing config can override individually."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")


# ── stub client ──────────────────────────────────────────────────────────────


class _FakeResponse:
    """Mimics enough of httpx.Response for the helper's needs."""

    def __init__(self, status: int, body: dict | None = None):
        self.status_code = status
        self._body = body or {"ok": True}
        self.request = httpx.Request("POST", "https://fake/")

    def json(self):
        return self._body

    def raise_for_status(self):
        if 400 <= self.status_code:
            raise httpx.HTTPStatusError(
                f"Server error '{self.status_code}' for url '{self.request.url}'",
                request=self.request,
                response=self,  # type: ignore[arg-type]
            )


class _FakeAsyncClient:
    """Drop-in for httpx.AsyncClient that pops a scripted response (or
    raises) per .post() call. Tracks every call so tests can assert on
    the retry count + URL/headers/body."""

    def __init__(self, scripted: list):
        # Each item is either a `_FakeResponse` (returned) or an
        # exception instance (raised).
        # Note: we take the list **by reference** so that the helper's
        # multiple AsyncClient context-manager instances (one per retry
        # attempt) share a single queue of scripted responses. Copying
        # would make every retry re-see the first failure forever.
        self._scripted = scripted
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if not self._scripted:
            raise AssertionError("FakeAsyncClient: no more scripted responses queued")
        nxt = self._scripted.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


def _factory(scripted: Iterable):
    """Build a client_factory that hands out one stub per post-loop iteration."""
    scripted = list(scripted)
    instances: list[_FakeAsyncClient] = []

    def make():
        # The helper opens a fresh AsyncClient per attempt (so the
        # context manager closes between retries). We mirror that
        # by creating a new fake each call, but they all share the
        # same scripted queue — the helper still sees one response
        # per attempt regardless.
        c = _FakeAsyncClient(scripted)
        instances.append(c)
        return c

    return make, instances


async def _no_sleep(_secs: float):
    """Test seam: skip backoff so retry tests stay sub-millisecond."""
    return None


def _run(coro):
    return asyncio.run(coro)


# ── happy paths ──────────────────────────────────────────────────────────────


def test_first_attempt_2xx_returns_parsed_json_no_retry():
    factory, instances = _factory([_FakeResponse(200, {"choices": [{"message": {"content": "hi"}}]})])

    result = _run(post_chat_completion(
        {"messages": [{"role": "user", "content": "x"}], "max_tokens": 8},
        client_factory=factory, sleep=_no_sleep,
    ))

    assert result == {"choices": [{"message": {"content": "hi"}}]}
    # Exactly one HTTP call — no retry.
    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 1


def test_500_then_200_retries_and_succeeds():
    factory, instances = _factory([
        _FakeResponse(500),
        _FakeResponse(200, {"ok": "after-retry"}),
    ])

    result = _run(post_chat_completion({"foo": "bar"}, client_factory=factory, sleep=_no_sleep))

    assert result == {"ok": "after-retry"}
    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 2  # one failure + one success


def test_429_throttle_is_retried():
    factory, instances = _factory([
        _FakeResponse(429),
        _FakeResponse(200, {"ok": True}),
    ])

    _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep))

    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 2


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_all_5xx_retried(status):
    factory, instances = _factory([
        _FakeResponse(status),
        _FakeResponse(200, {"ok": True}),
    ])

    _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep))

    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 2


def test_connect_error_is_retried():
    """Network-layer flakes (Azure POP brief outage) retry too."""
    factory, instances = _factory([
        httpx.ConnectError("connection refused"),
        _FakeResponse(200, {"ok": True}),
    ])

    _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep))

    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 2


def test_read_timeout_is_retried():
    factory, instances = _factory([
        httpx.ReadTimeout("read timed out"),
        _FakeResponse(200, {"ok": True}),
    ])

    _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep))

    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 2


# ── failure paths ────────────────────────────────────────────────────────────


def test_persistent_500_exhausts_retries_and_raises():
    """4 attempts with max_retries=3 — same shape as production."""
    factory, instances = _factory([_FakeResponse(500)] * 4)

    with pytest.raises(httpx.HTTPStatusError) as exc:
        _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep, max_retries=3))

    # The original error string format is preserved so the existing
    # caller `except Exception as e: ... f"AI call failed ({e})"`
    # continues to read the same way it always has.
    assert "500" in str(exc.value)
    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 4  # 1 initial + 3 retries


def test_400_bad_request_is_NOT_retried():
    """4xx (not 429) means our request is wrong; retrying won't help
    and would just slow the user down."""
    factory, instances = _factory([_FakeResponse(400)])

    with pytest.raises(httpx.HTTPStatusError):
        _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep))

    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 1


def test_401_unauth_is_NOT_retried():
    factory, instances = _factory([_FakeResponse(401)])

    with pytest.raises(httpx.HTTPStatusError):
        _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep))

    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 1


def test_persistent_connect_error_raises_after_retries():
    factory, instances = _factory([httpx.ConnectError("nope")] * 4)

    with pytest.raises(httpx.ConnectError):
        _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep, max_retries=3))

    total_calls = sum(len(c.calls) for c in instances)
    assert total_calls == 4


def test_missing_config_raises_runtimeerror(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

    with pytest.raises(RuntimeError) as exc:
        _run(post_chat_completion({"x": 1}, sleep=_no_sleep))

    assert "AZURE_OPENAI_ENDPOINT" in str(exc.value)


# ── backoff ──────────────────────────────────────────────────────────────────


def test_backoff_grows_exponentially_between_attempts():
    """Sleeps should be ~1s, ~2s, ~4s — jittered upward by 0–1s. Verifies
    the thundering-herd guard is actually wired up (not "sleep(0)" by
    accident)."""
    factory, _ = _factory([_FakeResponse(500)] * 4)
    sleeps: list[float] = []

    async def record_sleep(s: float):
        sleeps.append(s)

    with pytest.raises(httpx.HTTPStatusError):
        _run(post_chat_completion(
            {"x": 1}, client_factory=factory, sleep=record_sleep, max_retries=3,
        ))

    # 3 sleeps total — between attempts 1→2, 2→3, 3→4.
    assert len(sleeps) == 3
    # Lower bound: 2**attempt; upper bound: 2**attempt + 1 (jitter).
    assert 1.0 <= sleeps[0] < 2.0
    assert 2.0 <= sleeps[1] < 3.0
    assert 4.0 <= sleeps[2] < 5.0


def test_no_sleep_when_max_retries_zero():
    factory, _ = _factory([_FakeResponse(500)])
    sleeps: list[float] = []

    async def record_sleep(s):
        sleeps.append(s)

    with pytest.raises(httpx.HTTPStatusError):
        _run(post_chat_completion(
            {"x": 1}, client_factory=factory, sleep=record_sleep, max_retries=0,
        ))

    assert sleeps == []


# ── request shape ────────────────────────────────────────────────────────────


def test_request_url_built_from_env():
    factory, instances = _factory([_FakeResponse(200, {"ok": True})])

    _run(post_chat_completion({"x": 1}, client_factory=factory, sleep=_no_sleep))

    call = instances[0].calls[0]
    assert call["url"] == (
        "https://example.openai.azure.com/openai/deployments/gpt-4o"
        "/chat/completions?api-version=2024-02-15-preview"
    )
    assert call["headers"]["api-key"] == "k"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["json"] == {"x": 1}
