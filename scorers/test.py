"""
scorers/test.py — unit tests for the LeadIt scoring layer.

Covers: scoring_utils, market, commercial, innovation, scalability, green,
        and score_project() end-to-end.
"""

import io
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

# ── path setup ────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "criteria"))

for mod in ["django", "django.db", "django.db.models", "projects", "projects.models"]:
    sys.modules[mod] = MagicMock()

# ── imports ───────────────────────────────────────────────────────────────
from scorers.scoring_utils   import score_leaf, rollup, build_result
from scorers.market          import score_market
from scorers.commercial      import score_commercial
from scorers.innovation      import score_innovation
from scorers.scalability     import score_scalability
from scorers.green           import score_green
from diagnostic.scoring      import score_project
from diagnostic.metrics      import derive_all_metrics
from diagnostic.services     import stage_classification, detect_perception_gap


# ── fixtures ──────────────────────────────────────────────────────────────

STRONG_PROFILE = {
    # stage self-assessment
    "self_assessed_stage":        "STRUCTURATION",
    # economics
    "selling_price":              100.0,
    "unit_cost":                  40.0,
    "expected_monthly_units":     50,
    "monthly_revenue":            5_000.0,
    "personnel_monthly_cost":     1_500.0,
    "rent_monthly":               500.0,
    "other_fixed_costs_monthly":  200.0,
    "initial_investment":         30_000.0,
    "ca_growth_rate":             0.10,
    "market_price_local":         90.0,
    "market_price_foreign":       120.0,
    # financing
    "needs_credit":               True,
    "credit_amount_needed":       25_000.0,
    "has_guarantee":              True,
    "apport_personnel":           10_000.0,
    "opex_months_covered":        6,
    # innovation / commercial
    "idea_is_new":                True,
    "foreign_model_studied":      True,
    "differentiation_claimed":    True,
    "gerant":                     "Ahmed Ben Ali",
    # scalability
    "team_core_complete":         True,
    "associes":                   ["Ahmed", "Sara"],
    # green
    "environmental_impact_type":        "économie_énergie",
    "environmental_impact_description": "Réduction de 30% de la consommation énergétique.",
    "waste_reduction_measures":         "Tri et partenariat avec recycleur local.",
    "energy_reduction_measures":        "Panneaux solaires sur le toit.",
    "resource_efficiency_measures":     "Achat groupé de matières premières.",
    "circular_practices_described":     "Réutilisation des emballages fournisseurs.",
    "sdg_alignment":                    ["7", "12"],
    "sdg_evidence":                     "40% de l'énergie issue du renouvelable.",
}

WEAK_PROFILE = {
    "self_assessed_stage":         "FUNDRAISING",
    "selling_price":               30.0,
    "unit_cost":                   40.0,   # selling below cost → negative margin
    "monthly_revenue":             500.0,
    "needs_credit":                True,
    "credit_eligibility_blockers": ["fichage_bct"],
    "idea_is_new":                 False,
    "differentiation_claimed":     False,
}

METRICS_STRONG = derive_all_metrics(STRONG_PROFILE)
METRICS_WEAK   = derive_all_metrics(WEAK_PROFILE)


def get_leaf(result, criterion):
    for lf in result["leaves"]:
        if lf["criterion"] == criterion:
            return lf
    return None


# ── 1. ScoringUtils ───────────────────────────────────────────────────────

