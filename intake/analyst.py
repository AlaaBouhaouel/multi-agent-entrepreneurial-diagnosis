"""
intake/analyst.py

Post-intake analysis and grounded Q&A session.

After the intake engine finishes collecting the profile, this module:
  1. Runs the rule-based diagnostic and scoring engines (no DB writes).
  2. Builds a rich structured context from the results.
  3. Exposes an AnalystSession for LLM-powered presentation and follow-up Q&A.

The LLM's role here is presentation and explanation only —
all scores and stage classification are produced by the deterministic engines.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .pii import llm_pii_mode, pii_for_llm


# ── Stage labels ───────────────────────────────────────────────────────────────

_STAGE_FR = {
    "IDEATION":      "Idéation (stade 1)",
    "STRUCTURATION": "Structuration (stade 2)",
    "MVP":           "MVP (stade 3)",
    "FUNDRAISING":   "Levée de fonds (stade 4)",
    "ACCELERATION":  "Accélération (stade 5)",
    "GROWTH":        "Croissance (stade 6)",
}

_DIM_FR = {
    "market":      "Santé financière",
    "commercial":  "Offre commerciale",
    "innovation":  "Innovation",
    "scalability": "Scalabilité",
    "green":       "Impact vert",
}


# ── Engine runner ──────────────────────────────────────────────────────────────

def _mock_django_if_needed() -> None:
    """Mock Django DB modules so pure-function engines can be imported without a DB."""
    try:
        from django.conf import settings
        settings.DATABASES  # raises if Django not configured
        return
    except Exception:
        pass
    from unittest.mock import MagicMock
    for mod in [
        "django", "django.db", "django.db.models",
        "django.db.models.base", "django.db.models.fields",
        "projects", "projects.models",
    ]:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()


def _ensure_criteria_path() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    criteria_path = os.path.join(root, "criteria")
    if criteria_path not in sys.path:
        sys.path.insert(0, criteria_path)
    if root not in sys.path:
        sys.path.insert(0, root)


def run_analysis(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run diagnostic + scoring on a profile dict without any DB writes.
    Returns a structured analysis dict.
    """
    _ensure_criteria_path()
    _mock_django_if_needed()

    from diagnostic.services import (
        stage_classification, compute_confidence,
        detect_perception_gap, extract_failed_criteria, identify_blockers,
    )
    from diagnostic.metrics import derive_all_metrics
    from scorers.market import score_market
    from scorers.commercial import score_commercial
    from scorers.innovation import score_innovation
    from scorers.scalability import score_scalability
    from scorers.green import score_green

    # ── Stage diagnosis ──────────────────────────────────────────────────────
    classification = stage_classification(profile)
    assigned_stage = classification["assigned_stage"]
    evidence       = classification["evidence"]
    stopped_at     = classification["stopped_at"]

    failed     = extract_failed_criteria(evidence)
    blockers   = identify_blockers(failed)
    confidence = compute_confidence(evidence)
    gap        = detect_perception_gap(profile, assigned_stage)

    # ── Scoring ──────────────────────────────────────────────────────────────
    metrics = derive_all_metrics(profile)
    scores = {
        "market":      score_market(profile, metrics),
        "commercial":  score_commercial(profile, metrics),
        "innovation":  score_innovation(profile, metrics),
        "scalability": score_scalability(profile, metrics),
        "green":       score_green(profile, metrics),
    }

    return {
        "assigned_stage":  assigned_stage,
        "stopped_at":      stopped_at,
        "confidence":      confidence,
        "perception_gap":  gap,
        "blockers":        blockers,
        "failed_criteria": failed,
        "metrics":         metrics,
        "scores":          scores,
    }


# ── Context builder ────────────────────────────────────────────────────────────

def _fmt_score(result: Optional[Dict]) -> str:
    if result is None:
        return "N/A"
    s = result.get("score")
    if s is None:
        return "insuffisant (données manquantes)"
    floor_met = result.get("floor_met", True)
    flag = " ⚠ plancher non atteint" if not floor_met else ""
    return f"{s:.1f}/10{flag}"


