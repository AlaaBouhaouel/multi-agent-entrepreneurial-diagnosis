"""
roadmap/llm.py

LLM clients for the roadmap layer.

Split by job (per the architecture decision):
  - RoadmapLLM (Anthropic / Claude Opus 4.8)
        Structured synthesis: takes already-retrieved, already-ranked KB items +
        the gap profile and emits ordered roadmap actions as JSON. The
        "intelligence" is in the deterministic gap analyzer + retrieval ranking;
        the LLM only phrases and orders grounded actions. It is forbidden from
        inventing resources (enforced by _validate_grounding).

  - The grounded ASSISTANT conversation is handled separately by Sonnet 4.6 —
        see assistant.py. Opus builds the artifact; Sonnet talks about it.

Every client degrades to a deterministic template generator when no model is
reachable, so the pipeline always produces a valid roadmap (important for demos
and CI). The template path is clearly labelled in the output.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


ROADMAP_MODEL = "claude-opus-4-8"

# Strict, grounding-focused system prompt. The model is told it may ONLY phrase
# and order the actions we hand it — never add resources.
ROADMAP_SYSTEM_PROMPT = """Tu es le moteur de feuille de route de LeadIt, un système d'orientation entrepreneuriale tunisien.

RÔLE STRICT : tu reçois (1) un diagnostic de projet, (2) une liste de RESSOURCES DÉJÀ SÉLECTIONNÉES depuis une base de connaissances vérifiée, et (3) les blocages prioritaires. Tu dois produire une feuille de route ORDONNÉE et PRIORISÉE.

RÈGLES ABSOLUES :
- N'invente JAMAIS de nom de programme, de montant, de procédure ou de ressource. Utilise UNIQUEMENT les ressources fournies, référencées par leur resource_id.
- Chaque action doit citer le resource_id de la ressource sur laquelle elle s'appuie. Si une action ne s'appuie sur aucune ressource fournie, ne la produis pas.
- Classe les actions en trois horizons : "immediate", "short_term", "medium_term".
- Une action a un ordre, une justification ancrée dans le diagnostic, et un horizon. Ce n'est pas une liste plate.
- Réponds en français.
- Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après, sans balises Markdown.
- always explain each generated step of the roadmap, what the user needs to do and not just dump websites.


FORMAT DE SORTIE (JSON strict) :
{
  "roadmap": [
    {
      "order": 1,
      "horizon": "immediate",
      "title": "Titre court de l'action",
      "rationale_fr": "Pourquoi cette action, ancrée dans le diagnostic (phase, blocage).",
      "resource_id": "id_de_la_ressource_fournie",
      "domain": "financier|légal|marché|organisationnel|technique|green"
    }
  ]
}"""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Pull the first JSON object out of a model response, tolerating stray text."""
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
    if candidate is None:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


class RoadmapLLM:
    """Anthropic-backed roadmap synthesizer (Claude Opus 4.8) with a deterministic fallback."""

    def __init__(self, model: str = ROADMAP_MODEL, api_key: Optional[str] = None,
                 max_tokens: int = 2048):
        self.model = model
        self.max_tokens = max_tokens
        self._client = None
        try:
            import os
            from anthropic import Anthropic
            self._client = Anthropic(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
                timeout=20.0,
                max_retries=0,
            )
        except Exception:
            self._client = None

    # ---- transport -----------------------------------------------------------

    def _call_anthropic(self, system: str, user: str) -> Optional[str]:
        # NOTE: no `temperature` — Opus 4.8/4.7 reject sampling params with a 400.
        # `thinking` is omitted: this is a strict-JSON ordering task guarded by
        # _validate_grounding + the template fallback, so no-thinking is correct.
        if self._client is None:
            return None
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
            return text
        except Exception:
            return None

    # ---- public API ----------------------------------------------------------

    def synthesize(self, prompt_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        prompt_payload is the grounded context built by the roadmap engine.
        Returns {"roadmap": [...], "_source": "llm"|"template"}.
        """
        user = json.dumps(prompt_payload, ensure_ascii=False, indent=2)
        # We append a trailing instruction since Claude expects clear JSON formatting constraints
        user += "\n\nRenvoie UNIQUEMENT le JSON comme demandé, sans aucun autre texte."
        raw = self._call_anthropic(ROADMAP_SYSTEM_PROMPT, user)
        parsed = _extract_json(raw) if raw else None

        if parsed and isinstance(parsed.get("roadmap"), list) and parsed["roadmap"]:
            cleaned = self._validate_grounding(parsed["roadmap"], prompt_payload)
            if cleaned:
                return {"roadmap": cleaned, "_source": "llm"}

        # fallback — deterministic, still fully grounded
        return {"roadmap": self._template_roadmap(prompt_payload), "_source": "template"}

    # ---- grounding guard -----------------------------------------------------

    @staticmethod
    def _validate_grounding(actions: List[Dict[str, Any]],
                            payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Drop any LLM action whose resource_id is not in the supplied resources.
        This is the hard anti-hallucination gate: §2.5.5 — a recommendation that
        cannot be traced to a KB item is a critical failure.
        """
        valid_ids = {r["resource_id"] for r in payload.get("resources", [])}
        out = []
        for a in actions:
            rid = a.get("resource_id")
            if rid in valid_ids:
                out.append({
                    "order":       a.get("order"),
                    "horizon":     a.get("horizon", "short_term"),
                    "title":       a.get("title", ""),
                    "rationale_fr": a.get("rationale_fr", ""),
                    "resource_id": rid,
                    "domain":      a.get("domain"),
                })
        for i, a in enumerate(sorted(out, key=lambda x: x.get("order") or 999), start=1):
            a["order"] = i
        return out

    # ---- deterministic fallback ---------------------------------------------

    @staticmethod
    def _template_roadmap(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build a grounded roadmap without an LLM: map the top-ranked resources
        into horizons by their domain's priority. Fully traceable.
        """
        horizons = ["immediate", "short_term", "medium_term"]
        resources = payload.get("resources", [])
        actions: List[Dict[str, Any]] = []
        for i, r in enumerate(resources):
            horizon = horizons[min(i // max(1, (len(resources) // 3 or 1)), 2)]
            desc = r.get("description", "")
            bene = r.get("benefits", "")
            
            rationale = r.get("why_matched", "")
            if desc:
                rationale += f" Ce que c'est : {desc}"
            if bene:
                rationale += f" Bénéfices attendus : {bene}"
                
            actions.append({
                "order":       i + 1,
                "horizon":     horizon,
                "title":       f"Mobiliser : {r.get('name')}",
                "rationale_fr": rationale.strip(),
                "resource_id": r["resource_id"],
                "domain":      (r.get("matched_domains") or [None])[0],
            })
        return actions