class TestScoringUtils(unittest.TestCase):

    def test_higher_is_better_match(self):
        # 8 ≥ 5 → 7
        self.assertEqual(score_leaf(8.0, [(10, 10), (5, 7), (0, 4)]), 7.0)

    def test_higher_is_better_top(self):
        self.assertEqual(score_leaf(10.0, [(10, 10), (5, 7), (0, 4)]), 10.0)

    def test_lower_is_better_match(self):
        # 8 ≤ 12 → 8
        self.assertEqual(score_leaf(8.0, [(6, 10), (12, 8), (24, 5)], higher_is_better=False), 8.0)

    def test_lower_is_better_top(self):
        # 4 ≤ 6 → 10
        self.assertEqual(score_leaf(4.0, [(6, 10), (12, 8), (24, 5)], higher_is_better=False), 10.0)

    def test_lower_is_better_fallback(self):
        # 50 > all thresholds → last entry = 5
        self.assertEqual(score_leaf(50.0, [(6, 10), (12, 8), (24, 5)], higher_is_better=False), 5.0)

    def test_none_returns_none(self):
        self.assertIsNone(score_leaf(None, [(10, 10), (0, 4)]))

    def test_rollup_weighted_average(self):
        leaves = [{"score": 10.0, "weight": 0.60}, {"score": 4.0, "weight": 0.40}]
        # (10*0.6 + 4*0.4) / 1.0 = 7.6
        self.assertAlmostEqual(rollup(leaves), 7.6, places=2)

    def test_rollup_renormalizes_over_non_none(self):
        # None leaf is excluded; weight renormalizes to 0.5 only
        leaves = [{"score": 10.0, "weight": 0.50}, {"score": None, "weight": 0.50}]
        self.assertAlmostEqual(rollup(leaves), 10.0, places=2)

    def test_rollup_all_none_returns_none(self):
        leaves = [{"score": None, "weight": 0.5}, {"score": None, "weight": 0.5}]
        self.assertIsNone(rollup(leaves))

    def test_build_result_floor_met(self):
        result = build_result([{"score": 8.0, "weight": 1.0}], floor=5.0)
        self.assertTrue(result["floor_met"])
        self.assertEqual(result["score"], 8.0)

    def test_build_result_floor_not_met(self):
        result = build_result([{"score": 3.0, "weight": 1.0}], floor=5.0)
        self.assertFalse(result["floor_met"])

    def test_build_result_all_none_floor_is_none(self):
        result = build_result([{"score": None, "weight": 1.0}], floor=5.0)
        self.assertIsNone(result["floor_met"])
        self.assertIsNone(result["score"])


# ── 2. Market scorer ──────────────────────────────────────────────────────

class TestMarketScorer(unittest.TestCase):

    def test_structure_keys(self):
        result = score_market(STRONG_PROFILE, METRICS_STRONG)
        for key in ("score", "floor", "floor_met", "leaves"):
            self.assertIn(key, result)

    def test_floor_is_5(self):
        self.assertEqual(score_market(STRONG_PROFILE, METRICS_STRONG)["floor"], 5.0)

    def test_strong_profile_floor_met(self):
        self.assertTrue(score_market(STRONG_PROFILE, METRICS_STRONG)["floor_met"])

    def test_negative_margin_viability_is_zero(self):
        lf = get_leaf(score_market(WEAK_PROFILE, METRICS_WEAK), "gross_margin_viability")
        self.assertEqual(lf["score"], 0.0)

    def test_high_margin_viability_scores_10(self):
        m = {**METRICS_STRONG, "gross_margin_ratio": 0.60}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "gross_margin_viability")
        self.assertEqual(lf["score"], 10.0)

    def test_medium_margin_viability_scores_7(self):
        m = {**METRICS_STRONG, "gross_margin_ratio": 0.35}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "gross_margin_viability")
        self.assertEqual(lf["score"], 7.0)

    def test_low_margin_viability_scores_4(self):
        m = {**METRICS_STRONG, "gross_margin_ratio": 0.20}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "gross_margin_viability")
        self.assertEqual(lf["score"], 4.0)

    def test_breakeven_12mo_scores_10(self):
        m = {**METRICS_STRONG, "breakeven_months": 12}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "breakeven_reachability")
        self.assertEqual(lf["score"], 10.0)

    def test_breakeven_over_48mo_scores_3(self):
        # 60 > all thresholds → score_leaf fallback = last entry (48→3)
        m = {**METRICS_STRONG, "breakeven_months": 60}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "breakeven_reachability")
        self.assertEqual(lf["score"], 3.0)

    def test_opex_6mo_scores_10(self):
        m = {**METRICS_STRONG, "opex_months_covered": 6}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "opex_runway")
        self.assertEqual(lf["score"], 10.0)

    def test_opex_zero_scores_0(self):
        m = {**METRICS_STRONG, "opex_months_covered": 0}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "opex_runway")
        self.assertEqual(lf["score"], 0.0)

    def test_commercial_bank_credit_scores_10(self):
        m = {**METRICS_STRONG, "credit_eligibility_path": "commercial_bank"}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "credit_access")
        self.assertEqual(lf["score"], 10.0)

    def test_bts_credit_scores_7(self):
        m = {**METRICS_STRONG, "credit_eligibility_path": "bts_fonapra"}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "credit_access")
        self.assertEqual(lf["score"], 7.0)

    def test_blocked_credit_scores_0(self):
        p = {**STRONG_PROFILE, "needs_credit": True}
        m = {**METRICS_STRONG, "credit_eligibility_path": "none"}
        lf = get_leaf(score_market(p, m), "credit_access")
        self.assertEqual(lf["score"], 0.0)

    def test_no_credit_needed_scores_9(self):
        p = {**STRONG_PROFILE, "needs_credit": False}
        m = {**METRICS_STRONG, "credit_eligibility_path": "none"}
        lf = get_leaf(score_market(p, m), "credit_access")
        self.assertEqual(lf["score"], 9.0)

    def test_no_investment_gap_scores_10(self):
        m = {**METRICS_STRONG, "credit_gap_exists": False}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "investment_gap_covered")
        self.assertEqual(lf["score"], 10.0)

    def test_gap_covered_by_plan_scores_8(self):
        m = {**METRICS_STRONG, "credit_gap_exists": True, "planned_credit_covers_gap": True}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "investment_gap_covered")
        self.assertEqual(lf["score"], 8.0)

    def test_gap_not_covered_scores_3(self):
        m = {**METRICS_STRONG, "credit_gap_exists": True, "planned_credit_covers_gap": False}
        lf = get_leaf(score_market(STRONG_PROFILE, m), "investment_gap_covered")
        self.assertEqual(lf["score"], 3.0)

    def test_weak_profile_floor_not_met(self):
        self.assertFalse(score_market(WEAK_PROFILE, METRICS_WEAK)["floor_met"])


