"""
scorers/commercial.py

Commercial positioning scoring engine (0-10).

Answers: "How well does this product stand against the market?"

gross_margin_ratio facet: pricing coherence.
Is the price-to-cost gap deliberate and defensible as a commercial positioning choice?
Compare with market.py (sustainability) and scalability.py (reinvestment room).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from criteria.calculations import _get_profile_value, _to_float
from .scoring_utils import build_result, leaf, score_leaf

_FLOOR = 4.0


def score_commercial(profile: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    leaves = [
        _pricing_coherence(metrics),
        _local_price_positioning(metrics),
        _foreign_price_positioning(metrics),
        _volume_vs_breakeven(profile, metrics),
    ]
    return build_result(leaves, _FLOOR)


# ── Leaves ────────────────────────────────────────────────────────────────────

def _pricing_coherence(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Facet: pricing coherence.
    Does the margin between price and cost reflect intentional positioning?
    A higher margin signals the founder has built in commercial headroom.
    """
    gmr = metrics.get("gross_margin_ratio")
    score: Optional[float]
    if gmr is None:
        score = None
    elif gmr < 0:
        score = 0.0
    else:
        score = score_leaf(gmr, [(0.40, 10), (0.25, 7), (0.10, 4), (0.0, 2)])
    return leaf(
        criterion    = "pricing_coherence",
        label_fr     = "Cohérence prix / coût (marge)",
        score        = score,
        weight       = 0.30,
        evidence     = {
            "gross_margin_ratio":      gmr,
            "gross_margin_percentage": metrics.get("gross_margin_percentage"),
        },
        justification = f"gross_margin_ratio {gmr} → score {score}",
    )


def _local_price_positioning(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """price_vs_local_market = my_price / market_price. Near 1.0 = competitive parity."""
    ratio = metrics.get("price_vs_local_market")
    score: Optional[float]
    if ratio is None:
        score = None
    elif 0.90 <= ratio <= 1.10:
        score = 10.0
    elif (0.75 <= ratio < 0.90) or (1.10 < ratio <= 1.25):
        score = 7.0
    elif (0.60 <= ratio < 0.75) or (1.25 < ratio <= 1.40):
        score = 4.0
    else:
        score = 1.0
    return leaf(
        criterion    = "local_price_positioning",
        label_fr     = "Positionnement prix vs marché tunisien",
        score        = score,
        weight       = 0.30,
        evidence     = {"price_vs_local_market": ratio},
        justification = f"price_vs_local_market {ratio} → score {score}",
    )


def _foreign_price_positioning(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Being cheaper than the foreign benchmark = competitive advantage for Tunisia."""
    ratio = metrics.get("price_vs_foreign_market")
    score: Optional[float]
    if ratio is None:
        score = None
    elif ratio <= 0.80:
        score = 10.0
    elif ratio <= 1.00:
        score = 8.0
    elif ratio <= 1.20:
        score = 5.0
    else:
        score = 2.0
    return leaf(
        criterion    = "foreign_price_positioning",
        label_fr     = "Positionnement prix vs marché étranger",
        score        = score,
        weight       = 0.20,
        evidence     = {"price_vs_foreign_market": ratio},
        justification = f"price_vs_foreign_market {ratio} → score {score}",
    )


def _volume_vs_breakeven(profile: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    expected  = _to_float(_get_profile_value(profile, "expected_monthly_units"))
    breakeven = metrics.get("breakeven_units")
    ratio: Optional[float] = None
    score: Optional[float] = None
    if expected is not None and breakeven is not None and breakeven > 0:
        ratio = round(expected / breakeven, 4)
        score = score_leaf(ratio, [(2.0, 10), (1.5, 8), (1.0, 5), (0.0, 2)])
    return leaf(
        criterion    = "volume_vs_breakeven",
        label_fr     = "Volume prévu vs point mort",
        score        = score,
        weight       = 0.15,
        evidence     = {
            "expected_monthly_units": expected,
            "breakeven_units":        breakeven,
            "ratio":                  ratio,
        },
        justification = f"expected/breakeven ratio {ratio} → score {score}",
    )
