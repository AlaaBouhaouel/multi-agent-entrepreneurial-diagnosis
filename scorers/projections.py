"""
scorers/projections.py

5-year financial projections and VAN (Net Present Value).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from diagnostic.calculations import (
    _get_profile_value,
    _to_float,
    _to_int,
    _round_or_none,
    _normalize_pct,
)
from .economics import compute_monthly_fixed_costs


def compute_annual_projection(profile: Any, year: int, discount_rate: float = 0.10) -> Dict[str, Any]:
    monthly_revenue         = _to_float(_get_profile_value(profile, "monthly_revenue"))
    selling_price           = _to_float(_get_profile_value(profile, "selling_price"))
    expected_monthly_units  = _to_float(_get_profile_value(profile, "expected_monthly_units"))
    cogs_pct                = _normalize_pct(_to_float(_get_profile_value(profile, "cogs_percentage"))) or 0.0
    tfse_pct                = _normalize_pct(_to_float(_get_profile_value(profile, "tfse_percentage"))) or 0.0
    growth_rate             = _normalize_pct(_to_float(_get_profile_value(profile, "ca_growth_rate"))) or 0.0
    tax_rate                = _normalize_pct(_to_float(_get_profile_value(profile, "tax_rate"))) or 0.15
    equipment_investment    = _to_float(_get_profile_value(profile, "equipment_investment")) or 0.0
    equipment_lifespan      = _to_int(_get_profile_value(profile, "equipment_lifespan_years")) or 1
    annual_debt_service     = _to_float(_get_profile_value(profile, "annual_debt_service")) or 0.0
    existing_credit_payment = _to_float(_get_profile_value(profile, "existing_credit_monthly_payment")) or 0.0

    if monthly_revenue is not None:
        ca = monthly_revenue * 12 * ((1 + growth_rate) ** max(0, year - 1))
    elif selling_price is not None and expected_monthly_units is not None:
        ca = selling_price * expected_monthly_units * 12 * ((1 + growth_rate) ** max(0, year - 1))
    else:
        return {"year": year, "missing_data": True}

    variable_costs   = ca * cogs_pct
    tfse             = ca * tfse_pct
    personnel_annual = (_to_float(_get_profile_value(profile, "personnel_monthly_cost")) or 0.0) * 12
    rent_annual      = (_to_float(_get_profile_value(profile, "rent_monthly")) or 0.0) * 12
    other_annual     = (_to_float(_get_profile_value(profile, "other_fixed_costs_monthly")) or 0.0) * 12

    total_charges = variable_costs + tfse + personnel_annual + rent_annual + other_annual
    rbe           = ca - total_charges
    amortization  = (equipment_investment / equipment_lifespan) if equipment_investment > 0 and year <= equipment_lifespan else 0.0
    financing_costs = annual_debt_service + (existing_credit_payment * 12)
    rne           = rbe - amortization - financing_costs
    tax           = max(0.0, rne * tax_rate)
    net_income    = rne - tax
    cash_flow     = net_income + amortization

    return {
        "year":                 year,
        "ca":                   _round_or_none(ca, 2),
        "variable_costs":       _round_or_none(variable_costs, 2),
        "tfse":                 _round_or_none(tfse, 2),
        "personnel_annual":     _round_or_none(personnel_annual, 2),
        "rent_annual":          _round_or_none(rent_annual, 2),
        "other_fixed_annual":   _round_or_none(other_annual, 2),
        "total_charges":        _round_or_none(total_charges, 2),
        "rbe":                  _round_or_none(rbe, 2),
        "amortization":         _round_or_none(amortization, 2),
        "financing_costs":      _round_or_none(financing_costs, 2),
        "rne":                  _round_or_none(rne, 2),
        "tax":                  _round_or_none(tax, 2),
        "net_income":           _round_or_none(net_income, 2),
        "cash_flow":            _round_or_none(cash_flow, 2),
        "discounted_cash_flow": _round_or_none(cash_flow / ((1 + discount_rate) ** year), 2),
    }


def compute_5_year_projection(profile: Any, discount_rate: float = 0.10) -> Dict[str, Any]:
    projection: List[Dict[str, Any]] = []
    van = 0.0

    for year in range(1, 6):
        row = compute_annual_projection(profile, year=year, discount_rate=discount_rate)
        projection.append(row)
        if not row.get("missing_data"):
            if year == 1:
                van -= _to_float(_get_profile_value(profile, "initial_investment")) or 0.0
            van += row["discounted_cash_flow"] or 0.0

    return {
        "projection_5y": projection,
        "van_5_years":   _round_or_none(van, 2),
        "discount_rate": discount_rate,
    }


def compute_breakeven_time_from_projection(profile: Any) -> Dict[str, Any]:
    initial_investment = _to_float(_get_profile_value(profile, "initial_investment"))
    if initial_investment is None:
        return {"breakeven_year": None, "breakeven_months": None, "reason": "missing_initial_investment"}

    proj       = compute_5_year_projection(profile)
    cumulative = -initial_investment

    for row in proj["projection_5y"]:
        if row.get("missing_data"):
            continue
        cumulative += row["cash_flow"] or 0.0
        if cumulative >= 0:
            return {
                "breakeven_year":   row["year"],
                "breakeven_months": row["year"] * 12,
                "reason":           "projection_based",
            }

    return {"breakeven_year": None, "breakeven_months": None, "reason": "projection_based"}
