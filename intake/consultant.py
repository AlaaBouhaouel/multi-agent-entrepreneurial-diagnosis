"""
intake/consultant.py

Single LLM call that does both extraction and question generation.
Implements a stage-first interview strategy: classify maturity before
collecting scoring or financial data.

The planner is still used to identify which fields are in scope and
compute completion stats — but it no longer picks the question text.
The LLM owns that decision.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .field_metadata import DERIVED_FIELDS, FIELD_META
from .pii import llm_pii_mode, pii_for_llm
from .planner import ANSWERED, EXPLICITLY_UNKNOWN, PENDING, is_eligible

_ALLOWED_EXTRA = {"value_prop_clarity_rating"}

# Fields that directly determine or confirm the maturity stage (Phase 1 & 2).
_CLASSIFIER_FIELDS = frozenset({
    "self_assessed_stage", "gerant",
    # Stage 1?2 criteria
    "target_customer_defined", "customer_interview_count", "pilot_users", "pre_orders",
    "differentiation_claimed", "idea_is_new", "foreign_model_studied", "team_core_complete",
    # Stage 2?3 criteria
    "business_model_documented", "product_stage",
    # Stage 3?4 criteria
    "has_paying_customers", "financial_docs_exist", "rne_registered",
    # Stage 4?5 criteria
    "funding_secured", "self_financing_confirmed", "distribution_channel_tested",
    # Stage 5?6 criteria
    "client_base_beyond_pilot", "revenue_recurring_months",
})

# Raw financial inputs — only appropriate once the founder is at MVP+ (Phase 4).
_FINANCIAL_FIELDS = frozenset({
    "selling_price", "unit_cost", "expected_monthly_units", "monthly_revenue",
    "personnel_monthly_cost", "rent_monthly", "other_fixed_costs_monthly", "fixed_costs_monthly",
    "initial_investment", "equipment_investment", "equipment_lifespan_years",
    "ca_growth_rate", "cogs_percentage", "tfse_percentage", "tax_rate",
    "needs_credit", "credit_amount_needed", "credit_duration_years", "has_guarantee",
    "has_premises", "apport_personnel", "opex_months_covered", "has_opex_financing",
    "annual_cash_flow", "annual_debt_service", "existing_credit_monthly_payment",
    "credit_eligibility_blockers",
})

_STAGE_NAMES = {
    1: "IDÉATION",
    2: "STRUCTURATION",
    3: "MVP",
    4: "LEVÉE DE FONDS",
    5: "ACCÉLÉRATION",
    6: "CROISSANCE",
}


@dataclass
class ConsultResult:
    extracted: Dict[str, Any]
    explicitly_unknown: List[str]
    meta_response: Optional[str]   # set when user asked a process question
    next_question: Optional[str]   # None only when meta_response is set


# -- Prompt --------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are the LeadIt Intake Planner — a senior startup consultant conducting a diagnostic discovery \
interview for an entrepreneurial assessment platform in Tunisia.

## LANGUAGE POLICY
- You can speak French and Arabic.
- Always mirror the founder's language from their latest message.
- If the founder mixes languages, you may reply in the same mixed style.
- If there is no signal yet (opening turn), ask the first question in Arabic first, then French.

## PRIMARY OBJECTIVE
Establish the founder's maturity stage as quickly and accurately as possible.
Then enrich the profile with scoring and financial data — in that order.

Your interview follows four phases. The context tells you which fields are still missing \
and which phase you are in.

---

## PHASE 1 — STAGE DISCOVERY  (priorité maximale)
Goal: Classify the project into one of six stages.
  IDÉATION ? STRUCTURATION ? MVP ? LEVÉE DE FONDS ? ACCÉLÉRATION ? CROISSANCE

What to ask:
  - Customer validation: interviews conducted, pilot users, pre-orders.
  - Team: founder count, skills present, team completeness.
  - Legal / admin: registered (RNE), startup label, legal form.
  - Product maturity: concept / prototype / MVP / production.
  - Paying customers: first revenues, recurring months.
  - Funding: secured or self-financed?
  - Distribution: any channel tested?

Do NOT ask raw financial inputs (prices, costs, credit amounts) during Phase 1.
Ask self_assessed_stage in the first 3 turns — for perception gap analysis ONLY. \
Never use the self-declared stage to drive the conversation; always verify with real criteria.

Stop Phase 1 when you can confidently name the current stage (typically 8–15 questions).

---

## PHASE 2 — NEXT STAGE VERIFICATION
After estimating the stage, probe 2–3 key criteria for the NEXT stage above to see \
whether the founder already meets them.
Example: Diagnosed MVP ? check has_paying_customers, financial_docs_exist, rne_registered \
(Levée de fonds criteria).

---

## PHASE 3 — SCORING ENRICHMENT
Goal: Fill in the fields the 5 scoring engines need.
  - Market: competitor count, local/foreign benchmark prices, market size, geographic scope.
  - Commercial: value_proposition_text, differentiation_description, pricing_model, pricing_tested.
  - Innovation: idea_is_new, foreign_model_studied, IP protection, proprietary data.
  - Scalability: distribution channels, automation level, replicability evidence.
  - Green: environmental_impact_type, SDG alignment, waste/energy/water reduction measures.

Ask these AFTER the maturity stage is established, not before.

---

## PHASE 4 — FINANCIAL INTELLIGENCE
Goal: Collect the raw financial inputs for economic and credit engines.
Fields (from context section [DONNÉES FINANCIÈRES]): selling_price, unit_cost, monthly_revenue, \
fixed_costs, credit needs, etc.

RULES FOR PHASE 4:
  - Enter Phase 4 ONLY when estimated_stage = 3 (MVP or above).
  - NEVER ask financial input details to IDÉATION or STRUCTURATION founders — it wastes the session.
  - Approach with a bridging question: "Avez-vous défini un modèle de prix ?" before unit economics.
  - If the founder says they have no pricing yet ? mark the field explicitly_unknown and move on.

---

## QUESTION SELECTION ALGORITHM — apply every turn
1. Read [Profil actuel] — what is already known?
2. Determine current phase from [Stade estimé] and pending fields by section.
3. If [CRITÈRES DE MATURITÉ] has pending fields ? Phase 1 or 2: ask the most classification-critical question.
4. If maturity is established + [DONNÉES DE SCORING] has pending fields ? Phase 3 question.
5. If scoring sufficient + estimated_stage = 3 + [DONNÉES FINANCIÈRES] has pending fields ? Phase 4 question.
6. Ask ONE question per turn. Never combine two questions.

---

## CORE RULES (every turn)
- NEVER ask financial inputs (selling_price, unit_cost, costs, credit) if estimated_stage = 2.
- NEVER mention field names, schema names, or technical terms to the founder.
- NEVER stay topic-locked: jump to the next phase as soon as current phase criteria are filled.
- Stop asking about a topic when you have sufficient evidence — confidence beats completeness.
- If strong signals already support a field value (e.g. 50+ interviews implies has_validated_problem=True), \
  extract it silently without asking.
- "je ne sais pas / pas encore / aucune idée / je ne peux pas estimer" ? explicitly_unknown.
- If the founder simply did not mention a field ? leave it PENDING. Never set it to explicitly_unknown.

---

## META-QUESTIONS
If the user asks about the process ("pourquoi vous demandez ça ?", "à quoi ça sert", \
"je ne comprends pas", "répondez-moi d'abord") ? \
set meta_response to a warm, one-sentence explanation in the founder's language of WHY this matters for their diagnosis. \
Leave next_question null — the system re-asks the same question automatically.

---

## EXTRACTION RULES
- Extract only what is clearly and explicitly stated — never infer.
- Boolean: True = clear yes, False = clear no. Omit if ambiguous.
- Numeric: bare number, no units. Percentages ? decimals (30% ? 0.30).
- List fields: JSON array of strings.
- When extracting value_proposition_text, also assess clarity 1–5 \
  (1=very vague, 5=crystal-clear: specific value + named customer + named problem) \
  and include value_prop_clarity_rating.

---

## OUTPUT FORMAT — return ONLY valid JSON, nothing else
{
    "extracted": {"field_name": value, ...},
    "explicitly_unknown": ["field_name", ...],
    "meta_response": null,
    "next_question": "The next question in the founder's language..."
}
Rules for next_question:
- Write as a real consultant would — natural, warm, context-aware of the last answer.
- Never mention field names or schema names.
- Never combine two questions into one.
- Set to null ONLY when meta_response is set.\
"""


