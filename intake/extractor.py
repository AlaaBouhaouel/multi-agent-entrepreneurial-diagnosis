"""
intake/extractor.py

LLM-powered extraction: converts a founder's natural-language answer into
typed, structured field values.

Wire up your LLM by passing a `call_llm` callable to `extract_fields()`.

    call_llm signature:
        (messages: list[dict]) -> str

    where each message is {"role": "system"|"user"|"assistant", "content": str}
    and the return value is the model's plain-text response (JSON expected).

──────────────────────────────────────────────────────────────────────────────
Anthropic wiring example (claude-sonnet-4-6):

    from anthropic import Anthropic

    _client = Anthropic(api_key="YOUR_API_KEY")

    def call_llm(messages: list[dict]) -> str:
        system = ""
        chat = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                chat.append(m)
        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=chat,
        )
        return response.content[0].text
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .field_metadata import DERIVED_FIELDS, FIELD_META

# Fields the extractor is allowed to populate in addition to those explicitly
# listed — includes derived fields the LLM assesses automatically.
_ALLOWED_EXTRA = {"value_prop_clarity_rating"}


@dataclass
class ExtractionResult:
    extracted: Dict[str, Any]          # field_name → typed value
    explicitly_unknown: List[str]       # fields the founder said they don't know
    needs_clarification: Optional[str]  # SHORT follow-up probe for the primary field, or None
    meta_response: Optional[str]        # explanation when user asked "why do you need this?"


def _build_field_descriptions(field_names: List[str]) -> str:
    """
    Build a concise field list for the LLM prompt, pulling type hints from
    the Pydantic schema so the model knows what format to return.
    """
    try:
        from projects.schemas import ProjectProfileData
        model_fields = ProjectProfileData.model_fields
    except Exception:
        model_fields = {}

    lines = []
    for name in field_names:
        meta = FIELD_META.get(name, {})
        field_info = model_fields.get(name)
        if field_info is not None:
            type_str = str(field_info.annotation)
            # Strip typing noise: Optional[int] → int
            type_str = re.sub(r"typing\.Optional\[(.+)\]", r"\1", type_str)
            type_str = type_str.replace("typing.", "")
        else:
            type_str = "any"

        required = not meta.get("can_be_explicitly_unknown", True)
        tag = " [REQUIRED]" if required else " [can be unknown]"
        lines.append(f"  - {name} ({type_str}){tag}")

    return "\n".join(lines)


_SYSTEM_PROMPT = """\
You are a structured-data extraction assistant for an entrepreneurial assessment platform in Tunisia.
Your job is to extract profile fields from a founder's conversational answer in French (or mixed French/Arabic/Darija).

RULES
1. Only extract values that are clearly stated — never infer, guess, or assume.
2. If the founder explicitly says they don't know, haven't done it yet, can't estimate, \
or have no information → add that field to "explicitly_unknown".
3. Fields marked [REQUIRED] cannot be left unknown. If the answer is genuinely ambiguous \
for a REQUIRED field (they gave some information but it is unclear), \
set "needs_clarification" to ONE short French follow-up probe targeting only that field. \
Do NOT generate new multi-field questions. Do NOT set needs_clarification if there is nothing ambiguous.
4. Fields marked [can be unknown] → accept "je ne sais pas" or equivalent as a valid response.
5. Boolean fields: True = clear yes, False = clear no. Omit the field if truly ambiguous.
6. Numeric fields: extract the bare number only (no currency, no units). \
Convert percentages to decimals (30% → 0.30).
7. List fields: return a JSON array of strings.
8. A single answer may reveal values for multiple fields — extract ALL of them.
9. When extracting value_proposition_text, also assess its clarity on a scale of 1–5 \
(1 = very vague, 5 = crystal clear: specific value + named target customer + named problem) \
and include value_prop_clarity_rating in "extracted".
10. META-QUESTIONS: If the founder's message is a question ABOUT the process — \
e.g. "pourquoi vous demandez ça ?", "à quoi sert cette question ?", "je ne comprends pas", \
"répondez-moi d'abord" — do NOT extract any fields and do NOT set needs_clarification. \
Instead, set "meta_response" to a warm, one-sentence French explanation of why this \
information matters for their diagnosis. The system will automatically re-ask the original question.
11. Return ONLY valid JSON — no markdown, no text outside the JSON object.

OUTPUT FORMAT (always return exactly this shape):
{
    "extracted": {},
    "explicitly_unknown": [],
    "needs_clarification": null,
    "meta_response": null
}
Populate only the relevant keys.\
"""


def extract_fields(
    question: str,
    primary_field: str,
    related_fields: List[str],
    user_answer: str,
    conversation_history: List[Dict[str, str]],
    call_llm: Callable[[List[Dict[str, str]]], str],
) -> ExtractionResult:
    """
    Call the LLM to extract structured field values from one founder answer.

    Parameters
    ----------
    question : str
        The question that was just asked (gives the LLM context for what field
        we were targeting).
    primary_field : str
        The field we explicitly asked about — listed first in the field descriptions.
    related_fields : list[str]
        Other pending fields to opportunistically extract if the answer mentions them.
    user_answer : str
        Raw answer from the founder.
    conversation_history : list[dict]
        Prior turns in role/content format (excludes the current user message).
    call_llm : callable
        Your LLM client function.
    """
    all_fields = [primary_field] + [f for f in related_fields if f != primary_field]
    field_descriptions = _build_field_descriptions(all_fields)

    user_content = (
        f"Question demandée : {question}\n\n"
        f"Réponse du fondateur : {user_answer}\n\n"
        f"Champs à extraire :\n{field_descriptions}"
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        *conversation_history,
        {"role": "user", "content": user_content},
    ]

    raw = call_llm(messages)
    return _parse_response(raw)


def _parse_response(raw: str) -> ExtractionResult:
    """
    Parse the LLM's JSON response into an ExtractionResult.
    Degrades gracefully on malformed output — returns empty result so the
    engine re-asks rather than crashing.
    """
    # Strip markdown code fences the model sometimes adds
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return ExtractionResult(extracted={}, explicitly_unknown=[], needs_clarification=None)

    allowed = set(FIELD_META.keys()) | _ALLOWED_EXTRA
    extracted = {k: v for k, v in data.get("extracted", {}).items() if k in allowed}
    explicitly_unknown = [f for f in data.get("explicitly_unknown", []) if f in FIELD_META]
    clarification = data.get("needs_clarification") or None
    meta_response = data.get("meta_response") or None

    return ExtractionResult(
        extracted=extracted,
        explicitly_unknown=explicitly_unknown,
        needs_clarification=clarification,
        meta_response=meta_response,
    )
