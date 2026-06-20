"""
diagnostic/scoring.py

Scoring orchestrator — computes all 5 dimension scores in one call.

derive_all_metrics() is called exactly once; its bundle is passed to every
engine. No engine re-derives a metric. All leaf evidence references back to
values in that bundle.

Usage:
    from diagnostic.scoring import score_project

    result = score_project(profile)
    result["scores"]["market"]["score"]          # composite 0-10
    result["scores"]["market"]["leaves"][0]      # evidence trail
    result["metrics"]["gross_margin_ratio"]      # shared financial fact
"""

from __future__ import annotations

from typing import Any, Dict

from diagnostic.metrics import derive_all_metrics
from scorers.market import score_market
from scorers.commercial import score_commercial
from scorers.innovation import score_innovation
from scorers.scalability import score_scalability
from scorers.green import score_green


def score_project(profile: Any) -> Dict[str, Any]:
    """
    Compute metrics once, then interpret them across all 5 dimensions.
    Returns the metrics bundle alongside the scores so callers can surface
    the evidence (§2.4.3, §2.4.5 — per-criterion contributions must be visible).
    """
    metrics = derive_all_metrics(profile)
    return {
        "scores": {
            "market":      score_market(profile, metrics),
            "commercial":  score_commercial(profile, metrics),
            "innovation":  score_innovation(profile, metrics),
            "scalability": score_scalability(profile, metrics),
            "green":       score_green(profile, metrics),
        },
        "metrics": metrics,
    }
