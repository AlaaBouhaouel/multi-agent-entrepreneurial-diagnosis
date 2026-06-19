"""
scorers/economics.py

Unit-economics calculations consumed by all scoring dimensions.
No orchestration, no persistence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from diagnostic.calculations import (
    _get_profile_value,
    _to_float,
    _to_int,
    _safe_div,
    _round_or_none,
    _is_truthy,
    _normalize_pct,
    _clamp,
)


def compute_gross_margin_percentage(profile: Any) -> Dict[str, Any]:
    """
    gross margin = (selling_price - unit_cost) / selling_price

    Scale contract:
    - gross_margin_percentage: 0–100, display only  (e.g. 58.33)
    - gross_margin_ratio:      0–1,   use this for all threshold comparisons (e.g. 0.5833)
    All scoring leaf rules must compare against gross_margin_ratio, never gross_margin_percentage.
    """
    selling_price = _to_float(_get_profile_value(profile, "selling_price"))
    unit_cost     = _to_float(_get_profile_value(profile, "unit_cost"))

    if selling_price is None or unit_cost is None:
        return {
            "gross_margin_percentage": None,
            "gross_margin_ratio":      None,
            "unit_contribution":       None,
            "price_covers_cost":       None,
        }

    contribution = selling_price - unit_cost
    margin_ratio = _safe_div(contribution, selling_price)
    margin_pct   = None if margin_ratio is None else margin_ratio * 100.0

    return {
        "gross_margin_percentage": _round_or_none(margin_pct, 2),    # 0–100, display
        "gross_margin_ratio":      _round_or_none(margin_ratio, 4),  # 0–1, comparisons
        "unit_contribution":       _round_or_none(contribution, 2),
        "price_covers_cost":       selling_price > unit_cost,
    }


def compute_price_positioning(profile: Any) -> Dict[str, Any]:
    selling_price  = _to_float(_get_profile_value(profile, "selling_price"))
    market_local   = _to_float(_get_profile_value(profile, "market_price_local"))
    market_foreign = _to_float(_get_profile_value(profile, "market_price_foreign"))

    return {
        "price_vs_local_market":   _round_or_none(_safe_div(selling_price, market_local), 4),
        "price_vs_foreign_market": _round_or_none(_safe_div(selling_price, market_foreign), 4),
        "market_price_local":      market_local,
        "market_price_foreign":    market_foreign,
    }


def compute_monthly_variable_costs(profile: Any) -> Optional[float]:
    monthly_revenue = _to_float(_get_profile_value(profile, "monthly_revenue"))
    cogs_percentage = _normalize_pct(_to_float(_get_profile_value(profile, "cogs_percentage")))
    expected_units  = _to_float(_get_profile_value(profile, "expected_monthly_units"))
    unit_cost       = _to_float(_get_profile_value(profile, "unit_cost"))

    if monthly_revenue is not None and cogs_percentage is not None:
        return _round_or_none(monthly_revenue * cogs_percentage, 2)
    if expected_units is not None and unit_cost is not None:
        return _round_or_none(expected_units * unit_cost, 2)
    return None


def compute_monthly_fixed_costs(profile: Any) -> Dict[str, Any]:
    fixed_costs = _to_float(_get_profile_value(profile, "fixed_costs_monthly"))
    personnel   = _to_float(_get_profile_value(profile, "personnel_monthly_cost"))
    rent        = _to_float(_get_profile_value(profile, "rent_monthly"))
    other       = _to_float(_get_profile_value(profile, "other_fixed_costs_monthly"))

    if fixed_costs is None:
        values = [v for v in [personnel, rent, other] if v is not None]
        total  = sum(values) if values else None
    else:
        total = fixed_costs
        if personnel is not None: total += personnel
        if rent      is not None: total += rent
        if other     is not None: total += other

    return {
        "monthly_fixed_costs": _round_or_none(total, 2),
        "components": {
            "fixed_costs_monthly":      fixed_costs,
            "personnel_monthly_cost":   personnel,
            "rent_monthly":             rent,
            "other_fixed_costs_monthly": other,
        },
    }


def compute_monthly_profit(profile: Any) -> Dict[str, Any]:
    monthly_revenue = _to_float(_get_profile_value(profile, "monthly_revenue"))
    variable_costs  = compute_monthly_variable_costs(profile)
    fixed_costs     = compute_monthly_fixed_costs(profile)["monthly_fixed_costs"]

    if monthly_revenue is None or variable_costs is None or fixed_costs is None:
        return {
            "monthly_profit":         None,
            "monthly_revenue":        monthly_revenue,
            "monthly_variable_costs": variable_costs,
            "monthly_fixed_costs":    fixed_costs,
        }

    profit = monthly_revenue - variable_costs - fixed_costs
    return {
        "monthly_profit":         _round_or_none(profit, 2),
        "monthly_revenue":        monthly_revenue,
        "monthly_variable_costs": variable_costs,
        "monthly_fixed_costs":    fixed_costs,
    }


def compute_break_even_units(profile: Any) -> Dict[str, Any]:
    fixed_costs       = compute_monthly_fixed_costs(profile)["monthly_fixed_costs"]
    unit_contribution = compute_gross_margin_percentage(profile).get("unit_contribution")

    if fixed_costs is None or unit_contribution is None:
        return {"breakeven_units": None, "unit_contribution": unit_contribution,
                "monthly_fixed_costs": fixed_costs, "breakeven_possible": None}

    if unit_contribution <= 0:
        return {"breakeven_units": None, "unit_contribution": unit_contribution,
                "monthly_fixed_costs": fixed_costs, "breakeven_possible": False}

    return {
        "breakeven_units":     _round_or_none(fixed_costs / unit_contribution, 2),
        "unit_contribution":   _round_or_none(unit_contribution, 2),
        "monthly_fixed_costs": fixed_costs,
        "breakeven_possible":  True,
    }


def compute_breakeven_months(profile: Any) -> Dict[str, Any]:
    initial_investment = _to_float(_get_profile_value(profile, "initial_investment"))
    monthly_profit     = compute_monthly_profit(profile)["monthly_profit"]

    if initial_investment is None or monthly_profit is None:
        return {"breakeven_months": None, "initial_investment": initial_investment,
                "monthly_profit": monthly_profit, "breakeven_possible": None}

    if monthly_profit <= 0:
        return {"breakeven_months": None, "initial_investment": initial_investment,
                "monthly_profit": monthly_profit, "breakeven_possible": False}

    return {
        "breakeven_months":    _round_or_none(initial_investment / monthly_profit, 2),
        "initial_investment":  initial_investment,
        "monthly_profit":      monthly_profit,
        "breakeven_possible":  True,
    }
