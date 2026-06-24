"""
roadmap/retrieval.py

The RAG retrieval layer.

Hard rule from KnowledgeBaseSpecification.md:
    "The roadmap engine never performs pure semantic search."
    Order: stage → scores → blocker domains → eligibility filter → vector search → rank.

So retrieval is two-phase:
    PHASE 1  STRUCTURED FILTER (deterministic, explainable)
             Keep only KB entries that are stage-compatible, domain-relevant,
             eligibility-passing, and active.
    PHASE 2  SEMANTIC RANK (vector similarity over the filtered candidates only)
             Embed a query built from the gap profile; score candidates;
             combine with structured signal into a final rank.

Every returned item is traceable: it carries its resource_id, source_url,
provider, the domains it matched, and the reason it passed each filter.

Backends
--------
VectorStore is abstract. Two impls:
  - InMemoryVectorStore : pure Python, used in dev/CI/sandbox and as Qdrant
                          fallback. Cosine over normalized vectors.
  - QdrantVectorStore   : production; same interface, talks to a Qdrant server.

The retrieval logic is backend-agnostic — Phase 1 filtering happens in Python
either way (Qdrant payload filters can be added later as an optimization).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .embeddings import EmbeddingBackend, get_embedding_backend
from .kb.schema import STAGE_NAME_TO_TAG, load_kb


# ─────────────────────────────────────────────────────────────────────────────
# Stage compatibility: a resource tagged for stage X is relevant to a project
# AT stage X and the immediately adjacent stages (the entrepreneur is either
# consolidating the current stage or preparing the next one).
# ─────────────────────────────────────────────────────────────────────────────

_STAGE_TAG_ORDER = (
    "ideation", "validation", "structuration",
    "fundraising", "launch_planning", "growth",
)


def _adjacent_stage_tags(current_tag: str, look_ahead: int = 1, look_back: int = 0) -> List[str]:
    if current_tag not in _STAGE_TAG_ORDER:
        return list(_STAGE_TAG_ORDER)
    i = _STAGE_TAG_ORDER.index(current_tag)
    lo = max(0, i - look_back)
    hi = min(len(_STAGE_TAG_ORDER) - 1, i + look_ahead)
    return list(_STAGE_TAG_ORDER[lo:hi + 1])


# ─────────────────────────────────────────────────────────────────────────────
# Vector stores
# ─────────────────────────────────────────────────────────────────────────────

class VectorStore:
    def upsert(self, ids: Sequence[str], vectors: Sequence[Sequence[float]],
               payloads: Sequence[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def search(self, query_vector: Sequence[float], allowed_ids: Optional[set],
               top_k: int) -> List[Dict[str, Any]]:
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    """Cosine similarity over normalized vectors. Filtering done via allowed_ids."""
    def __init__(self) -> None:
        self._ids: List[str] = []
        self._vecs: List[List[float]] = []
        self._payloads: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, int] = {}

    def upsert(self, ids, vectors, payloads) -> None:
        for rid, vec, payload in zip(ids, vectors, payloads):
            if rid in self._index:
                pos = self._index[rid]
                self._vecs[pos] = list(vec)
                self._payloads[rid] = payload
            else:
                self._index[rid] = len(self._ids)
                self._ids.append(rid)
                self._vecs.append(list(vec))
                self._payloads[rid] = payload

    @staticmethod
    def _dot(a: Sequence[float], b: Sequence[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def search(self, query_vector, allowed_ids, top_k) -> List[Dict[str, Any]]:
        scored: List[Dict[str, Any]] = []
        for rid, vec in zip(self._ids, self._vecs):
            if allowed_ids is not None and rid not in allowed_ids:
                continue
            scored.append({
                "resource_id": rid,
                "similarity":  self._dot(query_vector, vec),
                "payload":     self._payloads[rid],
            })
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]


class QdrantVectorStore(VectorStore):
    """
    Production backend. Same interface as InMemory.
    Phase-1 filtering still happens in Python (allowed_ids), passed to Qdrant as
    a `must` id filter so the ANN search only ranks eligible candidates.
    """
    def __init__(self, collection: str = "leadit_kb", url: str = "http://localhost:6333",
                 dim: int = 1024):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        self._models = __import__("qdrant_client.models", fromlist=["models"])
        self._client = QdrantClient(url=url)
        self._collection = collection
        if not self._client.collection_exists(collection):
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, ids, vectors, payloads) -> None:
        from qdrant_client.models import PointStruct
        points = [
            PointStruct(id=i, vector=list(v), payload={**p, "resource_id": rid})
            for i, (rid, v, p) in enumerate(zip(ids, vectors, payloads))
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def search(self, query_vector, allowed_ids, top_k) -> List[Dict[str, Any]]:
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        qfilter = None
        if allowed_ids is not None:
            qfilter = Filter(must=[FieldCondition(
                key="resource_id", match=MatchAny(any=list(allowed_ids)))])
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=list(query_vector),
            query_filter=qfilter,
            limit=top_k,
        )
        return [{
            "resource_id": h.payload.get("resource_id"),
            "similarity":  h.score,
            "payload":     h.payload,
        } for h in hits]


# ─────────────────────────────────────────────────────────────────────────────
# Eligibility filtering (Phase 1) — Tunisian-context rules
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FilterContext:
    """Everything Phase 1 needs, assembled from the gap profile + raw profile."""
    stage_tag: str
    relevant_domains: List[str]
    sector: Optional[str] = None
    legal_form_type: Optional[str] = None
    credit_eligibility_path: Optional[str] = None
    startup_label: Optional[bool] = None
    prior_accompaniment: List[str] = field(default_factory=list)


def _passes_structured_filter(entry: Dict[str, Any], ctx: FilterContext) -> Optional[Dict[str, Any]]:
    """
    Return a 'match record' if the entry passes all hard filters, else None.
    The match record explains WHY it passed (for traceability + ranking).
    """
    # 0) Status: never recommend expired resources.
    if entry.get("status") == "expired":
        return None

    # 1) Stage compatibility: entry must share a tag with the allowed stage window.
    allowed_stages = set(_adjacent_stage_tags(ctx.stage_tag))
    entry_stages = set(entry.get("stage_tags", []))
    if entry_stages and not (entry_stages & allowed_stages):
        return None
    stage_match = bool(entry_stages & {ctx.stage_tag})  # exact-stage bonus signal

    # 2) Domain relevance: entry must address at least one of the project's
    #    ranked weakness domains. (No weakness in a domain → don't surface its
    #    resources; that's how "diagnostic gap triggers retrieval" is enforced.)
    entry_domains = set(entry.get("blocker_domains", []))
    matched_domains = sorted(entry_domains & set(ctx.relevant_domains))
    if not matched_domains:
        return None

    # 3) Sector filter: sector-agnostic entries always pass; sector-specific
    #    entries pass only on a match.
    sector_ok = True
    if entry.get("sector_tags") and ctx.sector:
        sector_ok = any(ctx.sector.lower() in s or s in ctx.sector.lower()
                        for s in entry["sector_tags"])
    if not sector_ok:
        return None

    # 4) Avoid re-recommending completed programs.
    if entry["resource_id"] in (ctx.prior_accompaniment or []):
        return None

    # 5) Financing eligibility coherence: if this is a financing resource and we
    #    know the computed credit path, don't surface a path the founder can't use.
    #    (Soft on unknowns — only filters on a confident mismatch.)
    if "financier" in entry_domains and ctx.credit_eligibility_path:
        eid = entry["resource_id"].lower()
        provider = (entry.get("provider") or "").lower()
        is_bts = "bts" in eid or "fonapra" in eid or "bts" in provider
        if ctx.credit_eligibility_path == "none" and is_bts:
            # blocked path (e.g. fichage BCT) → BTS/FONAPRA won't help
            return None

    return {
        "resource_id":     entry["resource_id"],
        "matched_domains": matched_domains,
        "stage_exact":     stage_match,
        "entry":           entry,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Ranking (Phase 2 combine)
# ─────────────────────────────────────────────────────────────────────────────

_TRUST_WEIGHT = {"official": 1.0, "international": 0.85, "ecosystem": 0.7}


def _final_score(similarity: float, match: Dict[str, Any],
                 domain_priority: Dict[str, int]) -> float:
    """
    Blend semantic similarity with structured signal. All terms normalized to
    roughly 0–1 so weights are interpretable.

        0.45 semantic   — is the text actually about this need?
        0.25 domain      — does it hit a high-priority weakness domain?
        0.15 stage       — exact-stage match beats adjacent-stage
        0.15 trust       — official > international > ecosystem
    """
    entry = match["entry"]
    # domain term: best (lowest index = highest priority) matched domain
    if match["matched_domains"] and domain_priority:
        best_rank = min(domain_priority.get(d, 99) for d in match["matched_domains"])
        n = max(1, len(domain_priority))
        domain_term = 1.0 - (best_rank / n)
    else:
        domain_term = 0.0
    stage_term = 1.0 if match["stage_exact"] else 0.5
    trust_term = _TRUST_WEIGHT.get(entry.get("trust_level"), 0.6)
    sim_term = max(0.0, min(1.0, (similarity + 1) / 2))  # cosine [-1,1] → [0,1]

    return round(
        0.45 * sim_term + 0.25 * domain_term + 0.15 * stage_term + 0.15 * trust_term,
        4,
    )


# ─────────────────────────────────────────────────────────────────────────────
# The retriever
# ─────────────────────────────────────────────────────────────────────────────

class KBRetriever:
    def __init__(self, entries: List[Dict[str, Any]],
                 embedder: Optional[EmbeddingBackend] = None,
                 store: Optional[VectorStore] = None):
        self.entries = {e["resource_id"]: e for e in entries}
        self.embedder = embedder or get_embedding_backend("auto")
        self.store = store or InMemoryVectorStore()
        self._indexed = False

    @classmethod
    def from_file(cls, path: str, **kw) -> "KBRetriever":
        return cls(load_kb(path), **kw)

    def index(self) -> None:
        """Embed every KB entry's text_blob and load it into the vector store."""
        ids = list(self.entries.keys())
        blobs = [self.entries[i]["text_blob"] for i in ids]
        vectors = self.embedder.embed_texts(blobs)
        payloads = [self.entries[i] for i in ids]
        self.store.upsert(ids, vectors, payloads)
        self._indexed = True

    def _build_query_text(self, gap_profile: Dict[str, Any]) -> str:
        """
        Construct the semantic query from the gap profile. We describe the
        WEAKNESSES in natural language so the embedding matches resources that
        address them — not the project's strengths.
        """
        parts: List[str] = []
        stage = gap_profile.get("assigned_stage")
        if stage:
            parts.append(f"projet en phase {STAGE_NAME_TO_TAG.get(stage, stage)}")
        for rd in gap_profile.get("ranked_domains", [])[:3]:
            parts.append(f"besoin {rd['domain']}")
            for g in rd["gaps"][:3]:
                label = g.get("label_fr") or g.get("criterion") or ""
                if label:
                    parts.append(str(label).replace("_", " "))
        return " ; ".join(parts) or "accompagnement entrepreneurial Tunisie"

    def retrieve(self, gap_profile: Dict[str, Any], raw_profile: Optional[Any] = None,
                 top_k: int = 8, candidate_k: int = 40) -> List[Dict[str, Any]]:
        """
        Full two-phase retrieval.

        Returns a ranked list of traceable recommendation candidates:
          {resource_id, name, provider, source_url, trust_level, status,
           matched_domains, stage_exact, similarity, final_score, why_matched, entry}
        """
        if not self._indexed:
            self.index()

        # ---- assemble filter context from the gap profile (+ optional raw profile)
        stage_name = gap_profile.get("assigned_stage") or "IDEATION"
        stage_tag = STAGE_NAME_TO_TAG.get(stage_name, "ideation")
        ranked_domains = [rd["domain"] for rd in gap_profile.get("ranked_domains", [])]
        domain_priority = {d: i for i, d in enumerate(ranked_domains)}

        def _pv(key, default=None):
            if raw_profile is None:
                return default
            if isinstance(raw_profile, dict):
                return raw_profile.get(key, default)
            return getattr(raw_profile, key, default)

        anomalies = gap_profile.get("anomalies", [])
        credit_path = None
        # credit path lives in scoring metrics; gap_profile passes it through if present
        for a in anomalies:
            pass  # placeholder: structural flags don't carry credit path
        credit_path = gap_profile.get("credit_eligibility_path") or _pv("credit_eligibility_path")

        ctx = FilterContext(
            stage_tag=stage_tag,
            relevant_domains=ranked_domains or list(domain_priority.keys()),
            sector=_pv("sector"),
            legal_form_type=_pv("legal_form_type"),
            credit_eligibility_path=credit_path,
            startup_label=_pv("startup_label"),
            prior_accompaniment=_pv("prior_accompaniment", []) or [],
        )

        # ---- PHASE 1: structured filter
        matches: Dict[str, Dict[str, Any]] = {}
        for entry in self.entries.values():
            m = _passes_structured_filter(entry, ctx)
            if m:
                matches[entry["resource_id"]] = m

        if not matches:
            return []

        # ---- PHASE 2: semantic rank over the eligible candidates only
        query_text = self._build_query_text(gap_profile)
        query_vec = self.embedder.embed_query(query_text)
        allowed = set(matches.keys())
        hits = self.store.search(query_vec, allowed_ids=allowed, top_k=candidate_k)

        results: List[Dict[str, Any]] = []
        for hit in hits:
            rid = hit["resource_id"]
            match = matches.get(rid)
            if not match:
                continue
            entry = match["entry"]
            final = _final_score(hit["similarity"], match, domain_priority)
            results.append({
                "resource_id":     rid,
                "name":            entry.get("name"),
                "provider":        entry.get("provider"),
                "source_url":      entry.get("source_url"),
                "trust_level":     entry.get("trust_level"),
                "status":          entry.get("status"),
                "category":        entry.get("category"),
                "matched_domains": match["matched_domains"],
                "stage_exact":     match["stage_exact"],
                "similarity":      round(hit["similarity"], 4),
                "final_score":     final,
                "why_matched":     self._why(match, gap_profile),
                "entry":           entry,
            })

        results.sort(key=lambda r: r["final_score"], reverse=True)
        return results[:top_k]

    @staticmethod
    def _why(match: Dict[str, Any], gap_profile: Dict[str, Any]) -> str:
        domains = match["matched_domains"]
        stage = gap_profile.get("assigned_stage", "")
        dom_str = ", ".join(domains)
        return (f"Répond au(x) blocage(s) {dom_str} "
                f"identifié(s) à la phase {STAGE_NAME_TO_TAG.get(stage, stage)}")
