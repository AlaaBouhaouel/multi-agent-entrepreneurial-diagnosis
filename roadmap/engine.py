"""
roadmap/engine.py

The Roadmap Engine — Feature 3's orchestrator.

Pipeline (all grounded, all traceable):

    diagnose_project(profile)   →  diagnosis        (Feature 1)
    score_project(profile)      →  scoring          (Feature 2)
            │
            ▼
    analyze_gaps(diagnosis, scoring)  →  gap_profile        (pure logic)
            │
            ▼
    KBRetriever.retrieve(gap_profile) →  ranked resources   (structured + semantic)
            │
            ▼
    RoadmapLLM.synthesize(grounded payload) → ordered roadmap (LLM phrases/orders)
            │
            ▼
    build verdict + 3-horizon roadmap + unmatched gaps + Mon Parcours snapshot

Guarantees (brief §2.5):
  - Every roadmap action carries a resource_id + source_url from the KB.
  - Resources come ONLY from structured retrieval; the LLM cannot add any.
  - Different gap profiles → different retrieval → different roadmaps.
  - Gaps with no matching KB resource are reported as `unmatched_gaps`, never
    silently dropped and never answered with an invented resource.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .gap_analyzer import analyze_gaps
from .retrieval import KBRetriever
from .llm import RoadmapLLM
from .kb.schema import STAGE_NAME_TO_TAG


HORIZON_ORDER = ("immediate", "short_term", "medium_term")
HORIZON_LABELS_FR = {
    "immediate":   "Immédiat (0–1 mois)",
    "short_term":  "Court terme (1–3 mois)",
    "medium_term": "Moyen terme (3–12 mois)",
}


class RoadmapEngine:
    def __init__(self, retriever: KBRetriever, llm: Optional[RoadmapLLM] = None,
                 top_k: int = 8):
        self.retriever = retriever
        self.llm = llm or RoadmapLLM()
        self.top_k = top_k

    # ─────────────────────────────────────────────────────────────────────────

    def generate(self, profile: Any, diagnosis: Dict[str, Any],
                 scoring: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parameters
        ----------
        profile   : the shared project profile (dict or Django model)
        diagnosis : diagnose_project(profile)["metadata"]
        scoring   : score_project(profile)   ({"scores":..., "metrics":...})

        Returns the full roadmap-engine output (ready to append to the log).
        """
        # 1 — merge diagnostic + scoring into a ranked weakness profile
        gap_profile = analyze_gaps(diagnosis, scoring)
        # surface the computed credit path to the retriever's eligibility filter
        gap_profile["credit_eligibility_path"] = (
            (scoring.get("metrics") or {}).get("credit_eligibility_path")
        )

        # 2 — retrieve grounded, eligible, ranked resources
        resources = self.retriever.retrieve(
            gap_profile, raw_profile=profile, top_k=self.top_k,
        )

        # 3 — build the grounded payload the LLM is allowed to phrase
        payload = self._build_llm_payload(gap_profile, resources)

        # 4 — LLM synthesis (Qwen) with deterministic fallback
        synth = self.llm.synthesize(payload)
        actions = synth["roadmap"]

        # 5 — attach source_url + provider to every action (traceability) and
        #     group into horizons
        enriched = self._enrich_actions(actions, resources)
        roadmap_by_horizon = self._group_by_horizon(enriched)

        # 6 — gaps with no resource → reported explicitly, never invented
        unmatched = self._unmatched_gaps(gap_profile, resources)

        # 7 — verdict + perception-gap framing
        verdict = self._build_verdict(gap_profile, scoring)

        return {
            "author":    "roadmap_engine",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "output": {
                "assigned_stage":      gap_profile["assigned_stage"],
                "stage_tag":           STAGE_NAME_TO_TAG.get(gap_profile["assigned_stage"]),
                "perception_gap":      gap_profile.get("perception_gap"),
                "confidence":          gap_profile.get("confidence"),
                "verdict":             verdict,
                "roadmap_by_horizon":  roadmap_by_horizon,
                "roadmap_flat":        enriched,
                "matched_resources":   resources,
                "unmatched_gaps":      unmatched,
                "ranked_domains":      [rd["domain"] for rd in gap_profile["ranked_domains"]],
                "missing_data_fields": gap_profile.get("missing_data_fields", []),
                "synthesis_source":    synth["_source"],   # "llm" | "template"
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _build_llm_payload(self, gap_profile: Dict[str, Any],
                           resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compact, grounded context. Only fields the LLM needs to phrase + order."""
        return {
            "diagnostic": {
                "phase":          gap_profile["assigned_stage"],
                "phase_tag":      STAGE_NAME_TO_TAG.get(gap_profile["assigned_stage"]),
                "confidence":     (gap_profile.get("confidence") or {}).get("level"),
                "perception_gap": gap_profile.get("perception_gap"),
            },
            "blocages_prioritaires": [
                {
                    "domain":    rd["domain"],
                    "gap_count": rd["gap_count"],
                    "exemples":  [
                        (g.get("label_fr") or g.get("criterion"))
                        for g in rd["gaps"][:4]
                    ],
                }
                for rd in gap_profile["ranked_domains"][:4]
            ],
            "resources": [
                {
                    "resource_id":     r["resource_id"],
                    "name":            r["name"],
                    "provider":        r["provider"],
                    "category":        r.get("category"),
                    "matched_domains": r["matched_domains"],
                    "why_matched":     r["why_matched"],
                    "description":     r["entry"].get("description", ""),
                    "benefits":        r["entry"].get("benefits", ""),
                    "eligibility":     r["entry"].get("eligibility", ""),
                }
                for r in resources
            ],
        }

    @staticmethod
    def _enrich_actions(actions: List[Dict[str, Any]],
                        resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Attach source_url, provider, trust_level from the matched resource."""
        by_id = {r["resource_id"]: r for r in resources}
        out = []
        for a in actions:
            r = by_id.get(a.get("resource_id"))
            if not r:
                continue  # grounding guard already ran, but double-safe
            out.append({
                **a,
                "horizon_label_fr": HORIZON_LABELS_FR.get(a.get("horizon"), a.get("horizon")),
                "resource_name":    r["name"],
                "provider":         r["provider"],
                "source_url":       r["source_url"],
                "trust_level":      r["trust_level"],
            })
        return out

    @staticmethod
    def _group_by_horizon(actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        grouped = {h: [] for h in HORIZON_ORDER}
        for a in actions:
            h = a.get("horizon") if a.get("horizon") in grouped else "short_term"
            grouped[h].append(a)
        return {
            h: {"label_fr": HORIZON_LABELS_FR[h], "actions": grouped[h]}
            for h in HORIZON_ORDER
        }

    @staticmethod
    def _unmatched_gaps(gap_profile: Dict[str, Any],
                        resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Domains that have a weakness but NO retrieved resource. Reported so the
        UI can say 'Resource not found in knowledge base' (KB spec) instead of
        the LLM inventing one.
        """
        covered = set()
        for r in resources:
            covered.update(r["matched_domains"])
        unmatched = []
        for rd in gap_profile["ranked_domains"]:
            if rd["domain"] not in covered:
                unmatched.append({
                    "domain":    rd["domain"],
                    "gap_count": rd["gap_count"],
                    "message_fr": (
                        f"Blocage '{rd['domain']}' identifié mais aucune ressource "
                        f"correspondante dans la base de connaissances."
                    ),
                })
        return unmatched

    @staticmethod
    def _build_verdict(gap_profile: Dict[str, Any], scoring: Dict[str, Any]) -> Dict[str, Any]:
        """A short framing of where the project stands + the perception gap."""
        pg = gap_profile.get("perception_gap") or {}
        direction = pg.get("gap_direction")
        msg = None
        if direction == "overestimate":
            msg = (f"Vous vous situez à la phase {pg.get('self_assessed_stage')} alors que "
                   f"le diagnostic indique la phase {pg.get('diagnosed_stage')}. "
                   f"La feuille de route comble cet écart.")
        elif direction == "underestimate":
            msg = ("Votre projet est plus avancé que votre auto-évaluation. "
                   "La feuille de route capitalise sur cette avance.")
        elif direction == "aligned":
            msg = "Votre auto-évaluation correspond au diagnostic."
        return {
            "stage":            gap_profile["assigned_stage"],
            "perception_gap_message_fr": msg,
            "top_domains":      [rd["domain"] for rd in gap_profile["ranked_domains"][:3]],
        }
