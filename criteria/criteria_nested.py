"""
criteria_nested.py

Nested diagnostic criteria for the LeadIt maturity classifier.

Structure
---------
Each stage contains top-level parent criteria.
Parents group related leaf criteria under an aggregation rule:

    "all"  — every sub-criterion must pass  (AND)
    "any"  — at least one must pass         (OR)

Leaf criteria carry the actual field check:

    "truthy"    — field is True
    "enum_in"   — field value is in allowed_values
    "min_value" — field value >= min_value
    "contains"  — field (list) contains value
    "any"       — field_group: at least one field is True

Evaluation contract  (True | False | None):
    True  — criterion satisfied
    False — confirmed gap
    None  — data missing; surfaced, not hidden as failure

A stage passes only when all its top-level parent criteria return True.

consumers tag
-------------
Every leaf carries a `consumers` list.  The classifier evaluates ONLY
leaves tagged "classifier" (§2.3.5 — keep the taxonomy lean).
Other consumers:  "scoring:<dim>"  |  "roadmap_eligibility"  |  "feasibility"

Adaptive intake
---------------
Every leaf carries:
  intake_question_fr : the question asked to the founder
  intake_condition   : optional branch condition
                       {"field": str, "value": ..., "description": str}
                       OR {"field": str, "value_in": [...], "description": str}

Non-classifier intake questions (legal_form_type, associes, gerant,
needs_premises, has_premises) live in intake_routing.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


CriterionNode = Dict[str, Any]

STAGE_ORDER: Tuple[str, ...] = (
    "IDEATION",
    "MARKET_VALIDATION",
    "STRUCTURATION",
    "FUNDRAISING",
    "LAUNCH_PLANNING",
    "GROWTH",
)

STAGE_LABELS_FR: Dict[str, str] = {
    "IDEATION":          "Idéation",
    "MARKET_VALIDATION": "Validation marché",
    "STRUCTURATION":     "Structuration",
    "FUNDRAISING":       "Fundraising",
    "LAUNCH_PLANNING":   "Lancement",
    "GROWTH":            "Croissance",
}

# 1-based integer representation used throughout the profile and gap calculations.
# IDEATION=1, MARKET_VALIDATION=2, ..., GROWTH=6
STAGE_TO_INT: Dict[str, int] = {
    stage: idx + 1 for idx, stage in enumerate(STAGE_ORDER)
}
INT_TO_STAGE: Dict[int, str] = {v: k for k, v in STAGE_TO_INT.items()}


def stage_name_to_int(stage: str) -> Optional[int]:
    """Convert a stage name (any case) to its 1-based integer. Returns None if unknown."""
    return STAGE_TO_INT.get(stage.upper())

BLOCKER_DOMAINS: Tuple[str, ...] = (
    "financier",
    "légal",
    "marché",
    "organisationnel",
    "technique",
)


CRITERIA_BY_STAGE: Dict[str, List[CriterionNode]] = {

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 1 — IDEATION
    # Default entry stage. No criteria.
    # ─────────────────────────────────────────────────────────────────────
    "IDEATION": [],

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 2 — MARKET VALIDATION
    # 3 parents, all must pass.
    # ─────────────────────────────────────────────────────────────────────
    "MARKET_VALIDATION": [
        {
            "criterion":    "market_knowledge",
            "label_fr":     "Connaissance du marché",
            "domain":       "marché",
            "rule":         "all",
            "description_fr": (
                "Le fondateur a défini sa cible, son périmètre géographique, "
                "évalué le contexte marché et articulé sa différenciation."
            ),
            "sub_criteria": [
                {
                    "criterion":          "target_customer_defined",
                    "label_fr":           "Client cible identifié",
                    "domain":             "marché",
                    "field":              "target_customer_defined",
                    "rule":               "truthy",
                    "consumers":          ["classifier"],
                    "description_fr":     "Le fondateur a identifié son segment client cible.",
                    "intake_question_fr": "À qui s'adresse votre projet ? Décrivez votre client type.",
                },
                {
                    "criterion":          "geographic_scope_defined",
                    "label_fr":           "Périmètre géographique défini",
                    "domain":             "marché",
                    "field":              "geographic_scope",
                    "rule":               "enum_in",
                    "allowed_values":     ["local", "regional", "national", "international"],
                    "consumers":          ["classifier", "scoring:market", "scoring:scalability"],
                    "description_fr":     "Le fondateur a défini si le projet cible un marché local ou international.",
                    "intake_question_fr": (
                        "Votre projet cible-t-il le marché local, régional, national ou international ?"
                    ),
                },
                {
                    # Passes if the idea is original locally (idea_is_new = True)
                    # OR the founder studied the foreign equivalent (foreign_model_studied = True).
                    # If idea_is_new = True → foreign_model_studied is NOT asked (any rule satisfied).
                    # If idea_is_new = False → foreign_model_studied is asked via intake_condition.
                    "criterion":    "market_context_assessed",
                    "label_fr":     "Contexte marché évalué",
                    "domain":       "marché",
                    "rule":         "any",
                    "description_fr": (
                        "Soit l'idée est originale localement, soit le fondateur a étudié "
                        "les équivalents étrangers et sait ce qu'il apporte de différent."
                    ),
                    "intake_question_fr": (
                        "Votre idée existe-t-elle déjà sur le marché local ou à l'étranger ?"
                    ),
                    "sub_criteria": [
                        {
                            "criterion":          "idea_is_new",
                            "label_fr":           "Idée originale sur le marché local",
                            "domain":             "marché",
                            "field":              "idea_is_new",
                            "rule":               "truthy",
                            "consumers":          ["classifier"],
                            "description_fr":     "Le projet apporte une idée qui n'existe pas encore localement.",
                            "intake_question_fr": "Est-ce une idée nouvelle sur votre marché local ?",
                        },
                        {
                            "criterion":          "foreign_model_studied",
                            "label_fr":           "Modèle étranger étudié",
                            "domain":             "marché",
                            "field":              "foreign_model_studied",
                            "rule":               "truthy",
                            "consumers":          ["classifier"],
                            "description_fr": (
                                "Le fondateur a étudié le modèle étranger existant "
                                "avant de l'adapter au marché local."
                            ),
                            "intake_question_fr": (
                                "Avez-vous étudié comment ce concept fonctionne à l'étranger ? "
                                "Qu'est-ce que vous allez apporter de différent ?"
                            ),
                            "intake_condition": {
                                "field":       "idea_is_new",
                                "value":       False,
                                "description": "Ask only if idea_is_new is False (concept exists abroad).",
                            },
                        },
                    ],
                },
                {
                    "criterion":          "differentiation_articulated",
                    "label_fr":           "Différenciation articulée",
                    "domain":             "marché",
                    "field":              "differentiation_claimed",
                    "rule":               "truthy",
                    "consumers":          ["classifier", "scoring:market", "scoring:innovation"],
                    "description_fr": (
                        "Le fondateur articule clairement ce qu'il apporte de nouveau "
                        "par rapport aux alternatives existantes."
                    ),
                    "intake_question_fr": "Qu'est-ce qui différencie votre offre de ce qui existe déjà ?",
                },
            ],
        },
        {
            "criterion":    "founder_readiness",
            "label_fr":     "Maturité du fondateur",
            "domain":       "organisationnel",
            "rule":         "all",
            "description_fr": (
                "Le fondateur dispose des compétences dans le domaine "
                "et d'une expérience professionnelle pertinente."
            ),
            "sub_criteria": [
                {
                    # Passes if founder has skills OR team covers them.
                    "criterion":          "domain_competence",
                    "label_fr":           "Compétences domaine couvertes",
                    "domain":             "organisationnel",
                    "field_group":        ["founder_has_required_skills", "team_core_complete"],
                    "rule":               "any",
                    "consumers":          ["classifier", "scoring:scalability"],
                    "description_fr": (
                        "Le fondateur maîtrise le domaine, "
                        "ou son équipe couvre les compétences clés."
                    ),
                    "intake_question_fr": (
                        "Avez-vous les compétences nécessaires dans ce domaine, "
                        "ou avez-vous une équipe qui les couvre ?"
                    ),
                },
                {
                    "criterion":          "prior_professional_experience",
                    "label_fr":           "Expérience professionnelle antérieure",
                    "domain":             "organisationnel",
                    "field":              "founder_has_prior_experience",
                    "rule":               "truthy",
                    "consumers":          ["classifier"],
                    "description_fr": (
                        "Le fondateur a une expérience professionnelle pertinente avant ce projet."
                    ),
                    "intake_question_fr": (
                        "Avez-vous une expérience professionnelle dans ce domaine ou un domaine proche ?"
                    ),
                },
            ],
        },
        {
            # At least one demand signal is enough to pass.
            "criterion":    "customers_validation",
            "label_fr":     "Validation par la demande réelle",
            "domain":       "marché",
            "rule":         "any",
            "description_fr": (
                "Au moins une forme de validation externe par de vrais "
                "clients ou utilisateurs potentiels."
            ),
            "intake_question_fr": "Avez-vous déjà testé votre idée avec de vraies personnes ?",
            "sub_criteria": [
                {
                    "criterion":          "has_pre_orders",
                    "label_fr":           "Précommandes reçues",
                    "domain":             "marché",
                    "field":              "pre_orders",
                    "rule":               "min_value",
                    "min_value":          1,
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr":     "Au moins une précommande réelle a été reçue.",
                    "intake_question_fr": "Avez-vous reçu des précommandes ? Combien ?",
                },
                {
                    "criterion":          "has_pilot_users",
                    "label_fr":           "Utilisateurs pilotes",
                    "domain":             "marché",
                    "field":              "pilot_users",
                    "rule":               "min_value",
                    "min_value":          1,
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr":     "Au moins un utilisateur a testé le produit avant le lancement.",
                    "intake_question_fr": "Des personnes ont-elles testé votre produit ou service ? Combien ?",
                },
                {
                    "criterion":          "has_customer_interviews",
                    "label_fr":           "Entretiens clients structurés",
                    "domain":             "marché",
                    "field":              "customer_interview_count",
                    "rule":               "min_value",
                    "min_value":          1,
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr": (
                        "Au moins un entretien structuré avec un client ou prospect potentiel."
                    ),
                    "intake_question_fr": (
                        "Avez-vous mené des entretiens avec des clients potentiels ? Combien ?"
                    ),
                },
                {
                    "criterion":          "has_survey_results",
                    "label_fr":           "Résultats d'enquête disponibles",
                    "domain":             "marché",
                    "field":              "validation_type",
                    "rule":               "contains",
                    "value":              "survey",
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr":     "Une enquête ou sondage marché a été réalisée.",
                    "intake_question_fr": (
                        "Avez-vous réalisé une enquête ou un sondage auprès de votre cible ?"
                    ),
                },
            ],
        },
    ],

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 3 — STRUCTURATION
    # 2 parents, all must pass.
    # ─────────────────────────────────────────────────────────────────────
    "STRUCTURATION": [
        {
            "criterion":    "organisation",
            "label_fr":     "Organisation structurée",
            "domain":       "organisationnel",
            "rule":         "all",
            "description_fr": (
                "Le projet dispose d'un modèle économique documenté "
                "et d'une équipe couvrant les rôles clés."
            ),
            "sub_criteria": [
                {
                    "criterion":          "business_model_documented",
                    "label_fr":           "Modèle économique documenté",
                    "domain":             "organisationnel",
                    "field":              "business_model_documented",
                    "rule":               "truthy",
                    "consumers":          ["classifier"],
                    "description_fr": (
                        "Un business model canvas, une grille tarifaire ou un équivalent est documenté."
                    ),
                    "intake_question_fr": (
                        "Avez-vous documenté votre modèle économique (canvas, grille tarifaire, etc.) ?"
                    ),
                },
                {
                    "criterion":          "team_core_sufficient",
                    "label_fr":           "Équipe noyau suffisante",
                    "domain":             "organisationnel",
                    "field_group":        ["team_core_complete", "founder_has_required_skills"],
                    "rule":               "any",
                    "consumers":          ["classifier", "scoring:scalability"],
                    "description_fr": (
                        "Les rôles clés sont couverts par l'équipe, ou le fondateur "
                        "peut crédiblement couvrir les rôles manquants."
                    ),
                    "intake_question_fr": (
                        "Votre équipe couvre-t-elle les compétences clés nécessaires au projet ?"
                    ),
                },
            ],
        },
        {
            "criterion":    "legal",
            "label_fr":     "Démarche légale engagée",
            "domain":       "légal",
            "rule":         "all",
            "description_fr": "Le projet a entamé ou finalisé son enregistrement légal.",
            "sub_criteria": [
                {
                    "criterion":          "legal_form_initiated",
                    "label_fr":           "Forme juridique engagée",
                    "domain":             "légal",
                    "field":              "legal_form_status",
                    "rule":               "enum_in",
                    "allowed_values":     ["in_progress", "registered"],
                    "consumers":          ["classifier", "roadmap_eligibility"],
                    "description_fr":     "Le projet a commencé ou terminé l'incorporation légale.",
                    "intake_question_fr": (
                        "Avez-vous entamé ou finalisé l'enregistrement légal de votre entreprise ?"
                    ),
                },
            ],
        },
    ],

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 4 — FUNDRAISING
    # 2 parents, all must pass.
    # ─────────────────────────────────────────────────────────────────────
    "FUNDRAISING": [
        {
            "criterion":    "financial_evidence",
            "label_fr":     "Preuve de viabilité financière",
            "domain":       "financier",
            "rule":         "all",
            "description_fr": "Le projet a des clients payants et des documents financiers.",
            "sub_criteria": [
                {
                    "criterion":          "has_paying_customers",
                    "label_fr":           "Clients payants",
                    "domain":             "financier",
                    "field":              "has_paying_customers",
                    "rule":               "truthy",
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr":     "Il existe de vraies transactions, pas seulement des intentions.",
                    "intake_question_fr": (
                        "Avez-vous des clients qui ont payé pour votre produit ou service ?"
                    ),
                },
                {
                    "criterion":          "financial_docs_exist",
                    "label_fr":           "Documents financiers existants",
                    "domain":             "financier",
                    "field":              "financial_docs_exist",
                    "rule":               "truthy",
                    "consumers":          ["classifier", "feasibility"],
                    "description_fr": (
                        "Prévisionnel, pitch deck chiffré, ou documents comptables disponibles."
                    ),
                    "intake_question_fr": (
                        "Avez-vous un prévisionnel financier, un pitch deck chiffré "
                        "ou des documents comptables ?"
                    ),
                },
            ],
        },
        {
            "criterion":    "legal_constitution",
            "label_fr":     "Entreprise légalement constituée",
            "domain":       "légal",
            "rule":         "all",
            "description_fr": "L'entreprise est officiellement enregistrée.",
            "sub_criteria": [
                {
                    "criterion":          "legal_form_registered",
                    "label_fr":           "Forme juridique enregistrée",
                    "domain":             "légal",
                    "field":              "legal_form_status",
                    "rule":               "enum_in",
                    "allowed_values":     ["registered"],
                    "consumers":          ["classifier", "roadmap_eligibility"],
                    "description_fr":     "L'entreprise est légalement constituée.",
                    "intake_question_fr": "Votre entreprise est-elle officiellement enregistrée ?",
                },
                {
                    # Confirms registration in the RNE (Registre National des Entreprises).
                    # Only asked when legal_form_status is registered.
                    "criterion":          "rne_registered",
                    "label_fr":           "Enregistrée au RNE",
                    "domain":             "légal",
                    "field":              "rne_registered",
                    "rule":               "truthy",
                    "consumers":          ["classifier", "roadmap_eligibility"],
                    "description_fr": (
                        "L'entreprise est enregistrée au Registre National des Entreprises (RNE)."
                    ),
                    "intake_question_fr": (
                        "Votre entreprise est-elle enregistrée au Registre National des Entreprises (RNE) ?"
                    ),
                    "intake_condition": {
                        "field":       "legal_form_status",
                        "value":       "registered",
                        "description": "Ask only when legal_form_status = registered.",
                    },
                },
            ],
        },
    ],

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 5 — LAUNCH PLANNING
    # 1 parent.
    # ─────────────────────────────────────────────────────────────────────
    "LAUNCH_PLANNING": [
        {
            "criterion":    "launch_readiness",
            "label_fr":     "Prêt pour le lancement",
            "domain":       "financier",
            "rule":         "all",
            "description_fr": (
                "Le financement est sécurisé et un canal de distribution a été testé."
            ),
            "sub_criteria": [
                {
                    # Passes if external funding secured OR self-financing confirmed.
                    "criterion":          "funding_ready",
                    "label_fr":           "Financement sécurisé ou autofinancement confirmé",
                    "domain":             "financier",
                    "field_group":        ["funding_secured", "self_financing_confirmed"],
                    "rule":               "any",
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr": (
                        "Le projet dispose d'un financement externe ou d'un autofinancement suffisant."
                    ),
                    "intake_question_fr": (
                        "Avez-vous sécurisé le financement nécessaire pour lancer votre projet ?"
                    ),
                },
                {
                    "criterion":          "distribution_channel_tested",
                    "label_fr":           "Canal de distribution testé",
                    "domain":             "marché",
                    "field":              "distribution_channel_tested",
                    "rule":               "truthy",
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr": (
                        "Au moins un canal de vente a été testé en conditions réelles."
                    ),
                    "intake_question_fr": (
                        "Avez-vous testé un canal de vente ou de distribution en conditions réelles ?"
                    ),
                },
            ],
        },
    ],

    # ─────────────────────────────────────────────────────────────────────
    # STAGE 6 — GROWTH
    # 1 parent.
    # ─────────────────────────────────────────────────────────────────────
    "GROWTH": [
        {
            "criterion":    "growth_evidence",
            "label_fr":     "Preuves de croissance",
            "domain":       "financier",
            "rule":         "all",
            "description_fr": (
                "Le projet génère des revenus récurrents et a dépassé le cercle du pilote."
            ),
            "sub_criteria": [
                {
                    "criterion":          "revenue_recurring_months",
                    "label_fr":           "Revenu récurrent sur 3 mois ou plus",
                    "domain":             "financier",
                    "field":              "revenue_recurring_months",
                    "rule":               "min_value",
                    "min_value":          3,
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr": (
                        "Le projet a généré des revenus sur trois mois consécutifs minimum."
                    ),
                    "intake_question_fr": (
                        "Depuis combien de mois générez-vous des revenus de façon régulière ?"
                    ),
                },
                {
                    "criterion":          "client_base_beyond_pilot",
                    "label_fr":           "Base clients au-delà du pilote",
                    "domain":             "marché",
                    "field":              "client_base_beyond_pilot",
                    "rule":               "truthy",
                    "consumers":          ["classifier", "scoring:market"],
                    "description_fr": (
                        "Les clients dépassent le cercle du pilote ou des early adopters."
                    ),
                    "intake_question_fr": (
                        "Avez-vous des clients au-delà de votre cercle de pilote initial ?"
                    ),
                },
            ],
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Traversal helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_leaf(node: CriterionNode) -> bool:
    return "sub_criteria" not in node


def get_stage_criteria(stage: str) -> List[CriterionNode]:
    """Top-level parent criteria for a given stage."""
    return CRITERIA_BY_STAGE.get(stage.upper(), [])


def get_leaf_criteria(stage: str, classifier_only: bool = False) -> List[CriterionNode]:
    """
    All leaf criteria for a stage (depth-first).

    classifier_only=True  → only leaves tagged with "classifier" in consumers.
    classifier_only=False → all leaves regardless of consumers.
    """
    leaves: List[CriterionNode] = []

    def _walk(nodes: List[CriterionNode]) -> None:
        for node in nodes:
            if is_leaf(node):
                if not classifier_only or "classifier" in node.get("consumers", []):
                    leaves.append(node)
            else:
                _walk(node.get("sub_criteria", []))

    _walk(get_stage_criteria(stage))
    return leaves


def get_all_profile_fields(stage: str) -> List[str]:
    """Every profile field referenced by leaf criteria for a stage."""
    fields: List[str] = []
    for leaf in get_leaf_criteria(stage):
        if "field" in leaf:
            fields.append(leaf["field"])
        fields.extend(leaf.get("field_group", []))
    return sorted(set(fields))


def get_intake_questions(stage: str) -> List[Dict[str, Any]]:
    """
    Ordered intake questions for a stage.

    Includes parent-level gateway questions (before their sub-criteria are asked)
    and leaf-level questions with any branch conditions.
    """
    questions: List[Dict[str, Any]] = []

    def _walk(nodes: List[CriterionNode]) -> None:
        for node in nodes:
            if not is_leaf(node):
                if "intake_question_fr" in node:
                    questions.append({
                        "criterion":   node["criterion"],
                        "question_fr": node["intake_question_fr"],
                        "condition":   node.get("intake_condition"),
                        "consumers":   node.get("consumers", []),
                        "is_parent":   True,
                    })
                _walk(node.get("sub_criteria", []))
            else:
                if "intake_question_fr" in node:
                    questions.append({
                        "criterion":   node["criterion"],
                        "question_fr": node["intake_question_fr"],
                        "condition":   node.get("intake_condition"),
                        "consumers":   node.get("consumers", []),
                        "is_parent":   False,
                    })

    _walk(get_stage_criteria(stage))
    return questions


def is_valid_stage(stage: str) -> bool:
    return stage.upper() in STAGE_ORDER


def get_stage_index(stage: str) -> Optional[int]:
    s = stage.upper()
    return STAGE_ORDER.index(s) if s in STAGE_ORDER else None
