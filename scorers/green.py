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
        weight       = 0.60,
        evidence     = {
            "environmental_impact_type":        impact_type,
            "environmental_impact_description": bool(description),
        },
        justification = f"impact_type={impact_type}, description={'set' if description else 'missing'} → score {score}",
    )


def _sdg_commitment(profile: Any) -> Dict[str, Any]:
    """SDG alignment: a non-empty list of aligned SDGs signals a sustainability commitment."""
    sdg_list = _get_profile_value(profile, "sdg_alignment")
    has_sdg   = _is_truthy(sdg_list)   # non-empty list → True
    score: Optional[float]
    if has_sdg is None:
        score = None
    elif has_sdg is False:
        score = 0.0
    else:
        score = 10.0
    return leaf(
        criterion    = "sdg_commitment",
        label_fr     = "Alignement avec les ODD",
        score        = score,
        weight       = 0.40,
        evidence     = {"sdg_alignment": sdg_list},
        justification = f"sdg_alignment={'set' if has_sdg else 'empty'} → score {score}",
    )
