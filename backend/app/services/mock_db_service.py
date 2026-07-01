"""
Mock data access layer for tool-calling.

Wraps SQLite queries so tool-calling logic (llm_service.py) never writes
raw SQL — swap this for a real DB client later without touching callers.
"""
import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "support.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_order(order_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM orders WHERE order_id = ? COLLATE NOCASE", (order_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def check_refund_eligibility(order_id: str) -> dict:
    order = get_order(order_id)
    if not order:
        return {"eligible": False, "reason": "Order not found."}
    if order["status"] != "Delivered":
        return {"eligible": False, "reason": f"Order status is '{order['status']}', not yet delivered."}
    delivered = date.fromisoformat(order["delivery_date"])
    days_since = (date.today() - delivered).days
    if days_since > order["refund_window_days"]:
        return {"eligible": False, "reason": f"Refund window ({order['refund_window_days']} days) has expired."}
    return {"eligible": True, "reason": f"Delivered {days_since} days ago, within refund window."}


def search_knowledge_base(query: str, limit: int = 3) -> list[dict]:
    conn = _connect()
    like = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT * FROM knowledge_base
        WHERE lower(title) LIKE ? OR lower(tags) LIKE ? OR lower(content) LIKE ?
        LIMIT ?
        """,
        (like, like, like, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_support_ticket(summary: str, priority: str, customer_email: str | None = None) -> dict:
    conn = _connect()
    count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    ticket_id = f"TCK-{1000 + count + 1}"
    conn.execute(
        "INSERT INTO tickets (ticket_id, summary, priority, customer_email, status) VALUES (?, ?, ?, ?, ?)",
        (ticket_id, summary, priority, customer_email, "Open"),
    )
    conn.commit()
    conn.close()
    return {"ticket_id": ticket_id, "summary": summary, "priority": priority, "customer_email": customer_email, "status": "Open"}