"""
scorers/financing.py

Credit eligibility, runway, and repayment calculations.
Tunisian-specific logic (BTS/FONAPRA, BCT fichage, fonds de commerce).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from diagnostic.calculations import (
    _get_profile_value,
    _to_float,
    _to_int,
    _safe_div,
    _round_or_none,
    _is_truthy,
)
from .economics import compute_monthly_profit, compute_monthly_fixed_costs


def compute_opex_runway_months(profile: Any) -> Optional[float]:
    """How many months of operating expenses are covered."""
    opex_months_covered = _to_float(_get_profile_value(profile, "opex_months_covered"))
    if opex_months_covered is not None:
        return opex_months_covered
    if _is_truthy(_get_profile_value(profile, "has_opex_financing")) is False:
        return 0.0
    return None


def compute_repayment_capacity_ratio(profile: Any) -> Dict[str, Any]:
    """
    repayment_capacity_ratio = annual debt service / annual cash flow
    Lower is better. Flag when > 0.40.
    """
    cash_flow = _to_float(_get_profile_value(profile, "annual_cash_flow"))
    if cash_flow is None:
        monthly_profit = compute_monthly_profit(profile)["monthly_profit"]
        cash_flow = None if monthly_profit is None else monthly_profit * 12

    annual_debt_service = _to_float(_get_profile_value(profile, "annual_debt_service"))
    if annual_debt_service is None:
        existing_payment   = _to_float(_get_profile_value(profile, "existing_credit_monthly_payment"))
        requested_amount   = _to_float(_get_profile_value(profile, "credit_amount_needed"))
        duration_years     = _to_int(_get_profile_value(profile, "credit_duration_years"))

        if existing_payment is not None:
            annual_debt_service = existing_payment * 12
        elif requested_amount is not None and duration_years and duration_years > 0:
            annual_debt_service = requested_amount / duration_years

    return {
        "repayment_capacity_ratio": _round_or_none(_safe_div(annual_debt_service, cash_flow), 4),
        "annual_cash_flow":         cash_flow,
        "annual_debt_service":      annual_debt_service,
    }


def compute_credit_eligibility_path(profile: Any) -> Dict[str, Any]:
    """
    Determine the financing path.

    Priority:
    1. BCT fichage or impayés → blocked
    2. has_guarantee OR has_premises (fonds de commerce) → commercial_bank
    3. needs_credit ≤ 150 000 DT → bts_fonapra
    4. none
    """
    blockers             = _get_profile_value(profile, "credit_eligibility_blockers", []) or []
    has_guarantee        = _is_truthy(_get_profile_value(profile, "has_guarantee"))
    has_premises         = _is_truthy(_get_profile_value(profile, "has_premises"))
    needs_credit         = _is_truthy(_get_profile_value(profile, "needs_credit"))
    credit_amount_needed = _to_float(_get_profile_value(profile, "credit_amount_needed"))

    if "fichage_bct" in blockers or "impayes" in blockers:
        return {"credit_eligibility_path": "none", "reason": "credit_blocked_by_bct_or_unpaid_debts"}

    if has_guarantee is True or has_premises is True:
        reason = "fonds_de_commerce_guarantee" if (has_premises and not has_guarantee) else "has_guarantee"
        return {"credit_eligibility_path": "commercial_bank", "reason": reason}

    if needs_credit and credit_amount_needed is not None and credit_amount_needed <= 150_000:
        return {"credit_eligibility_path": "bts_fonapra", "reason": "eligible_for_bts_fonapra_without_guarantee"}

    return {"credit_eligibility_path": "none", "reason": "no_valid_path"}


def compute_minimum_credit_needed(profile: Any, opex_buffer_months: int = 3) -> Dict[str, Any]:
    """
    Minimum credit = max(0, total_needs - apport_personnel)

    total_needs = initial_investment + monthly_fixed_costs × opex_buffer_months
    """
    initial_investment   = _to_float(_get_profile_value(profile, "initial_investment"))
    apport_personnel     = _to_float(_get_profile_value(profile, "apport_personnel")) or 0.0
    credit_amount_needed = _to_float(_get_profile_value(profile, "credit_amount_needed"))
    monthly_fixed        = compute_monthly_fixed_costs(profile)["monthly_fixed_costs"]

    if initial_investment is None and monthly_fixed is None:
        return {
            "minimum_credit_needed":   None,
            "total_financing_needs":   None,
            "apport_personnel":        apport_personnel,
            "investment_needs":        None,
            "working_capital_needed":  None,
            "gap_exists":              None,
            "planned_credit_covers_gap": None,
            "opex_buffer_months":      opex_buffer_months,
            "reason":                  "missing_cost_data",
        }

    investment      = initial_investment or 0.0
    working_capital = (monthly_fixed or 0.0) * opex_buffer_months
    total_needs     = investment + working_capital
    minimum_credit  = max(0.0, total_needs - apport_personnel)

    planned_covers: Optional[bool] = None
    if credit_amount_needed is not None:
        planned_covers = credit_amount_needed >= minimum_credit

    return {
        "minimum_credit_needed":     _round_or_none(minimum_credit, 2),
        "total_financing_needs":     _round_or_none(total_needs, 2),
        "apport_personnel":          _round_or_none(apport_personnel, 2),
        "investment_needs":          _round_or_none(investment, 2),
        "working_capital_needed":    _round_or_none(working_capital, 2),
        "gap_exists":                minimum_credit > 0,
        "planned_credit_covers_gap": planned_covers,
        "opex_buffer_months":        opex_buffer_months,
        "reason":                    "computed",
    }