# ── 3. Commercial scorer ──────────────────────────────────────────────────

class TestCommercialScorer(unittest.TestCase):

    def test_structure_keys(self):
        result = score_commercial(STRONG_PROFILE, METRICS_STRONG)
        for key in ("score", "floor", "floor_met", "leaves"):
            self.assertIn(key, result)

    def test_floor_is_4(self):
        self.assertEqual(score_commercial(STRONG_PROFILE, METRICS_STRONG)["floor"], 4.0)

    def test_negative_margin_pricing_coherence_zero(self):
        m = {**METRICS_STRONG, "gross_margin_ratio": -0.10}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "pricing_coherence")
        self.assertEqual(lf["score"], 0.0)

    def test_high_margin_pricing_coherence_10(self):
        m = {**METRICS_STRONG, "gross_margin_ratio": 0.60}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "pricing_coherence")
        self.assertEqual(lf["score"], 10.0)

    def test_local_price_parity_scores_10(self):
        m = {**METRICS_STRONG, "price_vs_local_market": 1.0}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "local_price_positioning")
        self.assertEqual(lf["score"], 10.0)

    def test_local_price_40pct_above_market_scores_4(self):
        # 1.40 is inclusive upper bound of third tier (1.25 < r <= 1.40) -> 4.0
        m = {**METRICS_STRONG, "price_vs_local_market": 1.40}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "local_price_positioning")
        self.assertEqual(lf["score"], 4.0)

    def test_local_price_50pct_above_market_scores_1(self):
        # 1.50 > 1.40 falls outside all bands -> else -> 1.0
        m = {**METRICS_STRONG, "price_vs_local_market": 1.50}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "local_price_positioning")
        self.assertEqual(lf["score"], 1.0)

    def test_foreign_price_below_80pct_scores_10(self):
        m = {**METRICS_STRONG, "price_vs_foreign_market": 0.75}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "foreign_price_positioning")
        self.assertEqual(lf["score"], 10.0)

    def test_foreign_price_above_120pct_scores_2(self):
        m = {**METRICS_STRONG, "price_vs_foreign_market": 1.30}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "foreign_price_positioning")
        self.assertEqual(lf["score"], 2.0)

    def test_volume_2x_breakeven_scores_10(self):
        # expected=50, breakeven=25 → ratio=2.0 → 10
        m = {**METRICS_STRONG, "breakeven_units": 25.0}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "volume_vs_breakeven")
        self.assertEqual(lf["score"], 10.0)

    def test_volume_below_breakeven_scores_2(self):
        # expected=50, breakeven=100 → ratio=0.5 → 2
        m = {**METRICS_STRONG, "breakeven_units": 100.0}
        lf = get_leaf(score_commercial(STRONG_PROFILE, m), "volume_vs_breakeven")
        self.assertEqual(lf["score"], 2.0)

    def test_gerant_set_scores_10(self):
        lf = get_leaf(score_commercial(STRONG_PROFILE, METRICS_STRONG), "management_identified")
        self.assertEqual(lf["score"], 10.0)

    def test_gerant_missing_scores_0(self):
        p = {**STRONG_PROFILE, "gerant": None}
        lf = get_leaf(score_commercial(p, METRICS_STRONG), "management_identified")
        self.assertEqual(lf["score"], 0.0)

    def test_strong_profile_floor_met(self):
        self.assertTrue(score_commercial(STRONG_PROFILE, METRICS_STRONG)["floor_met"])


