"""Shared AI engine for agents.

All agents import `get_ai_engine()` and call one of:
  - complete(system, user)        — plain text completion
  - extract(system, user, tool)   — tool-forced structured extraction
  - parallel_complete(pairs)      — N completions in parallel

Model and provider are resolved from env (DEFAULT_MODEL, AZURE_OPENAI_*).
Swap models with one env change.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from app.core.config import settings


class _Backend(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, *, max_tokens: int) -> str: ...

    @abstractmethod
    async def extract(
        self,
        system: str,
        user: str,
        tool_name: str,
        tool_description: str,
        tool_schema: dict,
        *,
        max_tokens: int,
    ) -> dict: ...


class _AzureOpenAIBackend(_Backend):
    def __init__(self, deployment: str):
        from openai import AsyncAzureOpenAI

        self._client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        self._deployment = deployment

    async def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    async def extract(
        self,
        system: str,
        user: str,
        tool_name: str,
        tool_description: str,
        tool_schema: dict,
        *,
        max_tokens: int,
    ) -> dict:
        tool = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_description,
                "parameters": tool_schema,
            },
        }
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": tool_name}},
        )
        choice = resp.choices[0]
        if not choice.message.tool_calls:
            return {}
        for tc in choice.message.tool_calls:
            if tc.function.name == tool_name:
                try:
                    return json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    return {}
        return {}


class AIEngine:
    """Facade used by agents."""

    def __init__(self, backend: _Backend, model_id: str):
        self._backend = backend
        self.model_id = model_id

    async def complete(self, system: str, user: str, *, max_tokens: int = 1000) -> str:
        return await self._backend.complete(system, user, max_tokens=max_tokens)

    async def extract(
        self,
        system: str,
        user: str,
        *,
        tool_name: str,
        tool_description: str,
        tool_schema: dict,
        max_tokens: int = 4000,
    ) -> dict:
        return await self._backend.extract(
            system,
            user,
            tool_name,
            tool_description,
            tool_schema,
            max_tokens=max_tokens,
        )

    async def parallel_complete(
        self,
        pairs: list[tuple[str, str]],
        *,
        max_tokens: int = 1000,
    ) -> list[str | Exception]:
        """Run N (system, user) completions concurrently. Exceptions are returned, not raised."""
        tasks = [self.complete(s, u, max_tokens=max_tokens) for s, u in pairs]
        return await asyncio.gather(*tasks, return_exceptions=True)


def _build_engine() -> AIEngine:
    model_id = settings.default_model
    if model_id.startswith("azure-"):
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            raise RuntimeError(
                "Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY in .env."
            )
        backend = _AzureOpenAIBackend(settings.azure_openai_deployment)
        return AIEngine(backend, model_id)
    raise ValueError(f"Unknown DEFAULT_MODEL: {model_id!r} (supported: azure-*)")


@lru_cache(maxsize=1)
def get_ai_engine() -> AIEngine:
    return _build_engine()
