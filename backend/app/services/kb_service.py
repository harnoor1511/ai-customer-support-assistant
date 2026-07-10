"""
Semantic search over the FAQ knowledge base (faq_kb table).

Loads every KB question's precomputed embedding into memory once (KB
size here is small — tens of rows — so this is fast and needs no
vector DB / extra infra), then answers queries with plain in-memory
cosine similarity.

Populate faq_kb first via: python -m app.data.faq_seed
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.utils.embeddings import embed_text

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "support.db"


@dataclass(frozen=True)
class KBEntry:
    id: int
    product: str
    section: str
    question: str
    answer: str


class KBService:
    """Loads faq_kb into memory once and answers similarity queries.

    Instantiate once (see get_kb_service) and reuse — reloading the
    model/embeddings per-request would be far too slow.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self._entries: list[KBEntry] = []
        self._embeddings: np.ndarray | None = None  # shape (n, dim), L2-normalized
        self._load(db_path)

    def _load(self, db_path: Path) -> None:
        if not db_path.exists():
            logger.warning("KB database not found at %s — KB search disabled.", db_path)
            return

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, product, section, question, answer, embedding FROM faq_kb"
            ).fetchall()
        except sqlite3.OperationalError:
            logger.warning("faq_kb table not found — run `python -m app.data.faq_seed` first.")
            conn.close()
            return
        conn.close()

        if not rows:
            logger.warning("faq_kb table is empty — KB search disabled.")
            return

        entries = []
        vectors = []
        for row in rows:
            entries.append(
                KBEntry(
                    id=row["id"],
                    product=row["product"] or "",
                    section=row["section"] or "",
                    question=row["question"],
                    answer=row["answer"],
                )
            )
            vectors.append(np.frombuffer(row["embedding"], dtype=np.float32))

        self._entries = entries
        self._embeddings = np.stack(vectors)
        logger.info("Loaded %d KB entries for semantic search.", len(entries))

    @property
    def is_ready(self) -> bool:
        return self._embeddings is not None and len(self._entries) > 0

    def best_match(self, query: str) -> tuple[KBEntry, float] | None:
        """Returns the single best-matching KB entry and its cosine
        similarity score (0-1), or None if the KB hasn't been loaded.
        """
        if not self.is_ready:
            return None

        query_vec = embed_text(query)  # already L2-normalized
        # Embeddings are normalized, so dot product == cosine similarity.
        scores = self._embeddings @ query_vec
        best_idx = int(np.argmax(scores))
        return self._entries[best_idx], float(scores[best_idx])


_kb_service: KBService | None = None


def get_kb_service() -> KBService:
    """Process-wide singleton so the model + embeddings load exactly once."""
    global _kb_service
    if _kb_service is None:
        _kb_service = KBService()
    return _kb_service
