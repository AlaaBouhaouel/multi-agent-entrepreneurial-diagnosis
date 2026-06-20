"""
scorers/scalability.py

Scalability scoring engine (0-10).

Answers: "Can this project grow without hitting structural limits?"

gross_margin_ratio facet: unit economics at scale.
Does the margin leave reinvestment room when volume multiplies 2-3x?
A narrow margin that barely works at launch collapses under scaling pressure.
Compare with market.py (sustainability threshold) and commercial.py (pricing intent).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from criteria.calculations import _get_profile_value, _is_truthy, _to_float
from .scoring_utils import build_result, leaf, score_leaf

_FLOOR = 4.0


def score_scalability(profile: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    leaves = [
        _unit_economics_at_scale(metrics),
        _volume_headroom(profile, metrics),
        _team_depth(profile),
        _fixed_cost_leverage(metrics),
    ]
    return build_result(leaves, _FLOOR)


# ── Leaves ────────────────────────────────────────────────────────────────────

def _unit_economics_at_scale(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Facet: reinvestment room at volume.
    A margin ≥55% means the business retains enough per unit to fund growth
    without external capital at each scaling step.
    """
    gmr = metrics.get("gross_margin_ratio")
    score: Optional[float]
    if gmr is None:
        score = None
    elif gmr < 0.10:
        score = 0.0
    else:
        score = score_leaf(gmr, [(0.55, 10), (0.40, 8), (0.25, 5), (0.10, 2)])
    return leaf(
        criterion    = "unit_economics_at_scale",
        label_fr     = "Économie unitaire à l'échelle",
        score        = score,
        weight       = 0.30,
        evidence     = {"gross_margin_ratio": gmr},
        justification = f"gross_margin_ratio {gmr} → score {score} (facet: reinvestment room at volume)",
    )


def _volume_headroom(profile: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    """How many times above breakeven is expected volume? Headroom = growth buffer."""
    expected  = _to_float(_get_profile_value(profile, "expected_monthly_units"))
    breakeven = metrics.get("breakeven_units")
    ratio: Optional[float] = None
    score: Optional[float] = None
    if expected is not None and breakeven is not None and breakeven > 0:
        ratio = round(expected / breakeven, 4)
        score = score_leaf(ratio, [(3.0, 10), (2.0, 8), (1.5, 6), (1.0, 4), (0.0, 1)])
    return leaf(
        criterion    = "volume_headroom",
        label_fr     = "Marge de volume au-dessus du seuil",
        score        = score,
        weight       = 0.25,
        evidence     = {
            "expected_monthly_units": expected,
            "breakeven_units":        breakeven,
            "ratio":                  ratio,
        },
        justification = f"expected/breakeven ratio {ratio} → score {score}",
    )


def _team_depth(profile: Any) -> Dict[str, Any]:
    core_complete = _is_truthy(_get_profile_value(profile, "team_core_complete"))
    associes      = _get_profile_value(profile, "associes") or []
    if not isinstance(associes, list):
        associes = []
    n = len(associes)

    score: Optional[float]
    if core_complete is None:
        score = None
    elif core_complete is True and n >= 2:
        score = 10.0
    elif core_complete is True:
        score = 7.0
    elif n >= 2:
        score = 5.0
    else:
        score = 2.0
    return leaf(
        criterion    = "team_depth",
        label_fr     = "Profondeur de l'équipe",
        score        = score,
        weight       = 0.25,
        evidence     = {"team_core_complete": core_complete, "associes_count": n},
        justification = f"core_complete={core_complete}, associes={n} → score {score}",
    )


def _fixed_cost_leverage(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    fixed_cost_ratio = monthly_fixed_costs / monthly_revenue.
    Low fixed base = fixed costs don't multiply with volume, improving margin at scale.
    """
    fixed    = metrics.get("monthly_fixed_costs")
    profit   = metrics.get("monthly_profit")
    variable = metrics.get("monthly_variable_costs")
    ratio: Optional[float] = None
    score: Optional[float] = None

    if fixed is not None and profit is not None and variable is not None:
        monthly_revenue = profit + variable + fixed   # revenue = profit + total costs
        if monthly_revenue > 0:
            ratio = round(fixed / monthly_revenue, 4)
            if ratio <= 0.30:
                score = 10.0
            elif ratio <= 0.50:
                score = 7.0
            elif ratio <= 0.70:
                score = 4.0
            else:
                score = 1.0

    return leaf(
        criterion    = "fixed_cost_leverage",
        label_fr     = "Levier charges fixes / chiffre d'affaires",
        score        = score,
        weight       = 0.20,
        evidence     = {
            "monthly_fixed_costs":     fixed,
            "fixed_to_revenue_ratio":  ratio,
        },
        justification = f"fixed/revenue ratio {ratio} → score {score}",
    )
