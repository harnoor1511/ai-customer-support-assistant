"""
LLM service layer.

This module isolates all LLM-provider plumbing (HTTP calls, auth, request
shaping) behind a single `LLMClient` interface. Business logic (support
triage) never talks to OpenRouter/Gemini directly — it calls
`generate_structured_json()`.
"""
from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM call fails or returns unusable output."""

    def __init__(self, message: str, *, status_code: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429


class LLMClient(ABC):
    """Common interface every LLM provider must implement."""

    @abstractmethod
    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
        tool_executor=None,
    ) -> dict[str, Any]:
        """Call the LLM and return a parsed JSON dict matching json_schema.

        If `tools` is provided, the provider may use function-calling and
        will invoke `tool_executor(name, args)` to resolve tool calls
        before producing a final answer. Providers that don't support
        tool-calling may simply ignore these params and answer directly.
        """
        raise NotImplementedError


class OpenRouterClient(LLMClient):
    def __init__(self, settings: Settings):
        self._settings = settings

    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
        tool_executor=None,
    ) -> dict[str, Any]:
        # NOTE: tool-calling is not wired for OpenRouter yet. It is used as
        # a fallback provider, so it simply answers directly without tools
        # rather than hard-failing — an acceptable degraded fallback.
        if not self._settings.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY is not configured on the server.")

        url = f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_schema", "json_schema": json_schema},
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise LLMError(
                    f"OpenRouter API error: {exc.response.status_code} {exc.response.text}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError(f"OpenRouter request failed: {exc}") from exc

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected OpenRouter response shape: {data}") from exc

        return _parse_json_content(content)


class GeminiClient(LLMClient):
    """
    Gemini client with:
      - automatic multi-key rotation on 429 rate limits
      - an agentic tool-calling loop (get_order, check_refund_eligibility, etc.)

    Flow when `tools` is provided:
      1. Call Gemini with tool declarations attached (no responseSchema —
         Gemini doesn't allow schema mode + function calling together).
      2. If Gemini asks to call a tool, run it via `tool_executor` and feed
         the result back into the conversation, then loop.
      3. Once Gemini stops requesting tools, make one final call with tools
         removed and responseSchema enforced, so we always end with strict
         JSON regardless of how much tool use happened.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._keys = settings.gemini_api_keys

    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
        tool_executor=None,
        max_tool_iterations: int = 4,
    ) -> dict[str, Any]:
        if not self._keys:
            raise LLMError("No GEMINI_API_KEY(s) configured on the server.")

        last_error: LLMError | None = None

        for idx, key in enumerate(self._keys):
            try:
                return await self._run_with_key(
                    key, system_prompt, user_prompt, json_schema, tools, tool_executor, max_tool_iterations
                )
            except LLMError as exc:
                last_error = exc
                if exc.is_rate_limited:
                    logger.warning(
                        "Gemini key #%d rate limited (429); trying next key. retry_after=%s",
                        idx + 1,
                        exc.retry_after,
                    )
                    if idx == len(self._keys) - 1 and exc.retry_after:
                        await asyncio.sleep(min(exc.retry_after, 10))
                    continue
                logger.warning("Gemini key #%d failed (non-429): %s", idx + 1, exc)
                continue

        raise LLMError(
            f"All {len(self._keys)} Gemini key(s) failed. Last error: {last_error}",
            status_code=getattr(last_error, "status_code", None),
        )

    async def _run_with_key(
        self,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        tools: list[dict[str, Any]] | None,
        tool_executor,
        max_tool_iterations: int,
    ) -> dict[str, Any]:
        """Runs the full tool-calling loop (if tools given) using one API key."""
        contents = [{"role": "user", "parts": [{"text": user_prompt}]}]

        for _ in range(max_tool_iterations):
            payload: dict[str, Any] = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.3},
            }

            if tools:
                payload["tools"] = [{"functionDeclarations": tools}]
            else:
                payload["generationConfig"]["responseMimeType"] = "application/json"
                payload["generationConfig"]["responseSchema"] = _to_gemini_schema(json_schema["schema"])

            data = await self._post(api_key, payload)

            try:
                candidate_parts = data["candidates"][0]["content"]["parts"]
            except (KeyError, IndexError) as exc:
                raise LLMError(f"Unexpected Gemini response shape: {data}") from exc

            function_call_part = next((p for p in candidate_parts if "functionCall" in p), None)

            if function_call_part and tool_executor:
                fn_name = function_call_part["functionCall"]["name"]
                fn_args = function_call_part["functionCall"].get("args", {})

                logger.info("Gemini requested tool call: %s(%s)", fn_name, fn_args)
                try:
                    tool_result = tool_executor(fn_name, fn_args)
                except Exception as exc:  # noqa: BLE001
                    tool_result = {"error": str(exc)}

                contents.append({"role": "model", "parts": [function_call_part]})
                contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": fn_name,
                            "response": {"result": tool_result},
                        }
                    }],
                })
                continue

            text_part = next((p.get("text") for p in candidate_parts if "text" in p), None)

            if tools:
                # Tools were on this call; ask once more with tools off and
                # schema on, so we always return strict JSON.
                contents.append({"role": "model", "parts": candidate_parts})
                contents.append({
                    "role": "user",
                    "parts": [{
                        "text": "Now respond with ONLY the final structured JSON object as instructed, "
                        "using the information gathered above."
                    }],
                })
                return await self._final_json_call(api_key, system_prompt, contents, json_schema)

            if text_part is None:
                raise LLMError(f"Gemini returned no text or function call: {data}")
            return _parse_json_content(text_part)

        raise LLMError("Exceeded max tool-call iterations without a final answer.")

    async def _final_json_call(
        self, api_key: str, system_prompt: str, contents: list[dict], json_schema: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
                "responseSchema": _to_gemini_schema(json_schema["schema"]),
            },
        }
        data = await self._post(api_key, payload)
        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected Gemini response shape: {data}") from exc
        return _parse_json_content(content)

    async def _post(self, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = (
            f"{self._settings.gemini_base_url.rstrip('/')}/models/"
            f"{self._settings.gemini_model}:generateContent?key={api_key}"
        )
        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                retry_after = _extract_retry_after(exc.response)
                raise LLMError(
                    f"Gemini API error: {exc.response.status_code} {exc.response.text}",
                    status_code=exc.response.status_code,
                    retry_after=retry_after,
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError(f"Gemini request failed: {exc}") from exc
        return resp.json()


def _extract_retry_after(response: httpx.Response) -> float | None:
    """Pull a retry delay from Gemini's 429 response, checking the
    Retry-After header first, then the RetryInfo detail Gemini sometimes
    embeds in the JSON error body.
    """
    header_val = response.headers.get("Retry-After")
    if header_val:
        try:
            return float(header_val)
        except ValueError:
            pass
    try:
        body = response.json()
        details = body.get("error", {}).get("details", [])
        for detail in details:
            if detail.get("@type", "").endswith("RetryInfo"):
                delay = detail.get("retryDelay", "")  # e.g. "23s"
                if delay.endswith("s"):
                    return float(delay[:-1])
    except (ValueError, AttributeError, KeyError):
        pass
    return None


def _parse_json_content(content: str) -> dict[str, Any]:
    """Defensively parse JSON text, stripping stray code fences if present."""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM did not return valid JSON: {content}") from exc


def _to_gemini_schema(openai_style_schema: dict[str, Any]) -> dict[str, Any]:
    """Gemini's responseSchema format is close to JSON Schema; strip fields it rejects."""
    schema = json.loads(json.dumps(openai_style_schema))  # deep copy
    schema.pop("additionalProperties", None)
    return schema


class FallbackChainClient(LLMClient):
    """
    Wraps a primary client (Gemini) with a secondary client (OpenRouter).
    If the primary exhausts all its keys/retries, we fall through to the
    secondary provider before ever resorting to the service-layer's static
    safe-fallback response.
    """

    def __init__(self, primary: LLMClient, secondary: LLMClient | None):
        self._primary = primary
        self._secondary = secondary

    async def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
        tool_executor=None,
    ) -> dict[str, Any]:
        try:
            return await self._primary.generate_structured_json(
                system_prompt, user_prompt, json_schema, tools=tools, tool_executor=tool_executor
            )
        except LLMError as primary_exc:
            if self._secondary is None:
                raise
            logger.warning("Primary LLM provider failed, falling back to OpenRouter: %s", primary_exc)
            try:
                # Secondary (OpenRouter) doesn't support tools yet — it will
                # just answer without them, which is an acceptable degraded
                # fallback rather than a hard failure.
                return await self._secondary.generate_structured_json(system_prompt, user_prompt, json_schema)
            except LLMError as secondary_exc:
                raise LLMError(
                    f"Primary and fallback providers both failed. "
                    f"Primary: {primary_exc}. Fallback: {secondary_exc}"
                ) from secondary_exc


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """Factory returning the configured LLM provider client.

    When llm_provider == "gemini" and an OpenRouter key is also configured,
    wraps Gemini (with its own key rotation + tool-calling) in a
    FallbackChainClient so a total Gemini outage/quota exhaustion falls
    through to OpenRouter automatically.
    """
    settings = settings or get_settings()
    if settings.llm_provider == "gemini":
        gemini_client = GeminiClient(settings)
        if settings.openrouter_api_key:
            return FallbackChainClient(gemini_client, OpenRouterClient(settings))
        return gemini_client
    return OpenRouterClient(settings)