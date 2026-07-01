"""
In-memory conversation history store, keyed by conversation_id.

Simple dict-based store — resets when the server restarts. Swap for a
SQLite table (same pattern as mock_db_service.py) later if you need
history to survive restarts.
"""
from threading import Lock

# conversation_id -> list of {"role": "user"|"assistant", "content": str}
_conversations: dict[str, list[dict]] = {}
_lock = Lock()

MAX_TURNS_KEPT = 20  # cap history length so prompts don't grow unbounded


def get_history(conversation_id: str) -> list[dict]:
    with _lock:
        return list(_conversations.get(conversation_id, []))


def append_turn(conversation_id: str, role: str, content: str) -> None:
    with _lock:
        history = _conversations.setdefault(conversation_id, [])
        history.append({"role": role, "content": content})
        if len(history) > MAX_TURNS_KEPT:
            del history[: len(history) - MAX_TURNS_KEPT]


def clear_history(conversation_id: str) -> None:
    with _lock:
        _conversations.pop(conversation_id, None)