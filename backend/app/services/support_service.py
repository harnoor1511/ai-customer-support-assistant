"""
Support triage business logic.

Orchestrates prompt building, LLM invocation, guardrails, and response
validation. Kept separate from the API layer (routes) and from LLM
plumbing (llm_service) so each concern can evolve independently — e.g.
adding retrieval (RAG) or conversation history later only touches this
file.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

from pydantic import ValidationError

from app.prompts.support_prompt import (
    SUPPORT_JSON_SCHEMA,
    SUPPORT_SYSTEM_PROMPT,
    build_user_prompt,
)
from app.schemas.support import (
    BatchMessageItem,
    BatchResultItem,
    BatchSupportResponse,
    Category,
    Priority,
    Sentiment,
    SupportRequest,
    SupportResponse,
)
from app.services.conversation_store import append_turn, get_history
from app.services.llm_service import LLMClient, LLMError
from app.tools.support_tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger(__name__)

# Deterministic guardrails, enforced in code regardless of what the LLM says.
LOW_CONFIDENCE_THRESHOLD = 0.6
ALWAYS_ESCALATE_PRIORITIES = {Priority.P0, Priority.P1}

_INJECTION_PATTERN = re.compile(
    r"\b(prompt injection|manipulat(e|ion) attempt|ignore (previous|prior) instructions|"
    r"attempted to (hijack|override|extract))\b",
    re.IGNORECASE,
)
_AMBIGUOUS_PATTERN = re.compile(
    r"\b(ambiguous|insufficient information|unclear|not enough (info|detail))\b",
    re.IGNORECASE,
)
_EXPLICIT_HUMAN_PATTERN = re.compile(
    r"\b(requires? human|needs? human|escalate to (a )?human|human (agent|review|intervention)|"
    r"manual review|cannot be resolved automatically)\b",
    re.IGNORECASE,
)

# Batch calls run concurrently but capped, to stay under provider rate
# limits and avoid hammering a free-tier LLM API.
MAX_CONCURRENT_LLM_CALLS = 5
MAX_RETRIES_PER_MESSAGE = 2


class SupportServiceError(Exception):
    """Raised when the support service cannot produce a valid response."""


class SupportService:
    def __init__(self, llm_client: LLMClient):
        self._llm_client = llm_client
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

    async def triage_message(self, request: SupportRequest) -> SupportResponse:
        conversation_id = request.conversation_id
        history = get_history(conversation_id) if conversation_id else None

        response = await self._call_llm_with_retry(request.message, history=history)
        response = self._apply_guardrails(response)

        if conversation_id:
            append_turn(conversation_id, "user", request.message)
            append_turn(conversation_id, "assistant", response.reply)

        return response

    async def triage_batch(self, items: list[BatchMessageItem]) -> BatchSupportResponse:
        """Triage many messages concurrently. Never raises — every item gets
        either a real result or a safe fallback, so one bad message never
        takes down the batch.
        """
        tasks = [self._triage_batch_item(item) for item in items]
        results = await asyncio.gather(*tasks)

        succeeded = sum(1 for r in results if r.error is None)
        failed = len(results) - succeeded
        needs_human_count = sum(1 for r in results if r.result and r.result.needs_human)
        total_latency = sum(r.latency_ms or 0 for r in results)

        return BatchSupportResponse(
            results=results,
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            needs_human_count=needs_human_count,
            total_latency_ms=total_latency,
            avg_latency_ms=round(total_latency / len(results), 1) if results else 0.0,
        )

    async def _triage_batch_item(self, item: BatchMessageItem) -> BatchResultItem:
        start = time.perf_counter()
        async with self._semaphore:
            try:
                if not item.message or not item.message.strip():
                    raise SupportServiceError("Empty message")

                response = await self._call_llm_with_retry(item.message)
                response = self._apply_guardrails(response)
                latency_ms = int((time.perf_counter() - start) * 1000)
                return BatchResultItem(
                    id=item.id,
                    message=item.message,
                    result=response,
                    error=None,
                    latency_ms=latency_ms,
                )
            except Exception as exc:  # noqa: BLE001 — batch rows must never raise
                logger.error("Batch item %s failed: %s", item.id, exc)
                latency_ms = int((time.perf_counter() - start) * 1000)
                return BatchResultItem(
                    id=item.id,
                    message=item.message,
                    result=_fallback_response(str(exc)),
                    error=str(exc),
                    latency_ms=latency_ms,
                )

    async def _call_llm_with_retry(self, message: str, history: list[dict] | None = None) -> SupportResponse:
        user_prompt = build_user_prompt(message, history=history)
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES_PER_MESSAGE + 1):
            try:
                raw = await self._llm_client.generate_structured_json(
                    system_prompt=SUPPORT_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    json_schema=SUPPORT_JSON_SCHEMA,
                    tools=TOOL_SCHEMAS,
                    tool_executor=execute_tool,
                )
                return SupportResponse.model_validate(raw)
            except LLMError as exc:
                last_error = exc
                logger.warning("LLM call attempt %d/%d failed: %s", attempt, MAX_RETRIES_PER_MESSAGE, exc)
            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "LLM output failed schema validation on attempt %d/%d: %s",
                    attempt,
                    MAX_RETRIES_PER_MESSAGE,
                    exc,
                )
            if attempt < MAX_RETRIES_PER_MESSAGE:
                await asyncio.sleep(0.5 * attempt)

        raise SupportServiceError(f"LLM call failed after {MAX_RETRIES_PER_MESSAGE} attempts: {last_error}")

    @staticmethod
    def _apply_guardrails(response: SupportResponse) -> SupportResponse:
        """
        Deterministic, independently-computed needs_human.

        We do NOT simply trust the model's raw needs_human boolean — models
        tend to over-flag "to be safe," which is what caused almost every
        message to be marked needs_human=true. Instead we recompute it from
        concrete signals and force the field to match, regardless of what
        the model returned.

        needs_human is True only when:
          - confidence is low, OR
          - priority is P0/P1 (critical), OR
          - summary/suggested_action indicates a prompt-injection attempt, OR
          - summary/suggested_action indicates genuine ambiguity/insufficient info, OR
          - the model explicitly stated human review/intervention is required
        Everything else is forced to False.
        """
        text_to_scan = f"{response.summary} {response.suggested_action}"

        is_low_confidence = response.confidence < LOW_CONFIDENCE_THRESHOLD
        is_critical_priority = response.priority in ALWAYS_ESCALATE_PRIORITIES
        is_injection_attempt = bool(_INJECTION_PATTERN.search(text_to_scan))
        is_ambiguous = bool(_AMBIGUOUS_PATTERN.search(text_to_scan))
        model_explicitly_flagged = bool(_EXPLICIT_HUMAN_PATTERN.search(text_to_scan))

        computed_needs_human = (
            is_low_confidence
            or is_critical_priority
            or is_injection_attempt
            or is_ambiguous
            or model_explicitly_flagged
        )

        if computed_needs_human != response.needs_human:
            response = response.model_copy(update={"needs_human": computed_needs_human})
        return response


def _fallback_response(reason: str) -> SupportResponse:
    """Safe, non-committal response used when the LLM call/validation fails
    entirely. Always routes to a human rather than guessing.
    """
    return SupportResponse(
        reply=(
            "Thanks for reaching out. We're routing your message to a member of "
            "our support team who will follow up shortly."
        ),
        category=Category.OTHER,
        priority=Priority.P2,
        summary=f"Automated triage failed to process this message ({reason}); needs manual review.",
        suggested_action="Manually triage this message.",
        needs_human=True,
        confidence=0.0,
        sentiment=Sentiment.NEUTRAL,
    )