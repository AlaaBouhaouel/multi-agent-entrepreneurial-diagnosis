"""
intake/field_metadata.py

Metadata for every field in ProjectProfileData that the intake engine may collect.
Drives the question planner (what to ask, in what order, under what conditions)
and the extractor (how to describe fields to the LLM).

Keys per entry:
  question_fr               Consultant-style French question to ask the user
  priority                  1=critical (ask first), 2=high, 3=medium, 4=low
  stage_min                 Minimum maturity stage (1-6) at which this field is relevant
  depends_on                Condition that must hold for this field to be eligible.
                            None = always eligible within stage_min.
                            {"field": str, "op": str, "value": Any}
                            ops: "eq" | "ne" | "in" | "not_none"
  can_be_explicitly_unknown True  = "je ne sais pas" is a valid final answer → field stays None
                            False = probe further, every founder should know this

Field set
---------
This registry was reduced to the 48 analysis-bearing fields: every field here is
read by the maturity classifier, a scoring engine, a derived metric, or the
roadmap eligibility filter. Pure-data fields (names, free-text descriptions that
fed nothing, and fine-grained accounting parameters that fall back to defaults)
were removed so intake stays focused on what actually drives the analysis.
Identity fields (gérant / associés / enterprise name) are deliberately not
collected here.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

Condition = Optional[Dict[str, Any]]


def _eq(field: str, value: Any) -> Condition:
    return {"field": field, "op": "eq", "value": value}


def _ne(field: str, value: Any) -> Condition:
    return {"field": field, "op": "ne", "value": value}


def _in(field: str, values: list) -> Condition:
    return {"field": field, "op": "in", "value": values}


def _not_none(field: str) -> Condition:
    return {"field": field, "op": "not_none"}


FIELD_META: Dict[str, Dict[str, Any]] = {

    # ── Self-Assessment ────────────────────────────────────────────────────
    "self_assessed_stage": {
        "question_fr": "À quel stade situez-vous votre projet actuellement ? (1=Idéation, 2=Structuration, 3=MVP, 4=Levée de fonds, 5=Accélération, 6=Croissance)",
        "priority": 1,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },

    # ── Founder & Team ─────────────────────────────────────────────────────
    "founder_has_prior_experience": {
        "question_fr": "Avez-vous déjà lancé un projet entrepreneurial ou géré une entreprise auparavant ?",
        "priority": 2,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "founder_has_required_skills": {
        "question_fr": "Les compétences techniques nécessaires pour développer votre offre sont-elles présentes au sein de l'équipe fondatrice ?",
        "priority": 2,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "team_core_complete": {
        "question_fr": "L'équipe fondatrice couvre-t-elle toutes les fonctions clés — technique, commerciale et opérationnelle ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "prior_accompaniment": {
        "question_fr": "Avez-vous bénéficié d'un programme d'accompagnement entrepreneurial ? Si oui, lequel ?",
        "priority": 4,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },

    # ── Legal & Administrative ─────────────────────────────────────────────
    "legal_form_status": {
        "question_fr": "Votre structure est-elle déjà enregistrée légalement ? (non enregistrée / en cours / enregistrée)",
        "priority": 2,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "legal_form_type": {
        "question_fr": "Quelle est la forme juridique de votre entreprise ? (SARL, SUARL, SA…)",
        "priority": 3,
        "stage_min": 2,
        "depends_on": _in("legal_form_status", ["in_progress", "registered"]),
        "can_be_explicitly_unknown": False,
    },
    "rne_registered": {
        "question_fr": "Votre entreprise est-elle inscrite au Registre National des Entreprises (RNE) ?",
        "priority": 2,
        "stage_min": 3,
        "depends_on": _eq("legal_form_status", "registered"),
        "can_be_explicitly_unknown": False,
    },
    "startup_label": {
        "question_fr": "Avez-vous obtenu ou êtes-vous en cours d'obtention du label Startup Act ?",
        "priority": 4,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },

    # ── Market & Validation ────────────────────────────────────────────────
    "target_customer_defined": {
        "question_fr": "Avez-vous clairement défini votre client cible — qui est-il, que fait-il, quel problème ressent-il ?",
        "priority": 1,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "geographic_scope": {
        "question_fr": "Quel est votre périmètre géographique visé ? (local, régional, national, international)",
        "priority": 2,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "validation_type": {
        "question_fr": "Comment avez-vous validé votre problème ou votre offre ? (entretiens clients, pilote, pré-commandes, sondage…)",
        "priority": 2,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "customer_interview_count": {
        "question_fr": "Combien d'entretiens avec des clients potentiels avez-vous menés jusqu'à présent ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "pilot_users": {
        "question_fr": "Combien d'utilisateurs avez-vous actuellement dans votre phase pilote ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "pre_orders": {
        "question_fr": "Avez-vous des pré-commandes confirmées ? Si oui, combien ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "differentiation_claimed": {
        "question_fr": "Votre offre se différencie-t-elle clairement des solutions existantes sur le marché ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },

    # ── Innovation ─────────────────────────────────────────────────────────
    "idea_is_new": {
        "question_fr": "Votre idée apporte-t-elle quelque chose de véritablement nouveau sur le marché tunisien, ou s'agit-il d'une adaptation d'un concept existant ?",
        "priority": 1,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "foreign_model_studied": {
        "question_fr": "Avez-vous étudié un modèle similaire à l'étranger comme référence ou point de comparaison ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "business_model_documented": {
        "question_fr": "Votre modèle économique est-il formalisé — dans un business plan, un Business Model Canvas ou tout autre document ?",
        "priority": 2,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },

    # ── Financial Inputs (raw inputs used to compute metrics) ──────────────
    "selling_price": {
        "question_fr": "Quel est votre prix de vente par unité ou par prestation (en dinars tunisiens) ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "unit_cost": {
        "question_fr": "Quel est votre coût de revient unitaire — ce que vous coûte la production ou la réalisation d'une unité ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "expected_monthly_units": {
        "question_fr": "Combien d'unités ou de prestations prévoyez-vous de vendre par mois ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "monthly_revenue": {
        "question_fr": "Quel est votre chiffre d'affaires mensuel actuel (en dinars tunisiens) ?",
        "priority": 1,
        "stage_min": 3,
        "depends_on": _eq("has_paying_customers", True),
        "can_be_explicitly_unknown": False,
    },
    "personnel_monthly_cost": {
        "question_fr": "Quel est le montant total de votre masse salariale mensuelle, charges sociales incluses ?",
        "priority": 2,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "rent_monthly": {
        "question_fr": "Quel est le montant de votre loyer mensuel pour vos locaux ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "other_fixed_costs_monthly": {
        "question_fr": "Quelles sont vos autres charges fixes mensuelles — hors salaires et loyer (assurances, abonnements, honoraires…) ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "cogs_percentage": {
        "question_fr": "Quelle est la part du coût des marchandises ou matières premières dans votre chiffre d'affaires (en %) ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "initial_investment": {
        "question_fr": "Quel est le montant total de l'investissement initial nécessaire pour lancer votre projet (en dinars tunisiens) ?",
        "priority": 2,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "market_price_local": {
        "question_fr": "À quel prix se vend une offre équivalente chez vos concurrents locaux (en dinars tunisiens) ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "market_price_foreign": {
        "question_fr": "À quel prix une offre similaire est-elle vendue sur les marchés étrangers de référence (indiquez en DT ou EUR) ?",
        "priority": 1,
        "stage_min": 2,
        "depends_on": _eq("foreign_model_studied", True),
        "can_be_explicitly_unknown": True,
    },

    # ── Financial State ────────────────────────────────────────────────────
    "has_paying_customers": {
        "question_fr": "Avez-vous déjà des clients qui paient réellement pour votre offre ?",
        "priority": 1,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "revenue_recurring_months": {
        "question_fr": "Depuis combien de mois avez-vous des revenus récurrents et stables ?",
        "priority": 2,
        "stage_min": 5,
        "depends_on": _eq("has_paying_customers", True),
        "can_be_explicitly_unknown": False,
    },
    "financial_docs_exist": {
        "question_fr": "Disposez-vous d'états financiers formels — bilan comptable, compte de résultat ?",
        "priority": 2,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "funding_secured": {
        "question_fr": "Avez-vous levé des fonds externes à ce stade — banque, investisseurs, subventions ?",
        "priority": 2,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "self_financing_confirmed": {
        "question_fr": "Avez-vous un apport personnel ou un autofinancement confirmé pour couvrir une partie de l'investissement ?",
        "priority": 2,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },

    # ── Credit & Financing ─────────────────────────────────────────────────
    "needs_credit": {
        "question_fr": "Avez-vous besoin d'un crédit bancaire pour financer votre projet ou démarrage ?",
        "priority": 2,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "credit_amount_needed": {
        "question_fr": "Quel montant de crédit recherchez-vous (en dinars tunisiens) ?",
        "priority": 2,
        "stage_min": 2,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": False,
    },
    "has_guarantee": {
        "question_fr": "Disposez-vous de garanties ou de sûretés à proposer à la banque — bien immobilier, caution, SOTUGAR ?",
        "priority": 2,
        "stage_min": 2,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": False,
    },
    "has_premises": {
        "question_fr": "Disposez-vous de locaux confirmés pour exercer votre activité ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": False,
    },
    "apport_personnel": {
        "question_fr": "Quel est le montant de votre apport personnel dans ce projet (en dinars tunisiens) ?",
        "priority": 2,
        "stage_min": 2,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": True,
    },
    "credit_eligibility_blockers": {
        "question_fr": "Avez-vous connaissance d'éléments susceptibles de bloquer votre accès au crédit ? (fichage BCT, dettes fiscales, antécédents de défaut…)",
        "priority": 3,
        "stage_min": 2,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": True,
    },
    "annual_debt_service": {
        "question_fr": "Quel est le montant total de vos remboursements d'emprunts sur une année ?",
        "priority": 3,
        "stage_min": 3,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": True,
    },
    "has_opex_financing": {
        "question_fr": "Le financement de vos charges d'exploitation courantes est-il assuré ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },

    # ── Distribution & Operations ──────────────────────────────────────────
    "distribution_channel_tested": {
        "question_fr": "Avez-vous testé vos canaux de distribution avec de vrais clients — pas seulement en théorie ?",
        "priority": 2,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "client_base_beyond_pilot": {
        "question_fr": "Votre base clients dépasse-t-elle le cercle des utilisateurs pilotes initiaux ?",
        "priority": 2,
        "stage_min": 5,
        "depends_on": _eq("has_paying_customers", True),
        "can_be_explicitly_unknown": False,
    },

    # ── Sustainability & Green ─────────────────────────────────────────────
    "environmental_impact_type": {
        "question_fr": "Votre projet a-t-il un impact environnemental positif ? Si oui, dans quel domaine ? (économie d'énergie / réduction des déchets / eau / biodiversité / aucun)",
        "priority": 2,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "environmental_impact_description": {
        "question_fr": "Décrivez concrètement l'impact environnemental positif de votre projet.",
        "priority": 3,
        "stage_min": 1,
        "depends_on": _ne("environmental_impact_type", "aucun"),
        "can_be_explicitly_unknown": False,
    },
    "sdg_alignment": {
        "question_fr": "Votre projet est-il aligné sur des Objectifs de Développement Durable (ODD) de l'ONU ? Si oui, lesquels — donnez les numéros.",
        "priority": 3,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
}

# No auto-derived fields. (value_prop_clarity_rating was removed with
# value_proposition_text; has_validated_problem was removed as a redundant gate —
# demand validation is read directly from customer_interview_count / pilot_users /
# pre_orders / validation_type.)
DERIVED_FIELDS: frozenset = frozenset()