# ── 4. Innovation scorer ──────────────────────────────────────────────────

class TestInnovationScorer(unittest.TestCase):

    def test_structure_keys(self):
        result = score_innovation(STRONG_PROFILE, METRICS_STRONG)
        for key in ("score", "floor", "floor_met", "leaves"):
            self.assertIn(key, result)

    def test_new_idea_scores_10(self):
        lf = get_leaf(score_innovation({"idea_is_new": True}, {}), "idea_novelty")
        self.assertEqual(lf["score"], 10.0)

    def test_adapted_idea_scores_4(self):
        lf = get_leaf(score_innovation({"idea_is_new": False}, {}), "idea_novelty")
        self.assertEqual(lf["score"], 4.0)

    def test_missing_idea_field_is_none(self):
        lf = get_leaf(score_innovation({}, {}), "idea_novelty")
        self.assertIsNone(lf["score"])

    def test_research_done_scores_10(self):
        lf = get_leaf(score_innovation({"foreign_model_studied": True}, {}), "market_research_depth")
        self.assertEqual(lf["score"], 10.0)

    def test_no_research_scores_2(self):
        lf = get_leaf(score_innovation({"foreign_model_studied": False}, {}), "market_research_depth")
        self.assertEqual(lf["score"], 2.0)

    def test_differentiation_claimed_caps_at_8(self):
        # claimed ≠ proven — max is 8, not 10
        lf = get_leaf(score_innovation({"differentiation_claimed": True}, {}), "differentiation_strength")
        self.assertEqual(lf["score"], 8.0)
        self.assertLess(lf["score"], 10.0)

    def test_no_differentiation_scores_0(self):
        lf = get_leaf(score_innovation({"differentiation_claimed": False}, {}), "differentiation_strength")
        self.assertEqual(lf["score"], 0.0)

    def test_price_below_80pct_foreign_scores_10(self):
        lf = get_leaf(score_innovation({}, {"price_vs_foreign_market": 0.75}), "price_advantage_vs_foreign")
        self.assertEqual(lf["score"], 10.0)

    def test_price_above_120pct_foreign_scores_2(self):
        lf = get_leaf(score_innovation({}, {"price_vs_foreign_market": 1.30}), "price_advantage_vs_foreign")
        self.assertEqual(lf["score"], 2.0)

    def test_strong_profile_floor_met(self):
        self.assertTrue(score_innovation(STRONG_PROFILE, METRICS_STRONG)["floor_met"])

    def test_empty_profile_score_is_none(self):
        result = score_innovation({}, {})
        self.assertIsNone(result["score"])


# ── 5. Scalability scorer ─────────────────────────────────────────────────

