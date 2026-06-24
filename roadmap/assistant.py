"""
roadmap/assistant.py

The Grounded Conversational Assistant — the SECONDARY layer (brief §1.6: the
assistant is NOT the core product; it operates only on the structured outputs of
the other features).

Per your decision: this conversation runs on Claude Sonnet (your Anthropic Pro
API key), because open-ended Q&A benefits from a stronger model — while the
deterministic roadmap was already built by the local Qwen model. The assistant
NEVER re-runs diagnosis/scoring/retrieval and NEVER invents resources.

Grounding contract
------------------
The assistant's system prompt is assembled ONLY from:
  - the diagnostic summary
  - the 5 scores + justifications
  - the ranked gaps
  - the roadmap actions (with resource_ids + source_urls)
  - the matched KB entries (and nothing else from the KB)

If the answer is not in that context, it must say so. Every answer should cite
where it came from (a diagnostic result, a score, a gap, or a resource_id).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


ASSISTANT_MODEL = "claude-sonnet-4-6"

ASSISTANT_SYSTEM_TEMPLATE = """Tu es l'assistant LeadIt pour ce projet entrepreneurial.

Tu réponds UNIQUEMENT à partir des données structurées ci-dessous, produites par
les moteurs de diagnostic, de scoring et de feuille de route. 

RÈGLES :
- Si la réponse n'est pas dans ces données, dis-le clairement : « Je n'ai pas cette information dans votre dossier. »
- N'invente JAMAIS de nom de programme, de montant, de procédure ou de ressource.
- Cite toujours ta source : un résultat de diagnostic, un score, un blocage, ou un resource_id de la feuille de route.
- Tu ne recalcules rien. Tu lis les résultats, tu ne les produis pas.
- Réponds dans la langue de l'utilisateur (français ou arabe).

═══════════ DIAGNOSTIC ═══════════
{diagnostic_block}

═══════════ SCORES ═══════════
{scores_block}

═══════════ BLOCAGES PRIORITAIRES ═══════════
{gaps_block}

═══════════ FEUILLE DE ROUTE ═══════════
{roadmap_block}

═══════════ RESSOURCES (base de connaissances) ═══════════
{kb_block}
"""


def _fmt_diagnostic(diagnosis: Dict[str, Any]) -> str:
    pg = diagnosis.get("perception_gap") or {}
    conf = diagnosis.get("confidence") or {}
    return (
        f"Phase diagnostiquée : {diagnosis.get('assigned_stage')} "
        f"(index {diagnosis.get('assigned_stage_index')})\n"
        f"Auto-évaluation : {pg.get('self_assessed_stage')} | "
        f"Écart de perception : {pg.get('gap_direction')} (taille {pg.get('gap_size')})\n"
        f"Confiance : {conf.get('level')} (score {conf.get('score')})"
    )


def _fmt_scores(scoring: Dict[str, Any]) -> str:
    lines = []
    for dim, res in (scoring.get("scores") or {}).items():
        if not isinstance(res, dict):
            continue
        lines.append(f"- {dim} : {res.get('score')}/10 (plancher atteint : {res.get('floor_met')})")
    return "\n".join(lines) or "Aucun score disponible."


def _fmt_gaps(roadmap_output: Dict[str, Any]) -> str:
    domains = roadmap_output.get("ranked_domains", [])
    unmatched = roadmap_output.get("unmatched_gaps", [])
    out = "Domaines de blocage (par priorité) : " + ", ".join(domains)
    if unmatched:
        out += "\nBlocages sans ressource KB : " + ", ".join(u["domain"] for u in unmatched)
    return out


def _fmt_roadmap(roadmap_output: Dict[str, Any]) -> str:
    lines = []
    for action in roadmap_output.get("roadmap_flat", []):
        lines.append(
            f"[{action.get('horizon')}] #{action.get('order')} {action.get('title')} "
            f"→ {action.get('resource_name')} ({action.get('resource_id')}) "
            f"| {action.get('rationale_fr')} | source: {action.get('source_url')}"
        )
    return "\n".join(lines) or "Aucune action."


def _fmt_kb(roadmap_output: Dict[str, Any]) -> str:
    lines = []
    for r in roadmap_output.get("matched_resources", []):
        e = r.get("entry", {})
        lines.append(
            f"- {r['resource_id']} | {r['name']} ({r['provider']}) "
            f"| {e.get('benefits','')} | éligibilité: {e.get('eligibility','')} "
            f"| source: {r['source_url']}"
        )
    return "\n".join(lines) or "Aucune ressource."


def build_assistant_context(diagnosis: Dict[str, Any],
                            scoring: Dict[str, Any],
                            roadmap_output: Dict[str, Any]) -> str:
    """Assemble the read-only grounding system prompt for the assistant."""
    return ASSISTANT_SYSTEM_TEMPLATE.format(
        diagnostic_block=_fmt_diagnostic(diagnosis),
        scores_block=_fmt_scores(scoring),
        gaps_block=_fmt_gaps(roadmap_output),
        roadmap_block=_fmt_roadmap(roadmap_output),
        kb_block=_fmt_kb(roadmap_output),
    )


class GroundedAssistant:
    """
    Thin wrapper over the Anthropic Messages API (Sonnet). Holds the grounding
    context as the system prompt; forwards user turns. Degrades gracefully if the
    SDK/key is absent (returns a clear message rather than crashing a demo).
    """
    def __init__(self, system_context: str, model: str = ASSISTANT_MODEL,
                 api_key: Optional[str] = None, max_tokens: int = 1024):
        self.system_context = system_context
        self.model = model
        self.max_tokens = max_tokens
        self._client = None
        try:
            import os
            from anthropic import Anthropic
            self._client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        except Exception:
            self._client = None

    def ask(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        messages : [{"role": "user"|"assistant", "content": "..."}]
        Returns {"reply": str, "_source": "sonnet"|"unavailable"}.
        """
        if self._client is None:
            return {
                "reply": ("Assistant indisponible (clé API ou SDK Anthropic manquant). "
                          "La feuille de route reste consultable dans le tableau de bord."),
                "_source": "unavailable",
            }
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_context,
                messages=messages,
            )
            text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
            return {"reply": text, "_source": "sonnet"}
        except Exception as exc:
            return {"reply": f"Erreur de l'assistant : {exc}", "_source": "error"}
