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

Blocks defined here:

DIAGNOSTIC ENGINE:
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
  LEGAL_BLOCK (Part B.2)  — legal_form_type, has_premises.
                            (Identity fields — gérant, associés — are not collected.)



Note: fields that are `computed` (gross_margin_percentage, van_5_years, etc.)
are never asked directly — they are derived by calculations.py from the `asked`
fields collected here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


IntakeQuestion = Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# IDEATION — green / environmental block
# Fires after ideation classifier questions.
# All fields are nullable — answers feed score_green only, not the classifier.
# ─────────────────────────────────────────────────────────────────────────────

GREEN_BLOCK: List[IntakeQuestion] = [
    {
        "field":              "environmental_impact_type",
        "label_fr":           "Type d'impact environnemental",
        "field_type":         "enum",
        "allowed_values":     ["réduction_pollution", "économie_énergie", "gestion_déchets",
                               "biodiversité", "économie_eau", "autre", "aucun"],
        "consumers":          ["scoring:green"],
        "computed_by":        [],
        "intake_question_fr": "Quel type d'impact environnemental positif votre projet génère-t-il ?",
        "intake_condition":   None,
        "nullable":           True,
    },
    {
        "field":              "environmental_impact_description",
        "label_fr":           "Description de l'impact environnemental",
        "field_type":         "string",
        "consumers":          ["scoring:green"],
        "computed_by":        [],
        "intake_question_fr": "Décrivez en quelques phrases l'impact environnemental positif de votre projet.",
        "intake_condition": {
            "field":       "environmental_impact_type",
            "operator":    "not_in",
            "value":       ["aucun"],
            "description": "Ask only if environmental_impact_type is not 'aucun'.",
        },
        "nullable":           True,
    },
    {
        "field":              "sdg_alignment",
        "label_fr":           "Alignement avec les ODD",
        "field_type":         "list",
        "allowed_values":     [str(i) for i in range(1, 18)],
        "consumers":          ["scoring:green"],
        "computed_by":        [],
        "intake_question_fr": (
            "Votre projet contribue-t-il aux Objectifs de Développement Durable (ODD) de l'ONU ? "
            "Si oui, lesquels ? (ex : ODD 7, ODD 12, ODD 13)"
        ),
        "intake_condition":   None,
        "nullable":           True,
    },
]


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
    # ── Investment ────────────────────────────────────────────────────────────
    {
        "field":              "initial_investment",
        "label_fr":           "Investissement initial",
        "field_type":         "float",
        "consumers":          ["scoring:market", "feasibility"],
        "computed_by":        ["breakeven_months", "van_5_years"],
        "intake_question_fr": "Quel est l'investissement initial nécessaire pour démarrer (en DT) ? (équipements, aménagement, stock de départ, etc.)",
        "intake_condition":   None,
    },
    # ── Opex financing ────────────────────────────────────────────────────────
    {
        "field":              "has_opex_financing",
        "label_fr":           "Financement des charges d'exploitation",
        "field_type":         "bool",
        "consumers":          ["scoring:market", "roadmap_eligibility", "feasibility"],
        "computed_by":        ["credit_eligibility_path"],
        "intake_question_fr": "Avez-vous déjà le financement pour couvrir vos charges d'exploitation (loyer, salaires, etc.) ?",
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
        "field":              "annual_debt_service",
        "label_fr":           "Remboursement annuel des emprunts",
        "field_type":         "float",
        "consumers":          ["feasibility"],
        "computed_by":        ["repayment_capacity_ratio"],
        "intake_question_fr": "Quel est le montant total de vos remboursements d'emprunts sur une année (en DT) ?",
        "intake_condition": {
            "field":       "needs_credit",
            "value":       True,
            "description": "Ask only if needs_credit = True.",
        },
        "nullable":           True,
    },
    {
        "field":              "apport_personnel",
        "label_fr":           "Apport personnel",
        "field_type":         "float",
        "consumers":          ["feasibility"],
        "computed_by":        ["minimum_credit_needed"],
        "intake_question_fr": "Quel est le montant de votre apport personnel dans ce projet (en DT) ?",
        "intake_condition": {
            "field":       "needs_credit",
            "value":       True,
            "description": "Ask only if needs_credit = True.",
        },
        "nullable":           True,
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
        "field":              "has_premises",
        "label_fr":           "Local disponible",
        "consumers":          ["roadmap_eligibility", "feasibility"],
        "field_type":         "bool",
        "intake_question_fr": "Disposez-vous d'un local confirmé pour exercer votre activité ?",
        "intake_condition": {
            "field":       "needs_credit",
            "value":       True,
            "description": "Ask when a credit is needed (premises count as fonds de commerce guarantee).",
        },
        "roadmap_note": (
            "has_premises = True → eligible as fonds de commerce / garantie "
            "in credit_eligibility_path logic."
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

# ─────────────────────────────────────────────────────────────────────────────
# SCORER_BLOCKS — questions tied to scoring dimensions, not maturity stages.
# Asked independently of stage progression (e.g. after classifier questions
# or as a dedicated section in the intake form).
# ─────────────────────────────────────────────────────────────────────────────

SCORER_BLOCKS: Dict[str, List[IntakeQuestion]] = {
    "green": GREEN_BLOCK,
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


def get_scorer_block(dimension: str) -> List[IntakeQuestion]:
    """Return intake questions for a scoring dimension (not stage-gated)."""
    return SCORER_BLOCKS.get(dimension.lower(), [])


def get_all_routing_fields() -> List[str]:
    """All profile fields populated by stage-gated intake questions."""
    fields: List[str] = []
    for blocks in ROUTING_BY_STAGE.values():
        for block in blocks:
            for q in block:
                if "field" in q:
                    fields.append(q["field"])
    return sorted(set(fields))


def get_all_scorer_fields() -> List[str]:
    """All profile fields populated by scorer-specific intake questions."""
    fields: List[str] = []
    for block in SCORER_BLOCKS.values():
        for q in block:
            if "field" in q:
                fields.append(q["field"])
    return sorted(set(fields))