class TestScalabilityScorer(unittest.TestCase):

    def test_structure_keys(self):
        result = score_scalability(STRONG_PROFILE, METRICS_STRONG)
        for key in ("score", "floor", "floor_met", "leaves"):
            self.assertIn(key, result)

    def test_margin_above_55pct_scores_10(self):
        m = {**METRICS_STRONG, "gross_margin_ratio": 0.60}
        lf = get_leaf(score_scalability(STRONG_PROFILE, m), "unit_economics_at_scale")
        self.assertEqual(lf["score"], 10.0)

    def test_margin_40pct_scores_8(self):
        m = {**METRICS_STRONG, "gross_margin_ratio": 0.40}
        lf = get_leaf(score_scalability(STRONG_PROFILE, m), "unit_economics_at_scale")
        self.assertEqual(lf["score"], 8.0)

    def test_margin_below_10pct_scores_0(self):
        m = {**METRICS_STRONG, "gross_margin_ratio": 0.05}
        lf = get_leaf(score_scalability(STRONG_PROFILE, m), "unit_economics_at_scale")
        self.assertEqual(lf["score"], 0.0)

    def test_complete_team_two_associes_scores_10(self):
        lf = get_leaf(score_scalability(STRONG_PROFILE, METRICS_STRONG), "team_depth")
        self.assertEqual(lf["score"], 10.0)

    def test_complete_team_no_associes_scores_7(self):
        p = {**STRONG_PROFILE, "associes": []}
        lf = get_leaf(score_scalability(p, METRICS_STRONG), "team_depth")
        self.assertEqual(lf["score"], 7.0)

    def test_incomplete_team_two_associes_scores_5(self):
        p = {**STRONG_PROFILE, "team_core_complete": False}
        lf = get_leaf(score_scalability(p, METRICS_STRONG), "team_depth")
        self.assertEqual(lf["score"], 5.0)

    def test_incomplete_team_no_associes_scores_2(self):
        p = {**STRONG_PROFILE, "team_core_complete": False, "associes": []}
        lf = get_leaf(score_scalability(p, METRICS_STRONG), "team_depth")
        self.assertEqual(lf["score"], 2.0)

    def test_volume_3x_breakeven_scores_10(self):
        # expected=50, breakeven=16 → ratio≈3.1 → 10
        m = {**METRICS_STRONG, "breakeven_units": 16.0}
        lf = get_leaf(score_scalability(STRONG_PROFILE, m), "volume_headroom")
        self.assertEqual(lf["score"], 10.0)

    def test_volume_below_breakeven_scores_1(self):
        m = {**METRICS_STRONG, "breakeven_units": 100.0}
        lf = get_leaf(score_scalability(STRONG_PROFILE, m), "volume_headroom")
        self.assertEqual(lf["score"], 1.0)

    def test_low_fixed_ratio_scores_10(self):
        # fixed=1000, profit=4000, variable=1000 → revenue=6000, ratio=0.167 → 10
        m = {**METRICS_STRONG, "monthly_fixed_costs": 1_000.0,
             "monthly_profit": 4_000.0, "monthly_variable_costs": 1_000.0}
        lf = get_leaf(score_scalability(STRONG_PROFILE, m), "fixed_cost_leverage")
        self.assertEqual(lf["score"], 10.0)

    def test_high_fixed_ratio_scores_1(self):
        # fixed=4000, profit=200, variable=800 → revenue=5000, ratio=0.80 → 1
        m = {**METRICS_STRONG, "monthly_fixed_costs": 4_000.0,
             "monthly_profit": 200.0, "monthly_variable_costs": 800.0}
        lf = get_leaf(score_scalability(STRONG_PROFILE, m), "fixed_cost_leverage")
        self.assertEqual(lf["score"], 1.0)

    def test_strong_profile_floor_met(self):
        self.assertTrue(score_scalability(STRONG_PROFILE, METRICS_STRONG)["floor_met"])


# ── 6. Green scorer ───────────────────────────────────────────────────────

