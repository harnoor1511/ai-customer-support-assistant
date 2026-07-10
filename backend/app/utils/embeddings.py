"""
Thin wrapper around a local sentence-embedding model.

Kept separate from kb_service so the (fairly slow) model load happens
in exactly one place and is trivially mockable in tests.
"""
from __future__ import annotations

import numpy as np

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None  # lazy-loaded singleton


def _get_model():
    global _model
    if _model is None:
        # Imported lazily so environments that never touch the KB path
        # (e.g. quick unit tests) don't pay the import cost.
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Encode a list of strings into L2-normalized embedding vectors,
    shape (len(texts), dim), dtype float32. Normalizing up front means
    cosine similarity reduces to a plain dot product at search time.
    """
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.astype(np.float32)


def embed_text(text: str) -> np.ndarray:
    """Encode a single string. Returns shape (dim,)."""
    return embed_texts([text])[0]
