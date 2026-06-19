"""
test.py — standalone unit tests for the LeadIt calculation + diagnostic layer.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# ── path setup ────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                              # scorers.*, diagnostic.*
sys.path.insert(0, os.path.join(ROOT, "criteria"))   # criteria_nested (flat import)

# Mock Django before any app module imports it
for mod in ["django", "django.db", "django.db.models", "projects", "projects.models"]:
    sys.modules[mod] = MagicMock()

# ── imports under test ────────────────────────────────────────────────
from diagnostic.calculations import (
    _get_profile_value, _to_float, _to_int, _is_truthy,
    compute_validation_strength, detect_structural_coherence,
    get_maturity_criteria_results,
)
from scorers.economics import (
    compute_gross_margin_percentage, compute_monthly_fixed_costs,
    compute_monthly_profit, compute_break_even_units,
)
from scorers.financing import (
    compute_credit_eligibility_path, compute_minimum_credit_needed,
    compute_opex_runway_months,
)
from diagnostic.services import (
    evaluate_criteria, stage_classification,
    extract_failed_criteria, identify_blockers,
    compute_confidence, detect_perception_gap,
)


# ── shared fixtures ───────────────────────────────────────────────────

STAGE2_PROFILE = {
    # market_knowledge
    "target_customer_defined":      True,
    "geographic_scope":             "local",
    "idea_is_new":                  True,
    "differentiation_claimed":      True,
    # founder_readiness
    "founder_has_required_skills":  True,
    "founder_has_prior_experience": True,
    # customers_validation (via interviews)
    "customer_interview_count":     5,
}

ECONOMICS_PROFILE = {
    "selling_price":             100.0,
    "unit_cost":                 40.0,
    "expected_monthly_units":    50,
    "personnel_monthly_cost":    1500.0,
    "rent_monthly":              500.0,
    "other_fixed_costs_monthly": 200.0,
    "initial_investment":        30_000.0,
    "monthly_revenue":           5_000.0,
}


# ── 1. Helper functions ───────────────────────────────────────────────

class TestHelpers(unittest.TestCase):

    def test_get_profile_value_dict(self):
        self.assertEqual(_get_profile_value({"age": 30}, "age"), 30)

    def test_get_profile_value_metadata_fallback(self):
        p = {"metadata": {"sector": "agri"}}
        self.assertEqual(_get_profile_value(p, "sector"), "agri")

    def test_get_profile_value_missing_returns_default(self):
        self.assertIsNone(_get_profile_value({}, "nope"))
        self.assertEqual(_get_profile_value({}, "nope", "default"), "default")

    def test_to_float_none(self):
        self.assertIsNone(_to_float(None))

    def test_to_float_string(self):
        self.assertEqual(_to_float("3.14"), 3.14)

    def test_to_float_invalid(self):
        self.assertIsNone(_to_float("abc"))

    def test_is_truthy_none(self):
        self.assertIsNone(_is_truthy(None))

    def test_is_truthy_bool(self):
        self.assertTrue(_is_truthy(True))
        self.assertFalse(_is_truthy(False))

    def test_is_truthy_non_empty_string(self):
        self.assertTrue(_is_truthy("yes"))

    def test_is_truthy_zero(self):
        self.assertFalse(_is_truthy(0))

    def test_to_int_string(self):
        self.assertEqual(_to_int("7"), 7)

    def test_to_int_none(self):
        self.assertIsNone(_to_int(None))

    def test_to_int_invalid(self):
        self.assertIsNone(_to_int("abc"))


# ── 2. Validation strength ────────────────────────────────────────────

class TestValidationStrength(unittest.TestCase):

    def test_no_data_returns_none(self):
        result = compute_validation_strength({})
        self.assertIsNone(result["score_0_100"])
        self.assertIsNone(result["label"])

    def test_five_interviews_is_medium(self):
        result = compute_validation_strength({"customer_interview_count": 5})
        self.assertGreaterEqual(result["score_0_100"], 35)

    def test_strong_evidence_is_high(self):
        result = compute_validation_strength({
            "customer_interview_count": 15,
            "pilot_users": 6,
            "pre_orders": 4,
        })
        self.assertEqual(result["label"], "high")

    def test_zero_counts_are_low(self):
        result = compute_validation_strength({
            "customer_interview_count": 0,
            "pilot_users": 0,
            "pre_orders": 0,
        })
        self.assertEqual(result["label"], "low")


# ── 3. Structural coherence ───────────────────────────────────────────

class TestStructuralCoherence(unittest.TestCase):

    def test_sarl_one_associe_flags(self):
        flags = detect_structural_coherence({
            "legal_form_type": "SARL",
            "associes": ["Ahmed"],
        })
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["type"], "sarl_insufficient_associes")

    def test_sarl_two_associes_ok(self):
        flags = detect_structural_coherence({
            "legal_form_type": "SARL",
            "associes": ["Ahmed", "Sara"],
        })
        self.assertEqual(flags, [])

    def test_suarl_two_associes_flags(self):
        flags = detect_structural_coherence({
            "legal_form_type": "SUARL",
            "associes": ["Ahmed", "Sara"],
        })
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["type"], "suarl_wrong_associes_count")

    def test_suarl_one_associe_ok(self):
        flags = detect_structural_coherence({
            "legal_form_type": "SUARL",
            "associes": ["Ahmed"],
        })
        self.assertEqual(flags, [])

    def test_no_legal_form_no_flags(self):
        self.assertEqual(detect_structural_coherence({}), [])


# ── 4. Maturity criteria results ──────────────────────────────────────

class TestMaturityCriteriaResults(unittest.TestCase):

    def test_returns_all_expected_keys(self):
        result = get_maturity_criteria_results(STAGE2_PROFILE)
        expected = [
            "target_customer_defined", "geographic_scope", "idea_is_new",
            "differentiation_claimed", "founder_has_required_skills",
            "founder_has_prior_experience", "has_paying_customers",
            "legal_form_status", "rne_registered",
        ]
        for key in expected:
            self.assertIn(key, result)

    def test_truthy_fields_resolve_correctly(self):
        result = get_maturity_criteria_results(STAGE2_PROFILE)
        self.assertTrue(result["target_customer_defined"])
        self.assertTrue(result["founder_has_prior_experience"])

    def test_missing_fields_return_none(self):
        result = get_maturity_criteria_results({})
        self.assertIsNone(result["target_customer_defined"])
        self.assertIsNone(result["legal_form_status"])

    def test_validation_strength_signal_included(self):
        result = get_maturity_criteria_results(STAGE2_PROFILE)
        self.assertIn("validation_strength_score_0_100", result)
        self.assertIn("validation_strength_label", result)


# ── 4. Unit economics ────────────────────────────────────────────────

class TestEconomics(unittest.TestCase):

    def test_gross_margin_ratio_is_0_to_1(self):
        result = compute_gross_margin_percentage(ECONOMICS_PROFILE)
        self.assertAlmostEqual(result["gross_margin_ratio"], 0.6, places=2)

    def test_gross_margin_percentage_is_0_to_100(self):
        result = compute_gross_margin_percentage(ECONOMICS_PROFILE)
        self.assertAlmostEqual(result["gross_margin_percentage"], 60.0, places=1)

    def test_selling_below_cost(self):
        result = compute_gross_margin_percentage({"selling_price": 30.0, "unit_cost": 50.0})
        self.assertFalse(result["price_covers_cost"])
        self.assertLess(result["gross_margin_ratio"], 0)

    def test_missing_price_returns_none(self):
        result = compute_gross_margin_percentage({})
        self.assertIsNone(result["gross_margin_ratio"])

    def test_monthly_fixed_costs_aggregation(self):
        result = compute_monthly_fixed_costs(ECONOMICS_PROFILE)
        self.assertAlmostEqual(result["monthly_fixed_costs"], 2200.0, places=1)

    def test_monthly_profit(self):
        # revenue=5000, variable=50×40=2000, fixed=2200 → profit=800
        result = compute_monthly_profit(ECONOMICS_PROFILE)
        self.assertAlmostEqual(result["monthly_profit"], 800.0, places=1)

    def test_breakeven_units(self):
        # fixed=2200, unit_contribution=60 → 2200/60 ≈ 36.67
        result = compute_break_even_units(ECONOMICS_PROFILE)
        self.assertTrue(result["breakeven_possible"])
        self.assertAlmostEqual(result["breakeven_units"], 36.67, places=1)

    def test_breakeven_impossible_when_no_contribution(self):
        result = compute_break_even_units({"selling_price": 40.0, "unit_cost": 40.0,
                                          "personnel_monthly_cost": 500.0})
        self.assertFalse(result["breakeven_possible"])


# ── 5. Financing ──────────────────────────────────────────────────────

class TestFinancing(unittest.TestCase):

    def test_bct_fichage_blocks(self):
        result = compute_credit_eligibility_path({
            "credit_eligibility_blockers": ["fichage_bct"],
        })
        self.assertEqual(result["credit_eligibility_path"], "none")
        self.assertEqual(result["reason"], "credit_blocked_by_bct_or_unpaid_debts")

    def test_has_guarantee_routes_to_bank(self):
        result = compute_credit_eligibility_path({"has_guarantee": True})
        self.assertEqual(result["credit_eligibility_path"], "commercial_bank")
        self.assertEqual(result["reason"], "has_guarantee")

    def test_has_premises_routes_to_bank_as_fonds_de_commerce(self):
        result = compute_credit_eligibility_path({"has_premises": True})
        self.assertEqual(result["credit_eligibility_path"], "commercial_bank")
        self.assertEqual(result["reason"], "fonds_de_commerce_guarantee")

    def test_bts_eligible(self):
        result = compute_credit_eligibility_path({
            "needs_credit": True,
            "credit_amount_needed": 80_000.0,
        })
        self.assertEqual(result["credit_eligibility_path"], "bts_fonapra")

    def test_above_bts_limit_no_guarantee_is_none(self):
        result = compute_credit_eligibility_path({
            "needs_credit": True,
            "credit_amount_needed": 200_000.0,
        })
        self.assertEqual(result["credit_eligibility_path"], "none")

    def test_minimum_credit_gap(self):
        result = compute_minimum_credit_needed({
            "initial_investment":        10_000.0,
            "personnel_monthly_cost":    500.0,
            "apport_personnel":          5_000.0,
        })
        # total = 10000 + (500 * 3) = 11500 | gap = 11500 - 5000 = 6500
        self.assertTrue(result["gap_exists"])
        self.assertAlmostEqual(result["minimum_credit_needed"], 6_500.0, places=1)

    def test_minimum_credit_no_gap_when_apport_covers(self):
        result = compute_minimum_credit_needed({
            "initial_investment": 5_000.0,
            "apport_personnel":   50_000.0,
        })
        self.assertFalse(result["gap_exists"])
        self.assertEqual(result["minimum_credit_needed"], 0.0)

    def test_opex_runway_from_field(self):
        self.assertEqual(compute_opex_runway_months({"opex_months_covered": 6}), 6.0)

    def test_opex_runway_no_financing_is_zero(self):
        self.assertEqual(compute_opex_runway_months({"has_opex_financing": False}), 0.0)


# ── 6. Classifier — evaluate_criteria & stage_classification ─────────

class TestClassifier(unittest.TestCase):

    def test_stage2_all_pass(self):
        results = evaluate_criteria("MARKET_VALIDATION", STAGE2_PROFILE)
        for r in results:
            self.assertTrue(r["value"], msg=f"{r['criterion']} failed unexpectedly")

    def test_stage2_missing_customer_validation_fails(self):
        profile = {**STAGE2_PROFILE}
        # remove all validation evidence
        profile.pop("customer_interview_count")
        results = evaluate_criteria("MARKET_VALIDATION", profile)
        validation = next(r for r in results if r["criterion"] == "customers_validation")
        self.assertIsNot(validation["value"], True)

    def test_classify_full_stage2_profile(self):
        result = stage_classification(STAGE2_PROFILE)
        self.assertEqual(result["assigned_stage"], "MARKET_VALIDATION")

    def test_classify_empty_profile_is_ideation(self):
        result = stage_classification({})
        self.assertEqual(result["assigned_stage"], "IDEATION")

    def test_stopped_at_is_set_on_failure(self):
        result = stage_classification({})
        self.assertEqual(result["stopped_at"], "MARKET_VALIDATION")

    def test_stage_criteria_returns_domain(self):
        results = evaluate_criteria("MARKET_VALIDATION", STAGE2_PROFILE)
        for r in results:
            self.assertIn("domain", r)
            self.assertIsNotNone(r["domain"])


# ── 7. Diagnostic chain ───────────────────────────────────────────────

class TestDiagnosticChain(unittest.TestCase):

    def _run_chain(self, profile):
        classification = stage_classification(profile)
        failed         = extract_failed_criteria(classification["evidence"])
        blockers       = identify_blockers(failed)
        confidence     = compute_confidence(classification["evidence"])
        return classification, failed, blockers, confidence

    def test_extract_failed_excludes_true(self):
        _, failed, _, _ = self._run_chain(STAGE2_PROFILE)
        for f in failed:
            self.assertIsNot(f["value"], True)

    def test_extract_failed_includes_stage(self):
        _, failed, _, _ = self._run_chain({})
        for f in failed:
            self.assertIn("stage", f)

    def test_identify_blockers_ranked_domains(self):
        _, _, blockers, _ = self._run_chain({})
        self.assertIn("ranked_domains", blockers)
        self.assertIn("by_domain", blockers)

    def test_confidence_all_resolved(self):
        _, _, _, confidence = self._run_chain(STAGE2_PROFILE)
        # Stage 2 evidence is all resolved (True/False, no None)
        self.assertIn(confidence["level"], ("high", "medium"))

    def test_confidence_empty_profile_is_low(self):
        _, _, _, confidence = self._run_chain({})
        self.assertEqual(confidence["level"], "low")

    def test_perception_gap_overestimate(self):
        result = detect_perception_gap(
            {"self_assessed_stage": 4},
            "MARKET_VALIDATION",   # diagnosed = stage 2
        )
        self.assertEqual(result["gap_direction"], "overestimate")
        self.assertEqual(result["gap_size"], 2)

    def test_perception_gap_aligned(self):
        result = detect_perception_gap(
            {"self_assessed_stage": 2},
            "MARKET_VALIDATION",
        )
        self.assertEqual(result["gap_direction"], "aligned")
        self.assertFalse(result["divergence"])

    def test_perception_gap_missing_self_assessment(self):
        result = detect_perception_gap({}, "IDEATION")
        self.assertIsNone(result["gap_size"])


def print_section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def print_results():
    from scorers.economics import compute_price_positioning, compute_breakeven_months
    from scorers.financing import compute_repayment_capacity_ratio
    from scorers.projections import compute_5_year_projection

    # ── Classifier ───────────────────────────────────────────────────
    print_section("CRITERIA — MARKET_VALIDATION (full Stage 2 profile)")
    for r in evaluate_criteria("MARKET_VALIDATION", STAGE2_PROFILE):
        icon = "✓" if r["value"] is True else "✗" if r["value"] is False else "?"
        print(f"  [{icon}] {r['criterion']:<30}  domain={r['domain']}")

    print_section("STAGE CLASSIFICATION")
    cls = stage_classification(STAGE2_PROFILE)
    print(f"  assigned_stage : {cls['assigned_stage']}")
    print(f"  stopped_at     : {cls['stopped_at']}")

    print_section("STAGE CLASSIFICATION — empty profile")
    cls_empty = stage_classification({})
    print(f"  assigned_stage : {cls_empty['assigned_stage']}")
    print(f"  stopped_at     : {cls_empty['stopped_at']}")
    failed = extract_failed_criteria(cls_empty["evidence"])
    print(f"  failed criteria ({len(failed)}):")
    for f in failed:
        val = "False" if f["value"] is False else "None"
        print(f"    - {f['criterion']:<30}  [{val}]  stage={f['stage']}  domain={f['domain']}")

    blockers = identify_blockers(failed)
    print(f"  ranked blocker domains : {blockers['ranked_domains']}")

    confidence = compute_confidence(cls_empty["evidence"])
    print(f"  confidence : {confidence['level']}  (score={confidence['score']},"
          f"  none={confidence['none_count']}/{confidence['total_evaluated']})")

    # ── Financial calculations ────────────────────────────────────────
    print_section("GROSS MARGIN  (selling=100, cost=40)")
    gm = compute_gross_margin_percentage(ECONOMICS_PROFILE)
    print(f"  gross_margin_percentage : {gm['gross_margin_percentage']}  (display, 0–100)")
    print(f"  gross_margin_ratio      : {gm['gross_margin_ratio']}  (comparisons, 0–1)")
    print(f"  unit_contribution       : {gm['unit_contribution']} DT")
    print(f"  price_covers_cost       : {gm['price_covers_cost']}")

    print_section("MONTHLY P&L  (revenue=5000, units=50)")
    profit = compute_monthly_profit(ECONOMICS_PROFILE)
    print(f"  monthly_revenue         : {profit['monthly_revenue']} DT")
    print(f"  monthly_variable_costs  : {profit['monthly_variable_costs']} DT")
    print(f"  monthly_fixed_costs     : {profit['monthly_fixed_costs']} DT")
    print(f"  monthly_profit          : {profit['monthly_profit']} DT")

    print_section("BREAKEVEN")
    bku = compute_break_even_units(ECONOMICS_PROFILE)
    bkm = compute_breakeven_months(ECONOMICS_PROFILE)
    print(f"  breakeven_units  : {bku['breakeven_units']} units/month")
    print(f"  breakeven_months : {bkm['breakeven_months']} months (from initial investment)")

    print_section("PRICE POSITIONING  (local=90, foreign=120)")
    pricing = compute_price_positioning({**ECONOMICS_PROFILE,
                                         "market_price_local": 90.0,
                                         "market_price_foreign": 120.0})
    print(f"  price_vs_local_market   : {pricing['price_vs_local_market']}x")
    print(f"  price_vs_foreign_market : {pricing['price_vs_foreign_market']}x")

    print_section("CREDIT ELIGIBILITY")
    cases = [
        ("BCT fichage",          {"credit_eligibility_blockers": ["fichage_bct"]}),
        ("has_guarantee",        {"has_guarantee": True}),
        ("has_premises",         {"has_premises": True}),
        ("BTS eligible 80k",     {"needs_credit": True, "credit_amount_needed": 80_000}),
        ("Above BTS, no guarantee", {"needs_credit": True, "credit_amount_needed": 200_000}),
    ]
    for label, p in cases:
        r = compute_credit_eligibility_path(p)
        print(f"  {label:<30} → {r['credit_eligibility_path']}  ({r['reason']})")

    print_section("MINIMUM CREDIT NEEDED")
    gap = compute_minimum_credit_needed({
        "initial_investment":     20_000.0,
        "personnel_monthly_cost": 1_000.0,
        "apport_personnel":       8_000.0,
    })
    print(f"  investment_needs       : {gap['investment_needs']} DT")
    print(f"  working_capital_needed : {gap['working_capital_needed']} DT  ({gap['opex_buffer_months']} months)")
    print(f"  total_financing_needs  : {gap['total_financing_needs']} DT")
    print(f"  apport_personnel       : {gap['apport_personnel']} DT")
    print(f"  minimum_credit_needed  : {gap['minimum_credit_needed']} DT")
    print(f"  gap_exists             : {gap['gap_exists']}")

    print_section("REPAYMENT CAPACITY")
    rep_cases = [
        ("Existing credit 300/mo",   {"existing_credit_monthly_payment": 300.0, **ECONOMICS_PROFILE}),
        ("Requested 50k over 5y",    {"credit_amount_needed": 50_000.0, "credit_duration_years": 5, **ECONOMICS_PROFILE}),
    ]
    for label, p in rep_cases:
        r = compute_repayment_capacity_ratio(p)
        flag = "⚠ overloaded" if (r["repayment_capacity_ratio"] or 0) > 0.40 else "ok"
        print(f"  {label:<35} ratio={r['repayment_capacity_ratio']}  {flag}")

    print_section("5-YEAR PROJECTION")
    proj = compute_5_year_projection({**ECONOMICS_PROFILE, "ca_growth_rate": 0.10})
    for row in proj["projection_5y"]:
        if row.get("missing_data"):
            print(f"  Year {row['year']}: missing data")
        else:
            print(f"  Year {row['year']}: CA={row['ca']:>10.0f} DT  "
                  f"net_income={row['net_income']:>9.0f} DT  "
                  f"cash_flow={row['cash_flow']:>9.0f} DT")
    print(f"  VAN (10%) : {proj['van_5_years']} DT")

    print_section("PERCEPTION GAP")
    for self_stage, diagnosed in [(4, "MARKET_VALIDATION"), (2, "MARKET_VALIDATION"), (1, "GROWTH")]:
        r = detect_perception_gap({"self_assessed_stage": self_stage}, diagnosed)
        print(f"  self={self_stage}  diagnosed={r['diagnosed_stage']}  "
              f"gap={r['gap_size']}  direction={r['gap_direction']}")

    print()


if __name__ == "__main__":
    print_results()
    unittest.main(verbosity=2)