class TestGreenScorer(unittest.TestCase):

    def test_structure_keys(self):
        result = score_green(STRONG_PROFILE, {})
        for key in ("score", "floor", "floor_met", "leaves"):
            self.assertIn(key, result)

    def test_impact_with_description_scores_10(self):
        p = {"environmental_impact_type": "économie_énergie",
             "environmental_impact_description": "Impact détaillé."}
        lf = get_leaf(score_green(p, {}), "impact_declared")
        self.assertEqual(lf["score"], 10.0)

    def test_impact_type_only_scores_6(self):
        p = {"environmental_impact_type": "économie_énergie"}
        lf = get_leaf(score_green(p, {}), "impact_declared")
        self.assertEqual(lf["score"], 6.0)

    def test_aucun_impact_scores_0(self):
        lf = get_leaf(score_green({"environmental_impact_type": "aucun"}, {}), "impact_declared")
        self.assertEqual(lf["score"], 0.0)

    def test_no_impact_type_is_none(self):
        lf = get_leaf(score_green({}, {}), "impact_declared")
        self.assertIsNone(lf["score"])

    def test_measure_described_scores_10(self):
        lf = get_leaf(score_green({"waste_reduction_measures": "Tri des déchets."}, {}), "waste_reduction")
        self.assertEqual(lf["score"], 10.0)

    def test_measure_none_is_none(self):
        lf = get_leaf(score_green({}, {}), "waste_reduction")
        self.assertIsNone(lf["score"])

    def test_measure_empty_string_scores_0(self):
        lf = get_leaf(score_green({"waste_reduction_measures": ""}, {}), "waste_reduction")
        self.assertEqual(lf["score"], 0.0)

    def test_sdg_with_evidence_scores_10(self):
        p = {"sdg_alignment": ["7", "12"], "sdg_evidence": "40% renouvelable."}
        lf = get_leaf(score_green(p, {}), "sdg_commitment")
        self.assertEqual(lf["score"], 10.0)

    def test_sdg_without_evidence_scores_6(self):
        lf = get_leaf(score_green({"sdg_alignment": ["7"]}, {}), "sdg_commitment")
        self.assertEqual(lf["score"], 6.0)

    def test_empty_sdg_list_scores_0(self):
        lf = get_leaf(score_green({"sdg_alignment": []}, {}), "sdg_commitment")
        self.assertEqual(lf["score"], 0.0)

    def test_full_green_profile_floor_met(self):
        self.assertTrue(score_green(STRONG_PROFILE, {})["floor_met"])

    def test_empty_profile_score_is_none(self):
        self.assertIsNone(score_green({}, {})["score"])


# ── 7. score_project — integration ───────────────────────────────────────

class TestScoreProject(unittest.TestCase):

    def setUp(self):
        self.result = score_project(STRONG_PROFILE)

    def test_returns_five_dimensions(self):
        for dim in ("market", "commercial", "innovation", "scalability", "green"):
            self.assertIn(dim, self.result["scores"])

    def test_metrics_bundle_included(self):
        self.assertIn("metrics", self.result)
        self.assertIn("gross_margin_ratio", self.result["metrics"])

    def test_all_dimension_structures_valid(self):
        for dim, engine in self.result["scores"].items():
            for key in ("score", "floor", "floor_met", "leaves"):
                self.assertIn(key, engine, msg=f"{dim} missing key {key}")

    def test_scores_are_0_to_10_or_none(self):
        for dim, engine in self.result["scores"].items():
            s = engine["score"]
            if s is not None:
                self.assertGreaterEqual(s, 0.0, msg=f"{dim} score below 0")
                self.assertLessEqual(s, 10.0, msg=f"{dim} score above 10")

    def test_strong_profile_market_floor_met(self):
        self.assertTrue(self.result["scores"]["market"]["floor_met"])

    def test_strong_profile_green_scores(self):
        self.assertIsNotNone(self.result["scores"]["green"]["score"])

    def test_weak_profile_market_floor_not_met(self):
        weak = score_project(WEAK_PROFILE)
        self.assertFalse(weak["scores"]["market"]["floor_met"])

    def test_gross_margin_ratio_same_across_engines(self):
        """Compute once: every engine's leaf reads the same gmr from the shared bundle."""
        gmr_bundle = self.result["metrics"]["gross_margin_ratio"]
        pairs = {
            "market":      "gross_margin_viability",
            "commercial":  "pricing_coherence",
            "scalability": "unit_economics_at_scale",
        }
        for dim, criterion in pairs.items():
            lf = get_leaf(self.result["scores"][dim], criterion)
            self.assertEqual(
                lf["evidence"]["gross_margin_ratio"], gmr_bundle,
                msg=f"{dim}/{criterion} used a different gmr than the shared bundle",
            )

    def test_leaves_have_evidence_and_justification(self):
        for dim, engine in self.result["scores"].items():
            for lf in engine["leaves"]:
                self.assertIn("evidence", lf, msg=f"{dim}/{lf['criterion']} missing evidence")
                self.assertIn("justification", lf, msg=f"{dim}/{lf['criterion']} missing justification")