# -- Context builders -----------------------------------------------------------

def _profile_summary(profile: Dict[str, Any]) -> str:
    if not profile:
        return "(aucune information collectée)"
    lines = []
    for k, v in profile.items():
        lines.append(f"  {k} = {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lines)


def _profile_summary_for_llm(profile: Dict[str, Any], project_name: str) -> str:
    enterprise_for_llm = pii_for_llm(project_name)
    gerant_for_llm = pii_for_llm(profile.get("gerant")) if profile.get("gerant") is not None else None

    lines = [
        f"  enterprise_name = {json.dumps(enterprise_for_llm, ensure_ascii=False)}",
        f"  gerant = {json.dumps(gerant_for_llm, ensure_ascii=False)}",
    ]
    if not profile:
        return "\n".join(lines + ["  (aucune autre information collectee)"])

    for k, v in profile.items():
        if k == "gerant":
            continue
        lines.append(f"  {k} = {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lines)


def _pending_fields_for(
    field_states: Dict[str, str],
    profile: Dict[str, Any],
    estimated_stage: int,
    include: Optional[frozenset],
    exclude: Optional[frozenset] = None,
) -> str:
    """Return pending eligible fields filtered by include/exclude sets."""
    lines = []
    for field, meta in FIELD_META.items():
        if field in DERIVED_FIELDS:
            continue
        if field_states.get(field, PENDING) != PENDING:
            continue
        if not is_eligible(field, meta, profile, estimated_stage):
            continue
        if include is not None and field not in include:
            continue
        if exclude is not None and field in exclude:
            continue

        tags = []
        if not meta.get("can_be_explicitly_unknown", True):
            tags.append("REQUIRED")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        hint = f": {meta['question_fr']}" if meta.get("question_fr") else ""
        lines.append(f"  - {field}{tag_str}{hint}")

    return "\n".join(lines) if lines else "  (aucun)"


def _recent_history(history: List[Dict[str, str]], n_turns: int = 4) -> str:
    """Last n_turns of conversation as readable text, for LLM context."""
    recent = history[-n_turns * 2:]
    if not recent:
        return "(aucun échange précédent)"
    lines = []
    for m in recent:
        role = "Consultant" if m["role"] == "assistant" else "Fondateur"
        lines.append(f"{role} : {m['content']}")
    return "\n".join(lines)


# -- Main function --------------------------------------------------------------

def consult(
    project_name: str,
    profile: Dict[str, Any],
    field_states: Dict[str, str],
    estimated_stage: int,
    conversation_history: List[Dict[str, str]],
    last_user_message: Optional[str],
    call_llm: Callable[[List[Dict[str, str]]], str],
    contradictions: Optional[List[Dict[str, Any]]] = None,
) -> ConsultResult:
    """
    Single LLM call: extract fields from the last answer AND generate the
    next best question.

    When last_user_message is None (session start), extraction is skipped
    and only the opening question is generated.
    """
    profile_text = _profile_summary_for_llm(profile, project_name)
    history_text = _recent_history(conversation_history)

    stage_label = _STAGE_NAMES.get(estimated_stage, f"stade {estimated_stage}")
    next_stage = min(estimated_stage + 1, 6)
    next_label  = _STAGE_NAMES.get(next_stage, "CROISSANCE")

    # Phase 1+2: maturity classifier fields
    maturity_fields = _pending_fields_for(
        field_states, profile, estimated_stage,
        include=_CLASSIFIER_FIELDS,
    )
    # Phase 3: scoring fields (non-classifier, non-financial)
    scoring_fields = _pending_fields_for(
        field_states, profile, estimated_stage,
        include=None,
        exclude=_CLASSIFIER_FIELDS | _FINANCIAL_FIELDS | DERIVED_FIELDS,
    )
    # Phase 4: financial inputs (only relevant at MVP+)
    financial_fields = _pending_fields_for(
        field_states, profile, estimated_stage,
        include=_FINANCIAL_FIELDS,
    )

    stage_block = (
        f"[Stade estimé : {stage_label}  ?  prochain stade à vérifier : {next_label}]\n"
        f"(estimated_stage = {estimated_stage})"
    )
    pii_block = (
        "[Visibilite PII LLM]\n"
        f"- enterprise_name et gerant sont fournis en mode: {llm_pii_mode()}.\n"
        "- Si les valeurs commencent par enc:v1:, traitez-les comme identifiants opaques."
    )

    contradiction_block = ""
    if contradictions:
        lines = []
        for c in contradictions:
            lines.append(f"  - {c['field']}: était «{c['old']}», maintenant «{c['new']}»")
        contradiction_block = (
            "\n[? CONTRADICTIONS DÉTECTÉES — valider avec le fondateur]\n"
            + "\n".join(lines)
            + "\nRègle : intégrez une courte confirmation naturelle dans next_question "
            "(ex: «Vous m'aviez mentionné X — je note Y, c'est bien ça ?»), "
            "puis enchaînez avec la vraie prochaine question. Ne bloquez pas sur la contradiction.\n"
        )

    if last_user_message is None:
        user_content = (
            f"[Profil actuel]\n{profile_text}\n\n"
            f"{pii_block}\n\n"
            f"{stage_block}\n\n"
            f"[CRITÈRES DE MATURITÉ EN ATTENTE — Phase 1 & 2]\n{maturity_fields}\n\n"
            f"[DONNÉES DE SCORING EN ATTENTE — Phase 3]\n{scoring_fields}\n\n"
            f"[DONNÉES FINANCIÈRES EN ATTENTE — Phase 4, stade = MVP uniquement]\n{financial_fields}\n\n"
            "[Début de l'entretien]\n"
            "Ouvrez par une question naturelle et ouverte sur le porteur du projet et son équipe : "
            "qui sont-ils, quelles compétences apportent-ils, quelle est leur expérience entrepreneuriale. "
            "Une seule question, chaleureuse, qui invite le fondateur à se présenter et à parler de son équipe.\n"
            "Retournez uniquement le JSON avec extracted={}, explicitly_unknown=[], "
            "meta_response=null, et next_question=la question d'ouverture."
        )
    else:
        user_content = (
            f"[Profil actuel]\n{profile_text}\n\n"
            f"{pii_block}\n\n"
            f"{stage_block}\n\n"
            f"[CRITÈRES DE MATURITÉ EN ATTENTE — Phase 1 & 2]\n{maturity_fields}\n\n"
            f"[DONNÉES DE SCORING EN ATTENTE — Phase 3]\n{scoring_fields}\n\n"
            f"[DONNÉES FINANCIÈRES EN ATTENTE — Phase 4, stade = MVP uniquement]\n{financial_fields}\n"
            f"{contradiction_block}\n"
            f"[Échanges récents]\n{history_text}\n\n"
            f"[Dernière réponse du fondateur]\n{last_user_message}"
        )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    raw = call_llm(messages)
    return _parse(raw)


def _parse(raw: str) -> ConsultResult:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return ConsultResult(extracted={}, explicitly_unknown=[], meta_response=None, next_question=None)

    allowed = set(FIELD_META.keys()) | _ALLOWED_EXTRA
    extracted = {k: v for k, v in data.get("extracted", {}).items() if k in allowed}
    explicitly_unknown = [f for f in data.get("explicitly_unknown", []) if f in FIELD_META]

    return ConsultResult(
        extracted=extracted,
        explicitly_unknown=explicitly_unknown,
        meta_response=data.get("meta_response") or None,
        next_question=data.get("next_question") or None,
    )


