"""
calculations.py

Diagnostic-layer utilities for LeadIt.

Contains:
- Shared profile-reading helpers used by services.py and scorer modules
- compute_validation_strength  — demand-evidence signal for the classifier
- detect_structural_coherence  — dossier-coherence flags (legal form vs. associés)
- get_maturity_criteria_results — flat criterion signals for the diagnostic engine

Everything else (unit economics, financing, projections, anomaly detection,
derive_all_metrics) lives in scorers/ and diagnostic/metrics.py.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Dict, List, Mapping, Optional


# ---------------------------------------------------------------------
# Shared profile-reading helpers
# (imported by services.py and all scorers/)
# ---------------------------------------------------------------------

def _get_profile_value(profile: Any, key: str, default: Any = None) -> Any:
    """Read a value from a dict, Django model field, or JSONField named metadata."""
    if isinstance(profile, Mapping):
        if key in profile and profile[key] is not None:
            return profile[key]
        return (profile.get("metadata") or {}).get(key, default)

    if hasattr(profile, key):
        value = getattr(profile, key)
        if value is not None:
            return value

    return (getattr(profile, "metadata", {}) or {}).get(key, default)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
        return out if isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: Optional[float], minimum: float, maximum: float) -> Optional[float]:
    if value is None:
        return None
    return max(minimum, min(maximum, value))


def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return numerator / denominator
    except ZeroDivisionError:
        return None


def _round_or_none(value: Optional[float], ndigits: int = 4) -> Optional[float]:
    if value is None:
        return None
    return round(value, ndigits)


def _is_truthy(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return bool(value)


def _normalize_pct(value: Optional[float]) -> Optional[float]:
    """Accept either 0.62 or 62 and return the 0–1 form."""
    if value is None:
        return None
    return value / 100.0 if value > 1 else value


# ---------------------------------------------------------------------
# Validation / demand evidence  (used by the classifier)
# ---------------------------------------------------------------------

def compute_validation_strength(profile: Any) -> Dict[str, Any]:
    """
    Combine validation evidence into a normalized signal.

    Inputs: customer_interview_count, pilot_users, pre_orders,
            has_validated_problem, validation_type

    Output: { score_0_100, score_0_1, components, label }
    """
    interviews       = _to_int(_get_profile_value(profile, "customer_interview_count"))
    pilots           = _to_int(_get_profile_value(profile, "pilot_users"))
    preorders        = _to_int(_get_profile_value(profile, "pre_orders"))
    validated        = _is_truthy(_get_profile_value(profile, "has_validated_problem"))
    validation_types = _get_profile_value(profile, "validation_type", []) or []

    score          = 0.0
    evidence_weight = 0.0

    if interviews is not None:
        evidence_weight += 1
        if   interviews == 0:           score += 0
        elif interviews <= 4:           score += 20
        elif interviews <= 9:           score += 40
        elif interviews <= 19:          score += 65
        else:                           score += 80

    if pilots is not None:
        evidence_weight += 1
        if   pilots == 0:               score += 0
        elif pilots <= 2:               score += 20
        elif pilots <= 5:               score += 45
        else:                           score += 60

    if preorders is not None:
        evidence_weight += 1
        if   preorders == 0:            score += 0
        elif preorders <= 2:            score += 20
        elif preorders <= 5:            score += 45
        else:                           score += 60

    if validated is True:
        score += 15;  evidence_weight += 0.5
    elif validated is False:
        evidence_weight += 0.5

    if validation_types:
        evidence_weight += 0.5
        score += min(len(validation_types) * 5, 15)

    components = {
        "customer_interview_count": interviews,
        "pilot_users":              pilots,
        "pre_orders":               preorders,
        "has_validated_problem":    validated,
        "validation_type":          validation_types,
    }

    if evidence_weight == 0:
        return {"score_0_100": None, "score_0_1": None, "components": components, "label": None}

    normalized   = _clamp(score / (evidence_weight * 80.0), 0.0, 1.0)
    score_0_100  = int(round((normalized or 0) * 100))
    label        = "low" if score_0_100 < 35 else "medium" if score_0_100 < 70 else "high"

    return {"score_0_100": score_0_100, "score_0_1": normalized, "components": components, "label": label}


# ---------------------------------------------------------------------
# Structural coherence  (dossier flags, NOT scoring anomalies)
# ---------------------------------------------------------------------

def detect_structural_coherence(profile: Any) -> List[Dict[str, Any]]:
    """
    Flag internally inconsistent legal structure data.
    These are dossier-coherence flags — the scoring engine must not duplicate them.
    """
    flags           = []
    legal_form_type = _get_profile_value(profile, "legal_form_type")
    associes        = _get_profile_value(profile, "associes") or []
    if not isinstance(associes, list):
        associes = []
    count = len(associes)

    if legal_form_type == "SARL" and 0 < count < 2:
        flags.append({"type": "sarl_insufficient_associes", "severity": "dossier_coherence",
                      "message": f"Une SARL requiert au moins 2 associés — {count} déclaré(s)."})

    if legal_form_type == "SUARL" and count > 0 and count != 1:
        flags.append({"type": "suarl_wrong_associes_count", "severity": "dossier_coherence",
                      "message": f"Une SUARL requiert exactement 1 associé — {count} déclaré(s)."})

    return flags


# ---------------------------------------------------------------------
# Maturity criteria signals  (consumed by the diagnostic engine)
# ---------------------------------------------------------------------

def get_maturity_criteria_results(profile: Any) -> Dict[str, Any]:
    """
    Return flat criterion signals needed by the diagnostic engine.
    Does not classify the project — only prepares the evidence map.
    """
    validation       = compute_validation_strength(profile)
    legal_form_status = _get_profile_value(profile, "legal_form_status")
    if legal_form_status is not None:
        legal_form_status = str(legal_form_status).lower()

    return {
        "has_validated_problem": (
            True  if validation.get("score_0_100") is not None and validation["score_0_100"] >= 35
            else False if validation.get("score_0_100") is not None
            else None
        ),
        "target_customer_defined":      _is_truthy(_get_profile_value(profile, "target_customer_defined")),
        "geographic_scope":             _get_profile_value(profile, "geographic_scope"),
        "idea_is_new":                  _is_truthy(_get_profile_value(profile, "idea_is_new")),
        "foreign_model_studied":        _is_truthy(_get_profile_value(profile, "foreign_model_studied")),
        "differentiation_claimed":      _is_truthy(_get_profile_value(profile, "differentiation_claimed")),
        "founder_has_required_skills":  _is_truthy(_get_profile_value(profile, "founder_has_required_skills")),
        "founder_has_prior_experience": _is_truthy(_get_profile_value(profile, "founder_has_prior_experience")),
        "team_core_complete":           _is_truthy(_get_profile_value(profile, "team_core_complete")),
        "business_model_documented":    _is_truthy(_get_profile_value(profile, "business_model_documented")),
        "legal_form_status":            legal_form_status,
        "rne_registered":               _is_truthy(_get_profile_value(profile, "rne_registered")),
        "has_paying_customers":         _is_truthy(_get_profile_value(profile, "has_paying_customers")),
        "financial_docs_exist":         _is_truthy(_get_profile_value(profile, "financial_docs_exist")),
        "funding_secured":              _is_truthy(_get_profile_value(profile, "funding_secured")),
        "self_financing_confirmed":     _is_truthy(_get_profile_value(profile, "self_financing_confirmed")),
        "distribution_channel_tested":  _is_truthy(_get_profile_value(profile, "distribution_channel_tested")),
        "revenue_recurring_months":     _get_profile_value(profile, "revenue_recurring_months"),
        "client_base_beyond_pilot":     _is_truthy(_get_profile_value(profile, "client_base_beyond_pilot")),
        "validation_strength_score_0_100": validation.get("score_0_100"),
        "validation_strength_label":       validation.get("label"),
    }