def build_context(profile: Dict[str, Any], analysis: Dict[str, Any], project_name: str = "Projet") -> str:
    """Build a rich plaintext briefing for the analyst LLM."""
    lines = ["## PROFIL COLLECTÉ"]
    lines.append(" Le nom de l' Entreprise est anonyme ")
    lines.append(" Le nom du gerant est anonyme ")
    lines.append(f"  pii_mode = {llm_pii_mode()}")
    for k, v in profile.items():
        if k == "gerant":
            continue
        lines.append(f"  {k} = {json.dumps(v, ensure_ascii=False)}")

    stage_fr = _STAGE_FR.get(analysis["assigned_stage"], analysis["assigned_stage"])
    conf     = analysis["confidence"]
    gap      = analysis["perception_gap"]
    blockers = analysis["blockers"]
    metrics  = analysis["metrics"]
    scores   = analysis["scores"]

    lines += [
        "",
        "## DIAGNOSTIC DE MATURITÉ",
        f"  Stade assigné  : {stage_fr}",
        f"  Bloqué à       : {analysis['stopped_at'] or 'N/A'}",
        f"  Confiance      : {conf['level']} ({conf['score']:.0%} des critères renseignés)",
    ]

    if gap.get("divergence"):
        direction = "surestimation" if gap["gap_direction"] == "overestimate" else "sous-estimation"
        lines.append(
            f"  Écart perception : {direction} de {gap['gap_size']} stade(s) "
            f"(déclaré: {gap['self_assessed_stage']}, assigné: {gap['diagnosed_stage']})"
        )
    else:
        lines.append("  Écart perception : aligné")

    if blockers.get("ranked_domains"):
        lines.append(f"  Domaines bloqueurs : {', '.join(blockers['ranked_domains'])}")

    lines += [
        "",
        "## SCORES DE SANTÉ (0–10)",
    ]
    for dim, label in _DIM_FR.items(): #explain each score, its weight  and its sub criteria if there is.
        lines.append(f"  {label:<22}: {_fmt_score(scores.get(dim))}")

    lines += [
        "",
        "## MÉTRIQUES FINANCIÈRES",
    ]
    financial_keys = [
        "gross_margin_ratio", "breakeven_months", "opex_months_covered",
        "credit_eligibility_path", "credit_gap_exists", "van_5_years",
    ]
    for k in financial_keys:
        v = metrics.get(k)
        if v is not None:
            lines.append(f"  {k} = {v}")
    lines += [
        "",
        "## ROADMAP",
    ]

    #retrieve the results of the roadmap 

    lines += [
        "",
        "## CRITÈRES NON SATISFAITS",
    ]
    for item in analysis["failed_criteria"][:10]:
        val = "Faux" if item["value"] is False else "Données manquantes"
        lines.append(f"  [{item['stage']}] {item['criterion']} — {val}")

    return "\n".join(lines)


# ── System prompt ──────────────────────────────────────────────────────────────

_ANALYST_SYSTEM_PROMPT = """\
You are a senior startup consultant who has just completed a discovery interview with a founder \
on the LeadIt platform in Tunisia.
You have access to the complete Project Profile and the results of a full diagnostic and scoring analysis.
Your role now shifts from interviewer to advisor.

## YOUR TASK
1. When asked to present: deliver a clear, honest, structured consultant-style diagnosis in French.
   - Start with the maturity stage and what it means concretely.
   - Report the 5 health scores with a one-sentence interpretation each.
   - Highlight the 2–3 most critical gaps the founder must address.
   - Acknowledge strong signals honestly.
   - If there is a perception gap, name it tactfully but clearly.
2. When asked a follow-up question: answer grounded exclusively in the profile data and analysis.
   - If the data supports a clear answer, give it.
   - If the data is insufficient, say so honestly — do not invent.
   - You may make recommendations, but always reference the specific data that supports them.

## TONE
Professional, warm, direct. Like a consultant who respects the founder's effort \
but will not sugarcoat the gaps. Speak in French at all times.

## CONSTRAINTS
- Never mention field names, schema names, or technical terms to the founder.
- Never claim the project is better or worse than the data shows.
- Never make up numbers or facts not present in the profile or analysis.
- Scores and stage are produced by the system — do not question or override them.\
"""


# ── Session ────────────────────────────────────────────────────────────────────

class AnalystSession:
    """
    Post-intake analysis session.

    Usage:
        analysis = run_analysis(profile_dict)
        session = AnalystSession(profile_dict, analysis, call_llm)

        print(session.present())      # initial consultant report

        while True:
            q = input("> ")
            print(session.ask(q))
    """

    def __init__(
        self,
        profile: Dict[str, Any],
        analysis: Dict[str, Any],
        call_llm: Callable[[List[Dict[str, str]]], str],
        project_name: str = "Projet",
    ) -> None:
        self._call_llm = call_llm
        self._context  = build_context(profile, analysis, project_name=project_name)
        self._history: List[Dict[str, str]] = []

    def present(self) -> str:
        """Generate the opening diagnostic presentation."""
        return self._chat(
            "Présentez maintenant une synthèse complète et honnête du diagnostic de ce projet. "
            "Commencez par le stade de maturité, puis les scores de santé, puis les axes prioritaires d'amélioration."
        )

    def ask(self, question: str) -> str:
        """Answer a follow-up question grounded in the profile and analysis."""
        return self._chat(question)

    # ── Internal ───────────────────────────────────────────────────────────

    def _chat(self, user_message: str) -> str:
        self._history.append({"role": "user", "content": user_message})

        messages = [
            {"role": "system", "content": _ANALYST_SYSTEM_PROMPT},
            # Grounding context as a pinned first exchange
            {"role": "user",      "content": f"Voici le dossier complet du projet :\n\n{self._context}"},
            {"role": "assistant", "content": "Dossier analysé. Je suis prêt à présenter le diagnostic."},
            *self._history,
        ]

        response = self._call_llm(messages)
        self._history.append({"role": "assistant", "content": response})
        return response
