"""
scorers/green.py

Green / sustainability scoring engine (0-10).

Answers: "Does this project actively reduce its environmental footprint?"

Reads profile fields directly — no financial metrics needed.
All fields are nullable (asked at IDEATION, all optional).
None = not answered yet; truthy string/list = practice described; falsy = no practice.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from criteria.calculations import _get_profile_value, _is_truthy
from .scoring_utils import build_result, leaf

_FLOOR = 4.0


def score_green(profile: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    del metrics  # green reads profile directly; financial layer not needed
    leaves = [
        _impact_declared(profile),
        _waste_reduction(profile),
        _energy_efficiency(profile),
        _water_conservation(profile),
        _resource_efficiency(profile),
        _circular_economy(profile),
        _sdg_commitment(profile),
    ]
    return build_result(leaves, _FLOOR)


# ── Leaves ────────────────────────────────────────────────────────────────────

def _impact_declared(profile: Any) -> Dict[str, Any]:
    """
    Has the founder identified and described their environmental impact?
    Type alone signals awareness; type + description signals commitment.
    """
    impact_type = _get_profile_value(profile, "environmental_impact_type")
    description = _get_profile_value(profile, "environmental_impact_description")
    score: Optional[float]
    if impact_type is None:
        score = None
    elif impact_type == "aucun":
        score = 0.0
    elif description:
        score = 10.0
    else:
        score = 6.0   # type declared but not described
    return leaf(
        criterion    = "impact_declared",
        label_fr     = "Impact environnemental déclaré et décrit",
        score        = score,
        weight       = 0.20,
        evidence     = {
            "environmental_impact_type":        impact_type,
            "environmental_impact_description": bool(description),
        },
        justification = f"impact_type={impact_type}, description={'set' if description else 'missing'} → score {score}",
    )


def _waste_reduction(profile: Any) -> Dict[str, Any]:
    measures = _get_profile_value(profile, "waste_reduction_measures")
    score    = _text_score(measures)
    return leaf(
        criterion    = "waste_reduction",
        label_fr     = "Réduction des déchets",
        score        = score,
        weight       = 0.15,
        evidence     = {"waste_reduction_measures": bool(measures)},
        justification = f"waste_reduction_measures={'described' if measures else 'missing'} → score {score}",
    )


def _energy_efficiency(profile: Any) -> Dict[str, Any]:
    measures = _get_profile_value(profile, "energy_reduction_measures")
    score    = _text_score(measures)
    return leaf(
        criterion    = "energy_efficiency",
        label_fr     = "Efficacité énergétique",
        score        = score,
        weight       = 0.15,
        evidence     = {"energy_reduction_measures": bool(measures)},
        justification = f"energy_reduction_measures={'described' if measures else 'missing'} → score {score}",
    )


def _water_conservation(profile: Any) -> Dict[str, Any]:
    measures = _get_profile_value(profile, "water_reduction_measures")
    score    = _text_score(measures)
    return leaf(
        criterion    = "water_conservation",
        label_fr     = "Conservation de l'eau",
        score        = score,
        weight       = 0.10,
        evidence     = {"water_reduction_measures": bool(measures)},
        justification = f"water_reduction_measures={'described' if measures else 'missing'} → score {score}",
    )


def _resource_efficiency(profile: Any) -> Dict[str, Any]:
    measures = _get_profile_value(profile, "resource_efficiency_measures")
    score    = _text_score(measures)
    return leaf(
        criterion    = "resource_efficiency",
        label_fr     = "Efficacité des ressources",
        score        = score,
        weight       = 0.15,
        evidence     = {"resource_efficiency_measures": bool(measures)},
        justification = f"resource_efficiency_measures={'described' if measures else 'missing'} → score {score}",
    )


def _circular_economy(profile: Any) -> Dict[str, Any]:
    practices = _get_profile_value(profile, "circular_practices_described")
    score     = _text_score(practices)
    return leaf(
        criterion    = "circular_economy",
        label_fr     = "Pratiques d'économie circulaire",
        score        = score,
        weight       = 0.10,
        evidence     = {"circular_practices_described": bool(practices)},
        justification = f"circular_practices_described={'set' if practices else 'missing'} → score {score}",
    )


def _sdg_commitment(profile: Any) -> Dict[str, Any]:
    """
    SDG alignment + evidence. Evidence matters: claiming SDGs without
    concrete examples scores lower than aligning with measurable proof.
    """
    sdg_list = _get_profile_value(profile, "sdg_alignment")
    evidence  = _get_profile_value(profile, "sdg_evidence")
    has_sdg   = _is_truthy(sdg_list)   # non-empty list → True
    score: Optional[float]
    if has_sdg is None:
        score = None
    elif has_sdg is False:
        score = 0.0
    elif evidence:
        score = 10.0
    else:
        score = 6.0   # SDGs claimed but no concrete evidence
    return leaf(
        criterion    = "sdg_commitment",
        label_fr     = "Alignement avec les ODD (avec preuves)",
        score        = score,
        weight       = 0.15,
        evidence     = {
            "sdg_alignment": sdg_list,
            "sdg_evidence":  bool(evidence),
        },
        justification = f"sdg_alignment={'set' if has_sdg else 'empty'}, evidence={'set' if evidence else 'missing'} → score {score}",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _text_score(value: Any) -> Optional[float]:
    """None → missing (not asked); truthy string → described (10); falsy → not done (0)."""
    if value is None:
        return None
    return 10.0 if value else 0.0
