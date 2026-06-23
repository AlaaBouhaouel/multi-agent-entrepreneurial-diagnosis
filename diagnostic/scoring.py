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

from projects.models import ProfileLog
from diagnostic.metrics import derive_all_metrics
from scorers.market import score_market
from scorers.commercial import score_commercial
from scorers.innovation import score_innovation
from scorers.scalability import score_scalability
from scorers.green import score_green

# Maps internal dimension name → ProfileLog.author choice key
_DIM_AUTHOR = {
    "market":      "market",
    "commercial":  "commercial",
    "innovation":  "innovation",
    "scalability": "scaling",
    "green":       "green",
}


def _save_scoring_log(profile: Any, dim: str, result: Dict[str, Any]) -> None:
    ProfileLog.objects.create(
        project=profile,
        author=_DIM_AUTHOR[dim],
        output_type=f"score.{dim}",
        metadata=result,
    )


def score_project(profile: Any) -> Dict[str, Any]:
    """
    Compute metrics once, then interpret them across all 5 dimensions.
    Persists one ProfileLog per engine. Returns the metrics bundle alongside
    the scores so callers can surface the evidence trail.
    """
    metrics = derive_all_metrics(profile)
    scores = {
        "market":      score_market(profile, metrics),
        "commercial":  score_commercial(profile, metrics),
        "innovation":  score_innovation(profile, metrics),
        "scalability": score_scalability(profile, metrics),
        "green":       score_green(profile, metrics),
    }
    for dim, result in scores.items():
        _save_scoring_log(profile, dim, result)
    return {
        "scores": scores,
        "metrics": metrics,
    }
