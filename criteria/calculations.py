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

