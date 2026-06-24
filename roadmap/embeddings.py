"""
roadmap/embeddings.py

Embedding backend for KB retrieval.

Primary:   BAAI/bge-m3 via sentence-transformers (multilingual FR + AR, 1024-dim).
           Chosen because the product is francophone Tunisian with an Arabic
           bonus-point goal — bge-m3 handles both natively in one model.

Fallback:  a deterministic hashing embedder (no external download) so the
           pipeline runs in CI / offline / this sandbox without pulling weights.
           It is NOT semantically good — it exists only to keep the pipeline
           executable end-to-end. Real retrieval quality requires bge-m3.

The rest of the system depends only on embed_texts() / embed_query() returning
unit-normalized float vectors of a fixed dimension. Swapping the backend never
touches the retrieval or roadmap code.
"""

from __future__ import annotations

import hashlib
import math
from typing import List, Optional, Sequence


class EmbeddingBackend:
    """Base interface."""
    dim: int = 0

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]


class BGEM3Backend(EmbeddingBackend):
    """BAAI/bge-m3 through sentence-transformers. Lazy-loads the model."""
    def __init__(self, model_name: str = "BAAI/bge-m3", device: Optional[str] = None):
        from sentence_transformers import SentenceTransformer  # imported lazily
        self._model = SentenceTransformer(model_name, device=device)
        self.dim = self._model.get_sentence_embedding_dimension()
        self.model_name = model_name

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        vecs = self._model.encode(
            list(texts),
            normalize_embeddings=True,   # cosine == dot product after this
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vecs]


class HashingBackend(EmbeddingBackend):
    """
    Deterministic, dependency-free fallback embedder.
    Bag-of-character-ngrams hashed into a fixed-dim vector, then L2-normalized.
    Good enough to exercise the pipeline; NOT a substitute for bge-m3 in prod.
    """
    def __init__(self, dim: int = 512):
        self.dim = dim
        self.model_name = "hashing-fallback"

    def _tokens(self, text: str) -> List[str]:
        text = text.lower()
        words = text.split()
        grams: List[str] = []
        for w in words:
            grams.append(w)
            padded = f"  {w}  "
            for i in range(len(padded) - 2):
                grams.append(padded[i:i + 3])  # char trigrams (subword robustness)
        return grams

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in self._tokens(text or ""):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 8) & 1 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


def get_embedding_backend(prefer: str = "auto") -> EmbeddingBackend:
    """
    prefer = "auto"     → try bge-m3, fall back to hashing
             "bge"      → force bge-m3 (raises if unavailable)
             "hashing"  → force fallback
    """
    if prefer == "hashing":
        return HashingBackend()
    if prefer in ("auto", "bge"):
        try:
            return BGEM3Backend()
        except Exception:
            if prefer == "bge":
                raise
            return HashingBackend()
    raise ValueError(f"unknown prefer={prefer}")
