"""
diagnostic/metrics.py

Aggregates all computed metrics into a single bundle (derive_all_metrics)
and flags financial anomalies (detect_financial_anomalies).

This is the single entry point used by downstream engines
(scoring, gap analyzer, roadmap) to read computed fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from diagnostic.calculations import (
    compute_validation_strength,
    detect_structural_coherence,
    _get_profile_value,
    _to_float,
    _is_truthy,
)
from scorers.economics import (
    compute_gross_margin_percentage,
    compute_price_positioning,
    compute_monthly_fixed_costs,
    compute_monthly_profit,
    compute_break_even_units,
)
from scorers.financing import (
    compute_opex_runway_months,
    compute_repayment_capacity_ratio,
    compute_credit_eligibility_path,
    compute_minimum_credit_needed,
)
from scorers.projections import (
    compute_5_year_projection,
    compute_breakeven_time_from_projection,
)


def detect_financial_anomalies(profile: Any) -> List[Dict[str, Any]]:
    """
    Cross-cutting financial anomaly flags for scoring and gap analysis.
    Does NOT duplicate structural coherence checks (see detect_structural_coherence).
    """
    gross        = compute_gross_margin_percentage(profile)
    pricing      = compute_price_positioning(profile)
    profit       = compute_monthly_profit(profile)
    breakeven    = compute_breakeven_time_from_projection(profile)
    projection   = compute_5_year_projection(profile)
    repayment    = compute_repayment_capacity_ratio(profile)
    credit_path  = compute_credit_eligibility_path(profile)
    runway       = compute_opex_runway_months(profile)

    anomalies: List[Dict[str, Any]] = []

    selling_price = _to_float(_get_profile_value(profile, "selling_price"))
    unit_cost     = _to_float(_get_profile_value(profile, "unit_cost"))

    if selling_price is not None and unit_cost is not None and selling_price < unit_cost:
        anomalies.append({"type": "selling_below_cost", "severity": "critical",
                          "message": "Prix de vente inférieur au coût de revient."})

    if profit["monthly_profit"] is not None and profit["monthly_profit"] <= 0:
        anomalies.append({"type": "negative_monthly_profit", "severity": "critical",
                          "message": "Le projet ne génère pas de profit mensuel."})

    if breakeven["breakeven_year"] is not None and breakeven["breakeven_year"] > 3:
        anomalies.append({"type": "late_breakeven", "severity": "warning",
                          "message": "Le projet n'atteint le point mort qu'après 3 ans."})

    if projection["van_5_years"] is not None and projection["van_5_years"] < 0:
        anomalies.append({"type": "negative_van", "severity": "warning",
                          "message": "La VAN sur 5 ans est négative."})

    if repayment["repayment_capacity_ratio"] is not None and repayment["repayment_capacity_ratio"] > 0.40:
        anomalies.append({"type": "debt_overload", "severity": "warning",
                          "message": "La capacité de remboursement dépasse 40% du cash flow."})

    if runway is not None and runway < 3 and _is_truthy(_get_profile_value(profile, "has_paying_customers")) is False:
        anomalies.append({"type": "no_runway_no_revenue", "severity": "warning",
                          "message": "Moins de 3 mois de charges couvertes et aucun client payant."})

    if credit_path["credit_eligibility_path"] == "none" and _is_truthy(_get_profile_value(profile, "needs_credit")):
        anomalies.append({"type": "credit_ineligible", "severity": "warning",
                          "message": "Le projet a besoin d'un crédit mais n'est éligible à aucun chemin évident."})

    local_ratio = pricing.get("price_vs_local_market")
    if local_ratio is not None and local_ratio > 1.3 and \
            _is_truthy(_get_profile_value(profile, "differentiation_claimed")) is False:
        anomalies.append({"type": "premium_without_differentiation", "severity": "warning",
                          "message": "Prix premium sans différenciation claire."})

    return anomalies


def derive_all_metrics(profile: Any) -> Dict[str, Any]:
    """
    Single entry point for all computed metrics.

    Scale contract: gross_margin_percentage is 0–100 (display only).
    All threshold comparisons must use gross_margin_ratio (0–1).
    """
    validation   = compute_validation_strength(profile)
    gross        = compute_gross_margin_percentage(profile)
    pricing      = compute_price_positioning(profile)
    fixed_costs  = compute_monthly_fixed_costs(profile)
    profit       = compute_monthly_profit(profile)
    bk_units     = compute_break_even_units(profile)
    bk_time      = compute_breakeven_time_from_projection(profile)
    projection   = compute_5_year_projection(profile)
    repayment    = compute_repayment_capacity_ratio(profile)
    credit_path  = compute_credit_eligibility_path(profile)
    runway       = compute_opex_runway_months(profile)
    coherence    = detect_structural_coherence(profile)
    credit_gap   = compute_minimum_credit_needed(profile)

    return {
        "validation_strength":       validation,
        "gross_margin_percentage":   gross.get("gross_margin_percentage"),
        "gross_margin_ratio":        gross.get("gross_margin_ratio"),
        "unit_contribution":         gross.get("unit_contribution"),
        "price_vs_local_market":     pricing.get("price_vs_local_market"),
        "price_vs_foreign_market":   pricing.get("price_vs_foreign_market"),
        "monthly_fixed_costs":       fixed_costs["monthly_fixed_costs"],
        "monthly_profit":            profit["monthly_profit"],
        "monthly_variable_costs":    profit["monthly_variable_costs"],
        "breakeven_units":           bk_units["breakeven_units"],
        "breakeven_months":          bk_time["breakeven_months"],
        "breakeven_year":            bk_time["breakeven_year"],
        "van_5_years":               projection["van_5_years"],
        "repayment_capacity_ratio":  repayment["repayment_capacity_ratio"],
        "credit_eligibility_path":   credit_path["credit_eligibility_path"],
        "credit_eligibility_reason": credit_path["reason"],
        "opex_months_covered":       runway,
        "projection_5y":             projection["projection_5y"],
        "structural_coherence_flags": coherence,
        "minimum_credit_needed":     credit_gap["minimum_credit_needed"],
        "total_financing_needs":     credit_gap["total_financing_needs"],
        "working_capital_needed":    credit_gap["working_capital_needed"],
        "credit_gap_exists":         credit_gap["gap_exists"],
        "planned_credit_covers_gap": credit_gap["planned_credit_covers_gap"],
        "derived_at":                datetime.now(timezone.utc).isoformat(),
    }
