"""
roadmap/gap_analyzer.py

The Gap Analyzer is the bridge between Features 1+2 (Diagnostic + Scoring)
and Feature 3 (RAG roadmap). It is PURE LOGIC — no LLM, no KB, no randomness.

It consumes:
    diagnosis  = diagnose_project(profile)["metadata"]      (diagnostic/services.py)
    scoring    = score_project(profile)                      (diagnostic/scoring.py)

and produces a single ranked, domain-tagged weakness profile that the
retrieval layer turns into KB queries.

Why this exists
---------------
Brief §2.2: "A diagnostic finding that identifies a missing market validation
step should surface relevant support programs that address it. A scalability
gap should connect to specific actions in the roadmap." The gap analyzer is the
mechanism that makes diagnostic gaps and low sub-scores converge into one
ranked list of domains + concrete weaknesses — the retrieval filter.

Domain reconciliation
----------------------
The diagnostic engine emits 5 blocker domains (criteria_nested.BLOCKER_DOMAINS):
    financier, légal, marché, organisationnel, technique
The KB spec (KnowledgeBaseSpecification.md) adds a 6th: green.
Scoring dimensions don't map 1:1 to diagnostic domains, so we translate each
low score to a domain here. This keeps the KB's 6-domain space intact while the
classifier stays lean on 5.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Domain space (KB-facing — 6 domains, superset of the classifier's 5)
# ─────────────────────────────────────────────────────────────────────────────

KB_DOMAINS: Tuple[str, ...] = (
    "financier",
    "légal",
    "marché",
    "organisationnel",
    "technique",
    "green",
)

# Each scoring dimension contributes weakness signal to one or more KB domains.
# A low score in a dimension raises a gap in its mapped domain(s).
SCORE_DIMENSION_TO_DOMAINS: Dict[str, Tuple[str, ...]] = {
    "market":      ("marché", "financier"),
    "commercial":  ("marché", "organisationnel"),
    "innovation":  ("technique", "marché"),
    "scalability": ("organisationnel", "technique"),
    "green":       ("green",),
}

# A sub-score (leaf) at or below this 0–10 value is treated as a real weakness.
LOW_LEAF_THRESHOLD = 4.0
# A composite score at or below this triggers a dimension-level gap.
LOW_COMPOSITE_THRESHOLD = 5.0

# Severity weights used in ranking.
SEVERITY_CONFIRMED_GAP = 2   # diagnostic value == False  (real, identified gap)
SEVERITY_MISSING_DATA  = 1   # diagnostic value == None   (uncertainty surfaced)
SEVERITY_LOW_SCORE     = 2   # scoring leaf below threshold


# ─────────────────────────────────────────────────────────────────────────────
# Stage ordering (local copy to avoid importing the criteria package here;
# the gap analyzer only needs the index for "earlier stage = more fundamental")
# ─────────────────────────────────────────────────────────────────────────────

_STAGE_ORDER = (
    "IDEATION",
    "MARKET_VALIDATION",
    "STRUCTURATION",
    "FUNDRAISING",
    "LAUNCH_PLANNING",
    "GROWTH",
)


def _stage_index(stage: Optional[str]) -> int:
    if not stage:
        return 99
    try:
        return _STAGE_ORDER.index(str(stage).upper())
    except ValueError:
        return 99


# ─────────────────────────────────────────────────────────────────────────────
# Gap extraction
# ─────────────────────────────────────────────────────────────────────────────

def _gaps_from_diagnostic(diagnosis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Turn each failed/unknown diagnostic criterion into a gap record.
    Reads diagnosis['failed_criteria'] (list of {criterion, value, stage, domain}).
    """
    gaps: List[Dict[str, Any]] = []
    for item in diagnosis.get("failed_criteria", []) or []:
        value = item.get("value")
        is_confirmed = value is False
        gaps.append({
            "source":      "diagnostic",
            "criterion":   item.get("criterion"),
            "domain":      item.get("domain"),
            "stage":       item.get("stage"),
            "stage_index": _stage_index(item.get("stage")),
            "kind":        "confirmed_gap" if is_confirmed else "missing_data",
            "severity":    SEVERITY_CONFIRMED_GAP if is_confirmed else SEVERITY_MISSING_DATA,
            "detail":      None,
        })
    return gaps


