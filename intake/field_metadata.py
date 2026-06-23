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
    "self_assessed_readiness": {
        "question_fr": "Sur une échelle de 1 à 10, à quel point vous sentez-vous prêt à passer à la vitesse supérieure ?",
        "priority": 3,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "self_assessed_strengths": {
        "question_fr": "Quels sont, selon vous, les véritables points forts de votre projet ?",
        "priority": 3,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "self_assessed_weaknesses": {
        "question_fr": "Quels sont les aspects sur lesquels vous vous sentez encore fragile ou incertain ?",
        "priority": 3,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },

    # ── Founder & Team ─────────────────────────────────────────────────────
    "gerant": {
        "question_fr": "Qui est le porteur principal du projet — quel est votre nom et votre rôle ?",
        "priority": 1,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "founder_count": {
        "question_fr": "Combien de fondateurs êtes-vous au total ?",
        "priority": 2,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
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
    "associes": {
        "question_fr": "Pouvez-vous me donner les noms de vos co-fondateurs ou associés ?",
        "priority": 2,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "team_size": {
        "question_fr": "Quelle est la taille totale de votre équipe aujourd'hui, fondateurs inclus ?",
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
    "team_roles": {
        "question_fr": "Quels sont les rôles et responsabilités de chaque membre de l'équipe ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
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
    "registration_date": {
        "question_fr": "Quand avez-vous officiellement enregistré votre entreprise ?",
        "priority": 4,
        "stage_min": 3,
        "depends_on": _eq("legal_form_status", "registered"),
        "can_be_explicitly_unknown": True,
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
    "has_validated_problem": {
        "question_fr": "Avez-vous validé le problème que vous résolvez directement avec des clients potentiels ?",
        "priority": 1,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "validation_type": {
        "question_fr": "Comment avez-vous validé ce problème ? (entretiens clients, pilote, pré-commandes, sondage…)",
        "priority": 2,
        "stage_min": 1,
        "depends_on": _eq("has_validated_problem", True),
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
    "target_market_size": {
        "question_fr": "Quelle est, selon vous, la taille du marché adressable — en nombre de clients potentiels ou en volume d'affaires ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "competitor_count": {
        "question_fr": "Combien de concurrents directs avez-vous identifiés sur votre marché cible ?",
        "priority": 2,
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
    "differentiation_description": {
        "question_fr": "Qu'est-ce qui différencie concrètement votre offre — en quoi êtes-vous meilleur ou différent de la concurrence ?",
        "priority": 2,
        "stage_min": 2,
        "depends_on": _eq("differentiation_claimed", True),
        "can_be_explicitly_unknown": False,
    },
    "local_competitors": {
        "question_fr": "Quels sont les noms de vos principaux concurrents locaux ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
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

    # ── Product & Offer ────────────────────────────────────────────────────
    "product_stage": {
        "question_fr": "À quel stade en est votre produit ou service ? (concept, prototype, MVP, production)",
        "priority": 1,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "demo_available": {
        "question_fr": "Avez-vous une démonstration ou une version fonctionnelle que vous pouvez présenter aujourd'hui ?",
        "priority": 2,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "value_proposition_text": {
        "question_fr": "En une ou deux phrases, quelle est votre proposition de valeur — quel problème résolvez-vous et pour qui ?",
        "priority": 1,
        "stage_min": 1,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    # value_prop_clarity_rating is assessed by the LLM when extracting
    # value_proposition_text — it is never asked directly.
    "pricing_model": {
        "question_fr": "Quel est votre modèle de tarification ? (abonnement mensuel, paiement à l'acte, licence, B2B…)",
        "priority": 2,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "pricing_tested": {
        "question_fr": "Avez-vous testé votre prix auprès de vrais clients ou prospects ?",
        "priority": 2,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "pricing_documented": {
        "question_fr": "Votre politique de prix est-elle documentée dans une grille tarifaire ou un document commercial ?",
        "priority": 3,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },

    # ── Financial Inputs ───────────────────────────────────────────────────
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
    "fixed_costs_monthly": {
        "question_fr": "Quel est le montant total de vos charges fixes mensuelles (si vous les connaissez globalement) ?",
        "priority": 2,
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
    "equipment_investment": {
        "question_fr": "Quelle part de l'investissement est dédiée aux équipements et matériels ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": _not_none("initial_investment"),
        "can_be_explicitly_unknown": True,
    },
    "equipment_lifespan_years": {
        "question_fr": "Quelle est la durée de vie estimée de vos équipements (en années) ?",
        "priority": 4,
        "stage_min": 2,
        "depends_on": _not_none("equipment_investment"),
        "can_be_explicitly_unknown": True,
    },
    "ca_growth_rate": {
        "question_fr": "Quel taux de croissance mensuel de votre chiffre d'affaires anticipez-vous sur les 12 prochains mois ?",
        "priority": 3,
        "stage_min": 3,
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
    "tfse_percentage": {
        "question_fr": "Quel taux de charges sociales patronales s'applique à votre masse salariale ?",
        "priority": 4,
        "stage_min": 2,
        "depends_on": _not_none("personnel_monthly_cost"),
        "can_be_explicitly_unknown": True,
    },
    "tax_rate": {
        "question_fr": "Quel est votre taux d'imposition sur les bénéfices (IS) ?",
        "priority": 4,
        "stage_min": 4,
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
    "revenue_model_type": {
        "question_fr": "Comment générez-vous vos revenus ? (abonnement, facturation à l'acte, freemium, contrats B2B…)",
        "priority": 2,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
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
    "funding_amount": {
        "question_fr": "Quel est le montant total des financements externes levés (en dinars tunisiens) ?",
        "priority": 3,
        "stage_min": 4,
        "depends_on": _eq("funding_secured", True),
        "can_be_explicitly_unknown": False,
    },
    "funding_source": {
        "question_fr": "Quelle est la source de ce financement ? (banque, capital-risque, subvention, famille…)",
        "priority": 3,
        "stage_min": 4,
        "depends_on": _eq("funding_secured", True),
        "can_be_explicitly_unknown": False,
    },
    "self_financing_confirmed": {
        "question_fr": "Avez-vous un apport personnel ou un autofinancement confirmé pour couvrir une partie de l'investissement ?",
        "priority": 2,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "cost_structure_type": {
        "question_fr": "Votre structure de coûts est-elle plutôt à dominante fixe (locaux, personnel), variable (matières premières) ou mixte ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "marginal_cost_estimate": {
        "question_fr": "Quel est votre coût marginal pour accueillir un client supplémentaire — en ressources, temps ou argent ?",
        "priority": 4,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
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
    "credit_duration_years": {
        "question_fr": "Sur quelle durée souhaitez-vous rembourser ce crédit (en années) ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": True,
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
    "opex_months_covered": {
        "question_fr": "Combien de mois de charges d'exploitation pouvez-vous couvrir avec vos ressources actuelles ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "has_opex_financing": {
        "question_fr": "Le financement de vos charges d'exploitation courantes est-il assuré ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "annual_cash_flow": {
        "question_fr": "Quel est votre flux de trésorerie net annuel estimé — recettes moins toutes les dépenses ?",
        "priority": 3,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "annual_debt_service": {
        "question_fr": "Quel est le montant total de vos remboursements d'emprunts sur une année ?",
        "priority": 3,
        "stage_min": 3,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": True,
    },
    "existing_credit_monthly_payment": {
        "question_fr": "Avez-vous des crédits en cours ? Si oui, quelle est la mensualité totale ?",
        "priority": 3,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "credit_eligibility_blockers": {
        "question_fr": "Avez-vous connaissance d'éléments susceptibles de bloquer votre accès au crédit ? (fichage BCT, dettes fiscales, antécédents de défaut…)",
        "priority": 3,
        "stage_min": 2,
        "depends_on": _eq("needs_credit", True),
        "can_be_explicitly_unknown": True,
    },

    # ── Distribution & Operations ──────────────────────────────────────────
    "distribution_channels": {
        "question_fr": "Quels canaux utilisez-vous ou prévoyez-vous d'utiliser pour distribuer votre offre ?",
        "priority": 2,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "distribution_channel_tested": {
        "question_fr": "Avez-vous testé vos canaux de distribution avec de vrais clients — pas seulement en théorie ?",
        "priority": 2,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "delivery_model": {
        "question_fr": "Comment livrez-vous concrètement votre produit ou service au client final ?",
        "priority": 3,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "manual_dependency_level": {
        "question_fr": "Dans votre processus de livraison, quelle est la part d'intervention humaine manuelle ? (faible, moyenne, élevée)",
        "priority": 3,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "automation_level": {
        "question_fr": "Quel est le niveau d'automatisation de vos opérations actuellement ? (aucune, partielle, élevée)",
        "priority": 3,
        "stage_min": 3,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "standardised_process": {
        "question_fr": "Vos processus opérationnels sont-ils standardisés et documentés — peuvent-ils être répliqués sans vous ?",
        "priority": 3,
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

    # ── Technology ─────────────────────────────────────────────────────────
    "tech_is_core_to_offer": {
        "question_fr": "La technologie est-elle au cœur de votre offre, ou s'agit-il d'un simple outil support ?",
        "priority": 3,
        "stage_min": 2,
        "depends_on": None,
        "can_be_explicitly_unknown": False,
    },
    "tech_stack_described": {
        "question_fr": "Votre stack technologique est-il clairement défini et documenté ?",
        "priority": 3,
        "stage_min": 3,
        "depends_on": _eq("tech_is_core_to_offer", True),
        "can_be_explicitly_unknown": True,
    },
    "ip_protected": {
        "question_fr": "Avez-vous une protection de propriété intellectuelle en place — brevet, marque déposée, copyright ?",
        "priority": 4,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "proprietary_data": {
        "question_fr": "Possédez-vous des données propriétaires constituant un avantage compétitif difficile à répliquer ?",
        "priority": 4,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "network_effects": {
        "question_fr": "Votre modèle bénéficie-t-il d'effets de réseau — l'offre devient-elle plus utile à mesure que le nombre d'utilisateurs croît ?",
        "priority": 4,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
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
    "carbon_reduction_claimed": {
        "question_fr": "Votre projet contribue-t-il à une réduction mesurable des émissions de CO₂ ?",
        "priority": 4,
        "stage_min": 2,
        "depends_on": _ne("environmental_impact_type", "aucun"),
        "can_be_explicitly_unknown": True,
    },
    "waste_reduction_measures": {
        "question_fr": "Quelles mesures concrètes avez-vous mises en place pour réduire la production de déchets ?",
        "priority": 3,
        "stage_min": 1,
        "depends_on": _ne("environmental_impact_type", "aucun"),
        "can_be_explicitly_unknown": True,
    },
    "energy_reduction_measures": {
        "question_fr": "Quelles actions concrètes menez-vous pour réduire votre consommation énergétique ?",
        "priority": 3,
        "stage_min": 1,
        "depends_on": _ne("environmental_impact_type", "aucun"),
        "can_be_explicitly_unknown": True,
    },
    "water_reduction_measures": {
        "question_fr": "Quelles mesures adoptez-vous pour réduire votre consommation d'eau ?",
        "priority": 4,
        "stage_min": 1,
        "depends_on": _ne("environmental_impact_type", "aucun"),
        "can_be_explicitly_unknown": True,
    },
    "resource_efficiency_measures": {
        "question_fr": "Comment optimisez-vous l'utilisation de vos ressources et matières premières ?",
        "priority": 3,
        "stage_min": 1,
        "depends_on": _ne("environmental_impact_type", "aucun"),
        "can_be_explicitly_unknown": True,
    },
    "circular_practices_described": {
        "question_fr": "Avez-vous des pratiques d'économie circulaire — réutilisation, recyclage, revalorisation ? Décrivez-les.",
        "priority": 3,
        "stage_min": 2,
        "depends_on": _ne("environmental_impact_type", "aucun"),
        "can_be_explicitly_unknown": True,
    },
    "sdg_alignment": {
        "question_fr": "Votre projet est-il aligné sur des Objectifs de Développement Durable (ODD) de l'ONU ? Si oui, lesquels — donnez les numéros.",
        "priority": 3,
        "stage_min": 1,
        "depends_on": _ne("environmental_impact_type", "aucun"),
        "can_be_explicitly_unknown": True,
    },
    "sdg_evidence": {
        "question_fr": "Quels indicateurs ou preuves concrètes avez-vous de votre contribution aux ODD cités ?",
        "priority": 4,
        "stage_min": 1,
        "depends_on": _not_none("sdg_alignment"),
        "can_be_explicitly_unknown": True,
    },

    # ── Scalability ────────────────────────────────────────────────────────
    "replicability_evidence": {
        "question_fr": "Avez-vous des preuves ou des indicateurs que votre modèle peut être répliqué dans d'autres villes ou régions ?",
        "priority": 3,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "multi_segment_potential": {
        "question_fr": "Votre offre peut-elle adresser plusieurs segments de marché différents sans modifications majeures ?",
        "priority": 3,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "language_adaptability": {
        "question_fr": "Votre offre peut-elle être adaptée à d'autres langues ou contextes culturels ?",
        "priority": 4,
        "stage_min": 4,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
    "team_size_vs_customers": {
        "question_fr": "Comment votre équipe devrait-elle évoluer pour soutenir une multiplication par 5 ou 10 de votre base clients ?",
        "priority": 4,
        "stage_min": 5,
        "depends_on": None,
        "can_be_explicitly_unknown": True,
    },
}

# Fields populated automatically by the engine — never asked directly.
# value_prop_clarity_rating: LLM-assessed when extracting value_proposition_text (1-5).
# has_validated_problem: auto-set True if customer_interview_count>0 OR pilot_users>0 OR pre_orders>0.
DERIVED_FIELDS: frozenset = frozenset({"value_prop_clarity_rating"})
