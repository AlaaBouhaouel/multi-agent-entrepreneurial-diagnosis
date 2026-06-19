"""
intake_routing.py

Non-classifier intake question blocks for LeadIt.

These questions are asked during intake and written to the shared project
profile, but they do NOT affect maturity stage classification.
The classifier reads only fields tagged "classifier" in criteria_nested.py.

Every question here carries:
  consumers       : ["roadmap_eligibility" | "feasibility" | "scoring:<dim>"]
                    — never "classifier"
  intake_condition: the branch condition that must be met before asking
  field           : the profile field this question fills
  field_type      : "float" | "int" | "bool" | "string" | "list" | "enum"
  computed_by     : optional — downstream computed fields this question feeds
  coherence_check : optional — flags a contradiction in the Étude de Projet
                    view when the answer conflicts with a related field

Organisation
------------
Blocks are grouped by the stage during which they fire.
The intake engine calls get_routing_block(stage) to retrieve all non-classifier
questions relevant after the stage's classifier criteria are collected.

Blocks defined here
-------------------
MARKET_VALIDATION:
  UNIT_ECONOMICS_BLOCK    — selling_price, unit_cost, expected_monthly_units,
                            market_price_local, market_price_foreign.
                            Feeds: gross_margin_percentage, price_vs_local_market,
                            price_vs_foreign_market, breakeven_units, VAN.

STRUCTURATION:
  CHARGES_BLOCK           — fixed costs, personnel, rent, equipment, investment,
                            opex runway, credit situation.
                            Feeds: monthly_fixed_costs, breakeven_months,
                            repayment_capacity_ratio, credit_eligibility_path,
                            5-year projection.
  LEGAL_BLOCK (Part B.2)  — legal_form_type, associes, gerant, needs_premises,
                            has_premises.

Note: fields that are `computed` (gross_margin_percentage, van_5_years, etc.)
are never asked directly — they are derived by calculations.py from the `asked`
fields collected here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


IntakeQuestion = Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# MARKET_VALIDATION — unit economics block
# Fires unconditionally after market validation classifier questions.
# These are the raw inputs that feed every computed financial metric.
# ─────────────────────────────────────────────────────────────────────────────

UNIT_ECONOMICS_BLOCK: List[IntakeQuestion] = [
    {
        "field":              "selling_price",
        "label_fr":           "Prix de vente unitaire",
        "field_type":         "float",
        "consumers":          ["scoring:market", "scoring:commercial", "scoring:scalability", "feasibility"],
        "computed_by":        ["gross_margin_percentage", "price_vs_local_market", "price_vs_foreign_market",
                               "breakeven_units", "van_5_years"],
        "intake_question_fr": "À quel prix comptez-vous vendre votre produit ou service (en DT) ?",
        "intake_condition":   None,
    },
    {
        "field":              "unit_cost",
        "label_fr":           "Coût de revient unitaire",
        "field_type":         "float",
        "consumers":          ["scoring:market", "scoring:commercial", "scoring:scalability", "feasibility"],
        "computed_by":        ["gross_margin_percentage", "unit_contribution", "breakeven_units"],
        "intake_question_fr": (
            "Combien vous coûte la production ou la livraison d'une unité (en DT) ? "
            "(matières premières, emballage, transport, etc.)"
        ),
        "intake_condition":   None,
    },
    {
        "field":              "expected_monthly_units",
        "label_fr":           "Volume de ventes mensuel prévu",
        "field_type":         "int",
        "consumers":          ["scoring:market", "scoring:scalability", "feasibility"],
        "computed_by":        ["breakeven_units", "monthly_revenue", "van_5_years"],
        "intake_question_fr": "Combien d'unités pensez-vous vendre par mois ?",
        "intake_condition":   None,
    },
    {
        "field":              "market_price_local",
        "label_fr":           "Prix du marché local",
        "field_type":         "float",
        "consumers":          ["scoring:commercial", "scoring:innovation"],
        "computed_by":        ["price_vs_local_market"],
        "intake_question_fr": (
            "Quel est le prix du même produit ou service sur le marché tunisien ? "
            "Laissez vide si ce produit n'existe pas encore localement."
        ),
        "intake_condition":   None,
        "nullable":           True,
    },
    {
        "field":              "market_price_foreign",
        "label_fr":           "Prix du marché étranger",
        "field_type":         "float",
        "consumers":          ["scoring:commercial", "scoring:innovation"],
        "computed_by":        ["price_vs_foreign_market"],
        "intake_question_fr": (
            "Si ce produit existe à l'étranger, quel est son prix (en équivalent DT) ? "
            "Laissez vide si non applicable."
        ),
        "intake_condition": {
            "field":       "idea_is_new",
            "value":       False,
            "description": "Ask only if idea_is_new = False (concept inspired from abroad).",
        },
        "nullable":           True,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURATION — charges & financing block
# Fires after structuration classifier questions.
# Builds the full cost structure needed for the 5-year projection.
# ─────────────────────────────────────────────────────────────────────────────

CHARGES_BLOCK: List[IntakeQuestion] = [
    # ── Fixed costs ──────────────────────────────────────────────────────────
    {
        "field":              "personnel_monthly_cost",
        "label_fr":           "Charges salariales mensuelles",
        "field_type":         "float",
        "consumers":          ["scoring:market", "scoring:scalability", "feasibility"],
        "computed_by":        ["monthly_fixed_costs", "breakeven_units", "van_5_years"],
        "intake_question_fr": (
            "Quel est le coût salarial mensuel total estimé (en DT, charges sociales comprises) ? "
            "Incluez tous les employés hors fondateurs non rémunérés."
        ),
        "intake_condition":   None,
    },
    {
        "field":              "rent_monthly",
        "label_fr":           "Loyer mensuel",
        "field_type":         "float",
        "consumers":          ["scoring:market", "scoring:scalability", "feasibility"],
        "computed_by":        ["monthly_fixed_costs"],
        "intake_question_fr": "Quel est votre loyer mensuel (local, atelier, bureau) en DT ? Mettez 0 si vous travaillez depuis chez vous.",
        "intake_condition":   None,
    },
    {
        "field":              "other_fixed_costs_monthly",
        "label_fr":           "Autres charges fixes mensuelles",
        "field_type":         "float",
        "consumers":          ["scoring:market", "scoring:scalability", "feasibility"],
        "computed_by":        ["monthly_fixed_costs"],
        "intake_question_fr": (
            "Autres charges fixes mensuelles estimées (eau, électricité, internet, assurance, etc.) en DT ?"
        ),
        "intake_condition":   None,
    },
    # ── Equipment & investment ────────────────────────────────────────────────
    {
        "field":              "initial_investment",
        "label_fr":           "Investissement initial",
        "field_type":         "float",
        "consumers":          ["scoring:market", "feasibility"],
        "computed_by":        ["breakeven_months", "van_5_years"],
        "intake_question_fr": "Quel est l'investissement initial nécessaire pour démarrer (en DT) ? (équipements, aménagement, stock de départ, etc.)",
        "intake_condition":   None,
    },
    {
        "field":              "equipment_investment",
        "label_fr":           "Coût total de l'équipement",
        "field_type":         "float",
        "consumers":          ["feasibility"],
        "computed_by":        ["dotation_amortissement"],
        "intake_question_fr": "Quel est le coût total de l'équipement ou du matériel nécessaire (en DT) ?",
        "intake_condition":   None,
        "nullable":           True,
    },
    {
        "field":              "equipment_lifespan_years",
        "label_fr":           "Durée d'amortissement de l'équipement",
        "field_type":         "int",
        "consumers":          ["feasibility"],
        "computed_by":        ["dotation_amortissement"],
        "intake_question_fr": "Sur combien d'années cet équipement est-il utilisable ? (durée d'amortissement)",
        "intake_condition": {
            "field":       "equipment_investment",
            "operator":    "gt",
            "value":       0,
            "description": "Ask only if equipment_investment > 0.",
        },
    },
    {
        "field":              "ca_growth_rate",
        "label_fr":           "Taux de croissance annuel prévu",
        "field_type":         "float",
        "consumers":          ["feasibility"],
        "computed_by":        ["van_5_years", "projection_5y"],
        "intake_question_fr": (
            "De combien estimez-vous augmenter vos ventes chaque année ? "
            "(en %, ex : 0.10 pour 10%)"
        ),
        "intake_condition":   None,
    },
    # ── Opex financing & runway ───────────────────────────────────────────────
    {
        "field":              "has_opex_financing",
        "label_fr":           "Financement des charges d'exploitation",
        "field_type":         "bool",
        "consumers":          ["scoring:market", "roadmap_eligibility", "feasibility"],
        "computed_by":        ["credit_eligibility_path"],
        "intake_question_fr": "Avez-vous déjà le financement pour couvrir vos charges d'exploitation (loyer, salaires, etc.) ?",
        "intake_condition":   None,
    },
    {
        "field":              "opex_financing_source",
        "label_fr":           "Source du financement d'exploitation",
        "field_type":         "string",
        "consumers":          ["roadmap_eligibility"],
        "computed_by":        [],
        "intake_question_fr": "D'où vient ce financement ? (épargne personnelle, famille, revenus existants, autre)",
        "intake_condition": {
            "field":       "has_opex_financing",
            "value":       True,
            "description": "Ask only if has_opex_financing = True.",
        },
    },
    {
        "field":              "opex_months_covered",
        "label_fr":           "Durée de trésorerie disponible",
        "field_type":         "int",
        "consumers":          ["scoring:market", "feasibility"],
        "computed_by":        [],
        "intake_question_fr": "Pour combien de mois pouvez-vous couvrir vos charges sans revenus ?",
        "intake_condition":   None,
    },
    # ── Credit situation ──────────────────────────────────────────────────────
    {
        "field":              "needs_credit",
        "label_fr":           "Besoin de crédit",
        "field_type":         "bool",
        "consumers":          ["scoring:market", "roadmap_eligibility", "feasibility"],
        "computed_by":        ["credit_eligibility_path"],
        "intake_question_fr": "Avez-vous besoin d'un crédit pour lancer ou développer votre projet ?",
        "intake_condition":   None,
    },
    {
        "field":              "credit_amount_needed",
        "label_fr":           "Montant du crédit nécessaire",
        "field_type":         "float",
        "consumers":          ["scoring:market", "roadmap_eligibility", "feasibility"],
        "computed_by":        ["credit_eligibility_path", "loan_schedule"],
        "intake_question_fr": "Quel montant estimez-vous nécessaire (en DT) ?",
        "intake_condition": {
            "field":       "needs_credit",
            "value":       True,
            "description": "Ask only if needs_credit = True.",
        },
    },
    {
        "field":              "credit_duration_years",
        "label_fr":           "Durée de remboursement souhaitée",
        "field_type":         "int",
        "consumers":          ["feasibility"],
        "computed_by":        ["loan_schedule", "repayment_capacity_ratio"],
        "intake_question_fr": "Sur combien d'années souhaitez-vous rembourser ?",
        "intake_condition": {
            "field":       "needs_credit",
            "value":       True,
            "description": "Ask only if needs_credit = True.",
        },
    },
    {
        "field":              "has_guarantee",
        "label_fr":           "Garantie disponible",
        "field_type":         "bool",
        "consumers":          ["roadmap_eligibility", "feasibility"],
        "computed_by":        ["credit_eligibility_path"],
        "intake_question_fr": "Avez-vous une garantie à proposer ? (bien immobilier, terrain, caution personnelle, nantissement)",
        "intake_condition": {
            "field":       "needs_credit",
            "value":       True,
            "description": "Ask only if needs_credit = True.",
        },
    },
    {
        "field":              "guarantee_type",
        "label_fr":           "Type de garantie",
        "field_type":         "enum",
        "allowed_values":     ["immobilier", "terrain", "caution_personnelle", "nantissement"],
        "consumers":          ["roadmap_eligibility", "feasibility"],
        "computed_by":        ["credit_eligibility_path"],
        "intake_question_fr": "De quel type est votre garantie ? (immobilier, terrain, caution personnelle, nantissement)",
        "intake_condition": {
            "field":       "has_guarantee",
            "value":       True,
            "description": "Ask only if has_guarantee = True.",
        },
    },
    {
        "field":              "has_existing_credit",
        "label_fr":           "Crédit en cours",
        "field_type":         "bool",
        "consumers":          ["scoring:market", "roadmap_eligibility", "feasibility"],
        "computed_by":        ["repayment_capacity_ratio", "credit_eligibility_path"],
        "intake_question_fr": "Avez-vous déjà un crédit en cours ?",
        "intake_condition":   None,
    },
    {
        "field":              "existing_credit_monthly_payment",
        "label_fr":           "Échéance mensuelle du crédit existant",
        "field_type":         "float",
        "consumers":          ["feasibility"],
        "computed_by":        ["repayment_capacity_ratio", "annual_debt_service"],
        "intake_question_fr": "Quelle est votre échéance mensuelle actuelle (en DT) ?",
        "intake_condition": {
            "field":       "has_existing_credit",
            "value":       True,
            "description": "Ask only if has_existing_credit = True.",
        },
    },
    {
        "field":              "existing_credit_remaining_years",
        "label_fr":           "Années restantes sur le crédit existant",
        "field_type":         "int",
        "consumers":          ["feasibility"],
        "computed_by":        ["projection_5y"],
        "intake_question_fr": "Combien d'années restent sur ce crédit ?",
        "intake_condition": {
            "field":       "has_existing_credit",
            "value":       True,
            "description": "Ask only if has_existing_credit = True.",
        },
    },
    {
        "field":              "credit_eligibility_blockers",
        "label_fr":           "Blocages éventuels pour le crédit",
        "field_type":         "list",
        "allowed_values":     ["fichage_bct", "impayes", "pas_de_garanties", "autre"],
        "consumers":          ["roadmap_eligibility", "feasibility"],
        "computed_by":        ["credit_eligibility_path"],
        "intake_question_fr": (
            "Y a-t-il des blocages qui pourraient empêcher l'accès au crédit ? "
            "(fichage BCT, impayés, absence de garanties, autre)"
        ),
        "intake_condition": {
            "field":       "needs_credit",
            "value":       True,
            "description": "Ask only if needs_credit = True.",
        },
        "nullable":           True,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURATION — legal branch (Part B.2)
# Fires when legal_form_status ∈ {in_progress, registered}
# ─────────────────────────────────────────────────────────────────────────────

STRUCTURATION_LEGAL_BLOCK: List[IntakeQuestion] = [
    {
        "field":              "legal_form_type",
        "label_fr":           "Type de forme juridique",
        "consumers":          ["roadmap_eligibility", "feasibility"],
        "allowed_values":     ["personne_physique", "SARL", "SUARL", "SA", "SAS", "autre"],
        "intake_question_fr": (
            "Quel est le type de votre forme juridique ? "
            "(Personne physique, SARL, SUARL, SA, SAS, autre)"
        ),
        "intake_condition": {
            "field":       "legal_form_status",
            "value_in":    ["in_progress", "registered"],
            "description": "Ask when legal entity exists (in progress or registered).",
        },
        "roadmap_note": (
            "Personne physique who needs SARL-only financing → roadmap action: "
            "'constituer une SARL/SUARL'. "
            "Personne morale required for BFPME co-financing and some BTS products."
        ),
    },
    {
        # Asked only when legal_form_type is a personne morale.
        "field":              "associes",
        "label_fr":           "Associés",
        "consumers":          ["feasibility", "scoring:scalability"],
        "field_type":         "list",
        "intake_question_fr": (
            "Qui sont les associés ? Pour chaque associé, indiquez le nom et "
            "le nombre de parts sociales."
        ),
        "intake_condition": {
            "field":       "legal_form_type",
            "value_in":    ["SARL", "SUARL", "SA", "SAS"],
            "description": "Ask only for personne morale legal forms.",
        },
        "coherence_check": {
            "SARL":  {"min_associes": 2, "description": "SARL requires ≥ 2 associés."},
            "SUARL": {"min_associes": 1, "max_associes": 1, "description": "SUARL requires exactly 1 associé."},
        },
        "coherence_flag_target": "etude_de_projet",
    },
    {
        "field":              "gerant",
        "label_fr":           "Gérant",
        "consumers":          ["feasibility", "scoring:commercial"],
        "field_type":         "string",
        "intake_question_fr": "Qui est le gérant de l'entreprise ?",
        "intake_condition": {
            "field":       "legal_form_type",
            "value_in":    ["SARL", "SUARL", "SA", "SAS"],
            "description": "Ask only for personne morale legal forms.",
        },
    },
    {
        "field":              "needs_premises",
        "label_fr":           "Local nécessaire",
        "consumers":          [],
        "field_type":         "bool",
        "role":               "branch_gate",
        "intake_question_fr": "Votre activité nécessite-t-elle un local (atelier, bureau, point de vente) ?",
        "intake_condition": {
            "field":       "legal_form_status",
            "value_in":    ["in_progress", "registered"],
            "description": "Ask when legal entity exists.",
        },
    },
    {
        "field":              "has_premises",
        "label_fr":           "Local disponible",
        "consumers":          ["roadmap_eligibility", "feasibility"],
        "field_type":         "bool",
        "intake_question_fr": "Avez-vous déjà un local ?",
        "intake_condition": {
            "field":       "needs_premises",
            "value":       True,
            "description": "Ask only if needs_premises = True.",
        },
        "roadmap_note": (
            "has_premises = True → eligible as fonds de commerce / garantie "
            "in credit_eligibility_path logic. "
            "needs_premises = True & has_premises = False → roadmap blocker: "
            "'sécuriser un local avant de déposer un dossier de crédit'."
        ),
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Registry — maps stage → routing blocks that fire after its classifier intake
# ─────────────────────────────────────────────────────────────────────────────

ROUTING_BY_STAGE: Dict[str, List[List[IntakeQuestion]]] = {
    "IDEATION":          [],
    "MARKET_VALIDATION": [UNIT_ECONOMICS_BLOCK],
    "STRUCTURATION":     [CHARGES_BLOCK, STRUCTURATION_LEGAL_BLOCK],
    "FUNDRAISING":       [],
    "LAUNCH_PLANNING":   [],
    "GROWTH":            [],
}


def get_routing_block(stage: str) -> List[IntakeQuestion]:
    """
    Return all non-classifier intake questions for a given stage,
    flattened from all blocks registered for that stage.
    """
    blocks = ROUTING_BY_STAGE.get(stage.upper(), [])
    questions: List[IntakeQuestion] = []
    for block in blocks:
        questions.extend(block)
    return questions


def get_all_routing_fields() -> List[str]:
    """All profile fields populated by non-classifier intake questions."""
    fields: List[str] = []
    for blocks in ROUTING_BY_STAGE.values():
        for block in blocks:
            for q in block:
                if "field" in q:
                    fields.append(q["field"])
    return sorted(set(fields))
