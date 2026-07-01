"""
Pydantic schemas for the support-assistant domain.

These are the single source of truth for request/response shapes and
for validating the LLM's structured output before it ever reaches the
client.
"""
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    BILLING = "Billing"
    TECHNICAL_ISSUE = "Technical Issue"
    REFUND = "Refund"
    ACCOUNT = "Account"
    FEATURE_REQUEST = "Feature Request"
    COMPLAINT = "Complaint"
    GENERAL_QUESTION = "General Question"
    OTHER = "Other"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Sentiment(str, Enum):
    """
    Internal-only signal for agents/analytics. Not intended to be shown
    to the customer directly in the chat widget.
    """
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"
    FRUSTRATED = "Frustrated"


class SupportRequest(BaseModel):
    """Incoming customer message from the frontend."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="Raw, possibly messy customer message.",
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty or whitespace-only")
        return v
    # Optional fields reserved for future extensibility (history, user id, etc.)
    conversation_id: str | None = Field(
        default=None, description="Reserved for future conversation-history support."
    )
    user_id: str | None = Field(
        default=None, description="Reserved for future user-preference/personalization support."
    )


class SupportResponse(BaseModel):
    """Structured, validated response returned to the frontend."""

    reply: str = Field(..., description="Customer-facing, professional and empathetic reply.")
    category: Category = Field(..., description="Issue classification.")
    priority: Priority = Field(..., description="Ticket urgency, P0 (critical) to P3 (low).")
    summary: str = Field(..., description="Concise 1-2 sentence internal summary for agents.")
    suggested_action: str = Field(..., description="Recommended next action for support team.")
    needs_human: bool = Field(..., description="Whether this should be escalated to a human.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence, 0 to 1.")
    sentiment: Sentiment = Field(
        ..., description="Internal sentiment signal, not shown to customer."
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 2)


class BatchMessageItem(BaseModel):
    """A single row of a batch triage request."""

    id: str = Field(..., description="Caller-supplied identifier for this message (e.g. row number).")
    message: str = Field(..., max_length=8000, description="Raw customer message.")


class BatchSupportRequest(BaseModel):
    """Batch of customer messages to triage in one call."""

    messages: list[BatchMessageItem] = Field(
        ..., min_length=1, max_length=200, description="Messages to triage, max 200 per request."
    )


class BatchResultItem(BaseModel):
    """One row of batch output: the original id plus either a result or an error."""

    id: str
    message: str
    result: SupportResponse | None = None
    error: str | None = Field(
        default=None, description="Set if this row failed to process; result will be a safe fallback."
    )
    latency_ms: int | None = Field(default=None, description="Wall-clock time for this item's LLM call.")


class BatchSupportResponse(BaseModel):
    """Full batch response with per-item results and aggregate stats."""

    results: list[BatchResultItem]
    total: int
    succeeded: int
    failed: int
    needs_human_count: int
    total_latency_ms: int
    avg_latency_ms: float