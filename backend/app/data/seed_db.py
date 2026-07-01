"""
Run this once to create and seed support.db with synthetic data.
Usage: python -m app.data.seed_db   (run from backend/ folder)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "support.db"


def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS tickets;
    DROP TABLE IF EXISTS knowledge_base;

    CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        customer_email TEXT,
        product TEXT,
        status TEXT,
        order_date TEXT,
        delivery_date TEXT,
        amount REAL,
        refund_window_days INTEGER
    );

    CREATE TABLE tickets (
        ticket_id TEXT PRIMARY KEY,
        summary TEXT,
        priority TEXT,
        customer_email TEXT,
        status TEXT
    );

    CREATE TABLE knowledge_base (
        id TEXT PRIMARY KEY,
        title TEXT,
        tags TEXT,
        content TEXT
    );
    """)

    orders = [
        ("ORD-1001", "alice@example.com", "Wireless Mouse", "Delivered", "2026-06-10", "2026-06-14", 29.99, 30),
        ("ORD-1002", "bob@example.com", "Mechanical Keyboard", "In Transit", "2026-06-25", None, 89.99, 30),
        ("ORD-1003", "carla@example.com", "USB-C Hub", "Delivered", "2026-04-01", "2026-04-05", 19.99, 30),
        ("ORD-1004", "dave@example.com", "Noise Cancelling Headphones", "Cancelled", "2026-06-28", None, 149.99, 30),
    ]
    cur.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)", orders
    )

    kb = [
        ("kb-001", "How to reset your password", "account,password,login",
         "Go to Settings > Security > Reset Password. A reset link is emailed within 5 minutes."),
        ("kb-002", "Refund policy", "refund,billing,policy",
         "Refunds are available within 30 days of delivery for unused items in original packaging."),
        ("kb-003", "Why is my order delayed", "shipping,delivery,order",
         "Delays are usually carrier-side. Orders 'In Transit' for more than 7 business days should be escalated."),
        ("kb-004", "How to update billing information", "billing,payment,account",
         "Go to Settings > Billing > Payment Methods to add or update a card."),
    ]
    cur.executemany(
        "INSERT INTO knowledge_base VALUES (?, ?, ?, ?)", kb
    )

    conn.commit()
    conn.close()
    print(f"Seeded database at {DB_PATH}")


if __name__ == "__main__":
    seed()