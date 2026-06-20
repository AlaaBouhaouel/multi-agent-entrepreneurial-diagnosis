"""
scorers/scoring_utils.py

Shared leaf-scoring and rollup utilities for the 5 scoring engines.

Boundary: derive_all_metrics() produces facts (0-1 ratios, DT amounts, months).
These utilities translate facts → 0-10 leaf scores and roll them up to a composite.
Engines interpret; they never re-derive a metric.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def score_leaf(
    value: Optional[float],
    thresholds: List[Tuple[float, float]],
    higher_is_better: bool = True,
) -> Optional[float]:
    """
    Map a numeric value to a 0-10 score using an ordered threshold list.

    higher_is_better=True  (default): thresholds ordered highest-first;
                           returns score for first threshold where value >= threshold.
    higher_is_better=False: thresholds ordered lowest-first;
                           returns score for first threshold where value <= threshold.

    Falls back to the last entry's score if no threshold matches.
    Returns None when value is None (missing data, not a failure).
    """
    if value is None:
        return None
    if higher_is_better:
        for threshold, score in thresholds:
            if value >= threshold:
                return float(score)
    else:
        for threshold, score in thresholds:
            if value <= threshold:
                return float(score)
    return float(thresholds[-1][1])


def rollup(leaves: List[Dict[str, Any]]) -> Optional[float]:
    """
    Weighted average of non-None leaf scores, renormalizing over scored leaves only.
    Returns None when all leaves are None (no data to score).
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for lf in leaves:
        s = lf["score"]
        w = lf["weight"]
        if s is not None:
            weighted_sum += s * w
            total_weight += w
    if total_weight == 0.0:
        return None
    return round(weighted_sum / total_weight, 2)


def build_result(leaves: List[Dict[str, Any]], floor: float) -> Dict[str, Any]:
    """Assemble the standard engine output dict."""
    composite = rollup(leaves)
    return {
        "score":     composite,
        "floor":     floor,
        "floor_met": None if composite is None else composite >= floor,
        "leaves":    leaves,
    }


def leaf(
    criterion: str,
    label_fr: str,
    score: Optional[float],
    weight: float,
    evidence: Dict[str, Any],
    justification: str,
) -> Dict[str, Any]:
    return {
        "criterion":     criterion,
        "label_fr":      label_fr,
        "score":         score,
        "weight":        weight,
        "evidence":      evidence,
        "justification": justification,
    }
