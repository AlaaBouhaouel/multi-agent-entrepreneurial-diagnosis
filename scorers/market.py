"""
scorers/market.py

Market viability scoring engine (0-10).

Answers: "Is this project financially viable as a business?"

gross_margin_ratio facet: revenue model sustainability.
Can the margin support long-term operations without needing constant re-injection?
Compare with commercial.py (pricing coherence) and scalability.py (reinvestment room).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from criteria.calculations import _get_profile_value, _is_truthy
from .scoring_utils import build_result, leaf, score_leaf

_FLOOR = 5.0


def score_market(profile: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    leaves = [
        _gross_margin_viability(metrics),
        _breakeven_reachability(metrics),
        _opex_runway(metrics),
        _credit_access(profile, metrics),
        _investment_gap_covered(metrics),
    ]
    return build_result(leaves, _FLOOR)


# ── Leaves ────────────────────────────────────────────────────────────────────

def _gross_margin_viability(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Facet: revenue model sustainability.
    Is the margin large enough that the business can survive normal cost shocks?
    """
    gmr = metrics.get("gross_margin_ratio")
    score: Optional[float]
    if gmr is None:
        score = None
    elif gmr < 0:
        score = 0.0
    else:
        score = score_leaf(gmr, [(0.50, 10), (0.35, 7), (0.20, 4), (0.0, 2)])
    return leaf(
        criterion    = "gross_margin_viability",
        label_fr     = "Viabilité de la marge brute",
        score        = score,
        weight       = 0.30,
        evidence     = {
            "gross_margin_ratio":      gmr,
            "gross_margin_percentage": metrics.get("gross_margin_percentage"),
        },
        justification = f"gross_margin_ratio {gmr} → score {score}",
    )


def _breakeven_reachability(metrics: Dict[str, Any]) -> Dict[str, Any]:
    bk = metrics.get("breakeven_months")
    score: Optional[float]
    if bk is None:
        score = None
    else:
        score = score_leaf(bk, [(12, 10), (24, 7), (36, 5), (48, 3)], higher_is_better=False)
        if score is None:
            score = 1.0   # > 48 months
    return leaf(
        criterion    = "breakeven_reachability",
        label_fr     = "Délai d'atteinte du point mort",
        score        = score,
        weight       = 0.25,
        evidence     = {
            "breakeven_months": bk,
            "breakeven_year":   metrics.get("breakeven_year"),
        },
        justification = f"breakeven_months {bk} → score {score}",
    )


def _opex_runway(metrics: Dict[str, Any]) -> Dict[str, Any]:
    runway = metrics.get("opex_months_covered")
    score: Optional[float]
    if runway is None:
        score = None
    elif runway == 0:
        score = 0.0
    else:
        score = score_leaf(runway, [(6, 10), (3, 7), (1, 4)])
    return leaf(
        criterion    = "opex_runway",
        label_fr     = "Trésorerie disponible (mois de charges)",
        score        = score,
        weight       = 0.20,
        evidence     = {"opex_months_covered": runway},
        justification = f"opex_months_covered {runway} → score {score}",
    )


def _credit_access(profile: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    path         = metrics.get("credit_eligibility_path")
    needs_credit = _is_truthy(_get_profile_value(profile, "needs_credit"))
    score: Optional[float]
    if path is None:
        score = None
    elif path == "commercial_bank":
        score = 10.0
    elif path == "bts_fonapra":
        score = 7.0
    elif path == "none" and needs_credit is False:
        score = 9.0   # self-funded — no credit needed
    elif path == "none" and needs_credit is True:
        score = 0.0   # needs credit but no eligible path
    else:
        score = None
    return leaf(
        criterion    = "credit_access",
        label_fr     = "Accès au financement",
        score        = score,
        weight       = 0.15,
        evidence     = {
            "credit_eligibility_path":   path,
            "credit_eligibility_reason": metrics.get("credit_eligibility_reason"),
            "needs_credit":              needs_credit,
        },
        justification = f"path={path}, needs_credit={needs_credit} → score {score}",
    )


def _investment_gap_covered(metrics: Dict[str, Any]) -> Dict[str, Any]:
    gap_exists  = metrics.get("credit_gap_exists")
    covers_gap  = metrics.get("planned_credit_covers_gap")
    min_credit  = metrics.get("minimum_credit_needed")
    score: Optional[float]
    if gap_exists is None:
        score = None
    elif gap_exists is False:
        score = 10.0  # fully self-funded, no gap
    elif covers_gap is True:
        score = 8.0
    elif covers_gap is False:
        score = 3.0
    else:
        score = None
    return leaf(
        criterion    = "investment_gap_covered",
        label_fr     = "Couverture du besoin d'investissement",
        score        = score,
        weight       = 0.10,
        evidence     = {
            "credit_gap_exists":         gap_exists,
            "planned_credit_covers_gap": covers_gap,
            "minimum_credit_needed":     min_credit,
        },
        justification = f"gap_exists={gap_exists}, planned_covers={covers_gap} → score {score}",
    )
