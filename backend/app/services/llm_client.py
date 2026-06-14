from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional, Protocol, runtime_checkable

from anthropic import Anthropic, APIError as AnthropicAPIError
from anthropic import AuthenticationError as AnthropicAuthenticationError
from groq import APIError as GroqAPIError
from groq import AuthenticationError as GroqAuthenticationError
from groq import Groq

from app.config import get_settings

FALLBACK_LABEL = "My logic is not listed here."
MCQ_KEYS = ("A", "B", "C", "D")
OPTION_MAX_WORDS = 20
GROQ_MAX_OUTPUT_TOKENS = 32768
ANTHROPIC_MAX_OUTPUT_TOKENS = 8192

LlmProvider = Literal["groq", "anthropic"]
VALID_LLM_PROVIDERS: tuple[LlmProvider, ...] = ("groq", "anthropic")


def extract_json(text: str) -> Any:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


class LlmAuthError(RuntimeError):
    pass


class GroqAuthError(LlmAuthError):
    pass


class AnthropicAuthError(LlmAuthError):
    pass


def normalize_llm_provider(value: str) -> LlmProvider:
    provider = value.strip().lower()
    if provider not in VALID_LLM_PROVIDERS:
        raise ValueError(f"llm_provider must be one of: {', '.join(VALID_LLM_PROVIDERS)}")
    return provider


@runtime_checkable
class LlmClient(Protocol):
    def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 8192,
    ) -> Any: ...


def _is_token_or_json_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "json_validate_failed",
            "max completion tokens",
            "max_tokens",
            "failed to generate json",
        )
    )


class GroqLlmClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = settings.groq_model

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 8192,
    ) -> Any:
        capped = min(max_tokens, GROQ_MAX_OUTPUT_TOKENS)
        attempts: list[tuple[int, bool]] = [
            (capped, True),
            (min(capped * 2, GROQ_MAX_OUTPUT_TOKENS), True),
            (min(capped * 2, GROQ_MAX_OUTPUT_TOKENS), False),
        ]
        last_error: Optional[Exception] = None

        for tokens, use_json_mode in attempts:
            try:
                content = self._request(
                    system, user, max_tokens=tokens, json_mode=use_json_mode
                )
                return extract_json(content)
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                continue
            except GroqAPIError as exc:
                if _is_token_or_json_error(exc):
                    last_error = exc
                    continue
                raise _wrap_groq_error(exc) from exc
            except Exception as exc:
                raise _wrap_groq_error(exc) from exc

        if last_error is not None:
            raise _wrap_groq_error(last_error)
        raise RuntimeError("Groq JSON generation failed after retries")

    def _request(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Groq returned an empty response")
        return content


class AnthropicLlmClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 8192,
    ) -> Any:
        capped = min(max_tokens, ANTHROPIC_MAX_OUTPUT_TOKENS)
        attempts = [capped, min(capped * 2, ANTHROPIC_MAX_OUTPUT_TOKENS)]
        last_error: Optional[Exception] = None
        json_system = system + "\n\nRespond with valid JSON only. No markdown fences."

        for tokens in attempts:
            try:
                content = self._request(json_system, user, max_tokens=tokens)
                return extract_json(content)
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                continue
            except AnthropicAPIError as exc:
                if _is_token_or_json_error(exc):
                    last_error = exc
                    continue
                raise _wrap_anthropic_error(exc) from exc
            except Exception as exc:
                raise _wrap_anthropic_error(exc) from exc

        if last_error is not None:
            raise _wrap_anthropic_error(last_error)
        raise RuntimeError("Anthropic JSON generation failed after retries")

    def _request(self, system: str, user: str, *, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [block.text for block in response.content if block.type == "text"]
        content = "".join(parts).strip()
        if not content:
            raise RuntimeError("Anthropic returned an empty response")
        return content


def _wrap_groq_error(exc: Exception) -> RuntimeError:
    if isinstance(exc, GroqAuthenticationError):
        return GroqAuthError(
            "Invalid GROQ_API_KEY. Check backend/.env and restart uvicorn."
        )
    if isinstance(exc, GroqAPIError):
        return RuntimeError(f"Groq API error: {exc}")
    return RuntimeError(str(exc))


def _wrap_anthropic_error(exc: Exception) -> RuntimeError:
    if isinstance(exc, AnthropicAuthenticationError):
        return AnthropicAuthError(
            "Invalid ANTHROPIC_API_KEY. Check backend/.env and restart uvicorn."
        )
    if isinstance(exc, AnthropicAPIError):
        return RuntimeError(f"Anthropic API error: {exc}")
    return RuntimeError(str(exc))


def wrap_groq_error(exc: Exception) -> RuntimeError:
    return _wrap_groq_error(exc)


def get_llm_client(provider: LlmProvider = "groq") -> LlmClient:
    if provider == "anthropic":
        return AnthropicLlmClient()
    return GroqLlmClient()