# ── print_results ─────────────────────────────────────────────────────────

def print_section(title):
    print(f"\n{'-' * 62}")
    print(f"  {title}")
    print('-' * 62)


def print_results():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for label, profile in [("STRONG", STRONG_PROFILE), ("WEAK", WEAK_PROFILE)]:
        print_section(f"SCORE PROJECT -- {label} profile")
        result = score_project(profile)
        m = result["metrics"]

        # ── Stage diagnosis ───────────────────────────────────────────────
        cl  = stage_classification(profile)
        gap = detect_perception_gap(profile, cl["assigned_stage"])

        declared  = gap["self_assessed_stage"]   # int or None
        diagnosed = gap["diagnosed_stage"]        # int or None

        print(f"\n  STAGE DIAGNOSIS")
        print(f"    Declared by user   : {profile.get('self_assessed_stage', 'N/A')!r}  (position {declared})")
        print(f"    Concluded by engine: {cl['assigned_stage']}  (position {diagnosed})")
        if gap["divergence"] is None:
            print(f"    Perception gap     : unknown  (no self-assessment provided)")
        elif gap["divergence"]:
            direction = "over-estimated" if declared > diagnosed else "under-estimated"
            print(f"    Perception gap     : {gap['gap_size']} stage(s) -- user {direction}")
        else:
            print(f"    Perception gap     : none  (accurate self-assessment)")
        if cl["stopped_at"]:
            print(f"    Stopped at         : {cl['stopped_at']}")

        print(f"\n  STAGE EVIDENCE")
        for stage, criteria_list in cl["evidence"].items():
            all_pass = bool(criteria_list) and all(item["value"] is True for item in criteria_list)
            marker = "+" if all_pass else "x"
            print(f"    [{marker}] {stage}")
            for item in criteria_list:
                v   = item["value"]
                sym = "+" if v is True else ("?" if v is None else "x")
                domain = f"  [{item['domain']}]" if item.get("domain") else ""
                print(f"          [{sym}] {item['criterion']:<40}  {str(v):<5}{domain}")

        # ── Metrics bundle ────────────────────────────────────────────────
        print(f"\n  METRICS BUNDLE")
        print(f"    gross_margin_ratio      : {m['gross_margin_ratio']}")
        print(f"    breakeven_months        : {m['breakeven_months']}")
        print(f"    opex_months_covered     : {m['opex_months_covered']}")
        print(f"    credit_eligibility_path : {m['credit_eligibility_path']}")
        print(f"    credit_gap_exists       : {m['credit_gap_exists']}")
        print(f"    van_5_years             : {m['van_5_years']} DT")

        # ── Scoring engines ───────────────────────────────────────────────
        for dim in ("market", "commercial", "innovation", "scalability", "green"):
            eng = result["scores"][dim]
            met = "+" if eng["floor_met"] else ("x" if eng["floor_met"] is False else "?")
            score_str = f"{eng['score']:.2f}" if eng["score"] is not None else "None"
            print(f"\n  [{met}] {dim.upper():<12}  score={score_str}  floor={eng['floor']}")
            for lf in eng["leaves"]:
                s = f"{lf['score']:>4.1f}" if lf["score"] is not None else "None"
                print(f"        {s}  (w={lf['weight']:.2f})  {lf['criterion']}")
                print(f"             {lf['justification']}")
                print(f"             evidence: {lf['evidence']}")
    print()


if __name__ == "__main__":
    # Capture print_results() output, write to stdout AND a timestamped log file
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    buf = io.StringIO()
    _real_stdout = sys.stdout

    class _Tee:
        def write(self, s):
            _real_stdout.write(s)
            buf.write(s)
        def flush(self):
            _real_stdout.flush()

    sys.stdout = _Tee()
    print_results()
    sys.stdout = _real_stdout

    logs_dir = os.path.join(ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = os.path.join(logs_dir, f"score_test_{ts}.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print(f"  log saved -> {log_path}\n")

    unittest.main(verbosity=2)