def _gaps_from_scoring(scoring: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Turn low composite scores and low leaves into gap records.
    Reads scoring['scores'][dim] = {score, floor, floor_met, leaves:[...]}.
    """
    gaps: List[Dict[str, Any]] = []
    scores = (scoring or {}).get("scores", {}) or {}

    for dim, result in scores.items():
        if not isinstance(result, dict):
            continue
        domains = SCORE_DIMENSION_TO_DOMAINS.get(dim, ())
        composite = result.get("score")

        # Composite-level gap
        if composite is not None and composite <= LOW_COMPOSITE_THRESHOLD:
            for domain in domains:
                gaps.append({
                    "source":      "scoring",
                    "criterion":   f"{dim}_composite_low",
                    "dimension":   dim,
                    "domain":      domain,
                    "stage":       None,
                    "stage_index": 50,  # scoring gaps sit between stages in priority
                    "kind":        "low_score",
                    "severity":    SEVERITY_LOW_SCORE,
                    "score":       composite,
                    "detail":      f"{dim} composite score {composite}/10",
                })

        # Leaf-level gaps (the granular, actionable weaknesses)
        for lf in result.get("leaves", []) or []:
            leaf_score = lf.get("score")
            if leaf_score is None or leaf_score > LOW_LEAF_THRESHOLD:
                continue
            for domain in domains:
                gaps.append({
                    "source":      "scoring",
                    "criterion":   lf.get("criterion"),
                    "dimension":   dim,
                    "domain":      domain,
                    "label_fr":    lf.get("label_fr"),
                    "stage":       None,
                    "stage_index": 50,
                    "kind":        "low_leaf",
                    "severity":    SEVERITY_LOW_SCORE,
                    "score":       leaf_score,
                    "evidence":    lf.get("evidence"),
                    "detail":      lf.get("justification"),
                })

    return gaps


# ─────────────────────────────────────────────────────────────────────────────
# Ranking
# ─────────────────────────────────────────────────────────────────────────────

def _rank_domains(gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aggregate gaps by domain and rank them.

    Ranking key (matches the diagnostic engine's own blocker logic in
    services.identify_blockers, extended with score severity):
        1. earliest stage among the domain's gaps  (lower index = more fundamental)
        2. number of gaps in the domain            (more = systemic)
        3. total severity                          (confirmed gaps + low scores)
    """
    by_domain: Dict[str, List[Dict[str, Any]]] = {d: [] for d in KB_DOMAINS}
    for g in gaps:
        domain = g.get("domain")
        if domain in by_domain:
            by_domain[domain].append(g)

    ranked: List[Dict[str, Any]] = []
    for domain, items in by_domain.items():
        if not items:
            continue
        earliest = min(i.get("stage_index", 99) for i in items)
        count = len(items)
        severity = sum(i.get("severity", 0) for i in items)
        ranked.append({
            "domain":        domain,
            "gap_count":     count,
            "earliest_stage_index": earliest,
            "total_severity": severity,
            "gaps":          items,
        })

    ranked.sort(key=lambda d: (d["earliest_stage_index"], -d["gap_count"], -d["total_severity"]))
    return ranked


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def analyze_gaps(diagnosis: Dict[str, Any], scoring: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge diagnostic blockers + low scores into one ranked weakness profile.

    Parameters
    ----------
    diagnosis : the `metadata` dict from diagnose_project()
    scoring   : the full dict from score_project()  ({"scores": {...}, "metrics": {...}})

    Returns
    -------
    {
        "assigned_stage":        str,
        "assigned_stage_index":  int,
        "perception_gap":        {...},     # passed through for roadmap framing
        "confidence":            {...},
        "ranked_domains":        [ {domain, gap_count, earliest_stage_index,
                                     total_severity, gaps:[...]}, ... ],
        "top_domain":            str | None,
        "all_gaps":              [ ...flat list... ],
        "missing_data_fields":   [ criterion, ... ],
        "anomalies":             [ ...from metrics... ],
    }
    """
    diag_gaps  = _gaps_from_diagnostic(diagnosis)
    score_gaps = _gaps_from_scoring(scoring)
    all_gaps   = diag_gaps + score_gaps

    ranked = _rank_domains(all_gaps)

    missing_data = [
        g["criterion"] for g in diag_gaps if g["kind"] == "missing_data"
    ]

    metrics = (scoring or {}).get("metrics", {}) or {}
    anomalies = metrics.get("structural_coherence_flags", []) or []

    return {
        "assigned_stage":       diagnosis.get("assigned_stage"),
        "assigned_stage_index": diagnosis.get("assigned_stage_index"),
        "perception_gap":       diagnosis.get("perception_gap"),
        "confidence":           diagnosis.get("confidence"),
        "ranked_domains":       ranked,
        "top_domain":           ranked[0]["domain"] if ranked else None,
        "all_gaps":             all_gaps,
        "missing_data_fields":  missing_data,
        "anomalies":            anomalies,
    }
