"""
scorers/innovation.py

Innovation scoring engine (0-10).

Answers: "How novel and differentiated is this idea?"

Reads profile fields directly — the financial compute layer is not needed
for this dimension (per architecture: do not stretch derive_all_metrics to cover
non-financial signals). price_vs_foreign_market is the sole exception, used
as a market-gap signal only, not a financial viability test.

gross_margin_ratio is NOT a leaf here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from criteria.calculations import _get_profile_value, _is_truthy
from .scoring_utils import build_result, leaf

_FLOOR = 4.0


def score_innovation(profile: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    leaves = [
        _idea_novelty(profile),
        _market_research_depth(profile),
        _differentiation_strength(profile),
        _price_advantage_vs_foreign(metrics),
    ]
    return build_result(leaves, _FLOOR)


# ── Leaves ────────────────────────────────────────────────────────────────────

def _idea_novelty(profile: Any) -> Dict[str, Any]:
    idea_is_new = _is_truthy(_get_profile_value(profile, "idea_is_new"))
    score: Optional[float]
    if idea_is_new is True:
        score = 10.0
    elif idea_is_new is False:
        score = 4.0   # adapted model — still scorable, not zero
    else:
        score = None
    return leaf(
        criterion    = "idea_novelty",
        label_fr     = "Nouveauté de l'idée",
        score        = score,
        weight       = 0.35,
        evidence     = {"idea_is_new": idea_is_new},
        justification = f"idea_is_new={idea_is_new} → score {score}",
    )


def _market_research_depth(profile: Any) -> Dict[str, Any]:
    studied = _is_truthy(_get_profile_value(profile, "foreign_model_studied"))
    score: Optional[float]
    if studied is True:
        score = 10.0
    elif studied is False:
        score = 2.0
    else:
        score = None
    return leaf(
        criterion    = "market_research_depth",
        label_fr     = "Profondeur de la veille marché",
        score        = score,
        weight       = 0.30,
        evidence     = {"foreign_model_studied": studied},
        justification = f"foreign_model_studied={studied} → score {score}",
    )


def _differentiation_strength(profile: Any) -> Dict[str, Any]:
    """Capped at 8: 'claimed' differentiation ≠ 'proven' differentiation."""
    differentiated = _is_truthy(_get_profile_value(profile, "differentiation_claimed"))
    score: Optional[float]
    if differentiated is True:
        score = 8.0
    elif differentiated is False:
        score = 0.0
    else:
        score = None
    return leaf(
        criterion    = "differentiation_strength",
        label_fr     = "Force de différenciation déclarée",
        score        = score,
        weight       = 0.25,
        evidence     = {"differentiation_claimed": differentiated},
        justification = f"differentiation_claimed={differentiated} → score {score}",
    )


def _price_advantage_vs_foreign(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Market-gap signal only: being cheaper signals an addressable local opportunity."""
    ratio = metrics.get("price_vs_foreign_market")
    score: Optional[float]
    if ratio is None:
        score = None
    elif ratio <= 0.80:
        score = 10.0
    elif ratio <= 1.00:
        score = 7.0
    elif ratio <= 1.20:
        score = 4.0
    else:
        score = 2.0
    return leaf(
        criterion    = "price_advantage_vs_foreign",
        label_fr     = "Avantage prix vs marché étranger",
        score        = score,
        weight       = 0.10,
        evidence     = {"price_vs_foreign_market": ratio},
        justification = f"price_vs_foreign_market {ratio} → score {score}",
    )
