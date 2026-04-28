"""Azure OpenAI HTTP client with retry-on-transient-failure.

The DMA agent services (classification, dedup, etc.) talk to Azure OpenAI
directly via raw httpx — separately from the `openai` SDK that
`app.core.ai_engine.AIEngine` uses — because they need to do JSON-from-
content extraction the SDK doesn't expose cleanly. The downside of the
raw httpx path is that the SDK's built-in retry policy (2 retries on
429/5xx) doesn't cover us. Without the helper here, transient Azure
500/503/rate-limit responses surface as hard failures to the user
(e.g. ``AI call failed (Server error '500 Internal Server Error' for
url '…/chat/completions…')``) even though a sub-second retry would
typically succeed — Azure deployments routinely emit one-off 500s under
modest load.

`post_chat_completion` is a thin wrapper that:

  * resolves the Azure deployment URL from env (de-duplicating the
    config lookup the services were each doing locally)
  * POSTs the chat-completion payload
  * retries on 429 / 5xx and on connection / read-timeout errors, with
    exponential backoff plus jitter
  * raises ``httpx.HTTPStatusError`` (or the underlying network error)
    only after retries are exhausted, so the caller's existing
    try/except fallback (e.g. "default to match", majority vote) only
    fires for genuinely persistent failures rather than the transient
    blips that prompted this module.

Callers keep their own try/except — that fallback behavior is
intentional UX, not a bug.
"""

from __future__ import annotations

import asyncio
import os
import random
from typing import Any, Awaitable, Callable

import httpx


# 429 = throttled, 500/502/503/504 = server-side errors. Azure routinely
# emits these for transient capacity issues; all are retryable.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Network-layer failures we treat as transient. We deliberately do NOT
# retry on httpx.HTTPStatusError (that's a non-2xx the server returned)
# or httpx.RequestError subclasses we don't list — e.g. a TLS handshake
# error or InvalidURL is a config bug, not a flake.
_RETRYABLE_EXC: tuple[type[Exception], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)


def _azure_cfg() -> tuple[str, str, str, str]:
    """Read Azure OpenAI config from env. Centralizes the lookup that
    was previously copy-pasted across DMA services (each maintaining
    its own ``_azure_cfg`` / inlined ``os.getenv`` calls)."""
    ep = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    key = os.getenv("AZURE_OPENAI_API_KEY", "")
    model = os.getenv("AZURE_OPENAI_MODEL", "")
    ver = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    return ep, key, model, ver


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with full jitter — ~1–2s, ~2–3s, ~4–5s …
    Jitter avoids the thundering herd when a parallel batch of N
    coroutines all hit a 500 simultaneously and would otherwise retry
    in lockstep."""
    return (2 ** attempt) + random.random()


async def post_chat_completion(
    payload: dict,
    *,
    timeout: float = 60.0,
    max_retries: int = 3,
    # Test seams — production callers shouldn't pass these. Injecting
    # `sleep` lets tests run instantly without real backoff delays;
    # injecting `client_factory` lets tests stub httpx wholesale.
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    client_factory: Callable[[], Any] | None = None,
) -> dict:
    """POST a chat-completion to Azure OpenAI with retry-on-transient.

    Returns the parsed JSON body of a 2xx response.

    Raises ``httpx.HTTPStatusError`` for non-retryable HTTP errors (4xx
    other than 429) immediately, and for retryable HTTP errors only
    after ``max_retries`` retries have been exhausted. Raises one of
    the retryable network exceptions (ConnectError, ReadTimeout, etc.)
    when those persist past the retry budget.
    """

    ep, key, model, ver = _azure_cfg()
    if not ep or not key or not model:
        raise RuntimeError(
            "Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT, "
            "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_MODEL in .env."
        )
    url = f"{ep}/openai/deployments/{model}/chat/completions?api-version={ver}"
    headers = {"Content-Type": "application/json", "api-key": key}

    factory = client_factory or (lambda: httpx.AsyncClient(timeout=timeout))

    # Loop runs `max_retries + 1` times — one initial attempt plus
    # `max_retries` retries. We only `continue` (i.e. retry) when both
    # the failure is retryable AND we have retries left; otherwise we
    # fall through to raise (or return on success).
    for attempt in range(max_retries + 1):
        try:
            async with factory() as client:
                resp = await client.post(url, headers=headers, json=payload)
        except _RETRYABLE_EXC:
            if attempt < max_retries:
                await sleep(_backoff_seconds(attempt))
                continue
            raise

        if resp.status_code in _RETRYABLE_STATUS and attempt < max_retries:
            await sleep(_backoff_seconds(attempt))
            continue

        # Either 2xx (return), non-retryable 4xx (raise immediately),
        # or retryable 5xx with retries exhausted (raise the original
        # error so the caller's try/except sees the same exception
        # type/string they always have).
        resp.raise_for_status()
        return resp.json()

    # Defensive: the loop above always either returns or raises on
    # the final iteration. This line keeps type checkers happy.
    raise RuntimeError("post_chat_completion: retry loop exited without return/raise")
