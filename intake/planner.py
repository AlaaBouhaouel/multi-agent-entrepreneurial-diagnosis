"""
intake/planner.py

Decides which field to ask about next, given the current intake state.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .field_metadata import DERIVED_FIELDS, FIELD_META

PENDING = "pending"
ANSWERED = "answered"
EXPLICITLY_UNKNOWN = "explicitly_unknown"
SKIPPED = "skipped"


def _check_condition(cond: Optional[Dict[str, Any]], profile: Dict[str, Any]) -> bool:
    if cond is None:
        return True
    field_val = profile.get(cond["field"])
    op = cond["op"]
    if op == "eq":
        return field_val == cond["value"]
    if op == "ne":
        # If the parent field is still unanswered (None), treat as not met —
        # ask the parent first, then come back to the dependent field.
        return field_val is not None and field_val != cond["value"]
    if op == "in":
        return field_val in cond["value"]
    if op == "not_none":
        return field_val is not None
    if op == "is_none":
        return field_val is None
    return False


def is_eligible(field: str, meta: Dict[str, Any], profile: Dict[str, Any], estimated_stage: int) -> bool:
    """True if the field should be considered for the next question."""
    if field in DERIVED_FIELDS:
        return False
    # Look one stage ahead so we warm up questions the user is about to need.
    if meta["stage_min"] > estimated_stage + 1:
        return False
    return _check_condition(meta.get("depends_on"), profile)


def pick_next_field(
    field_states: Dict[str, str],
    profile: Dict[str, Any],
    estimated_stage: int,
) -> Optional[str]:
    """
    Returns the field name to ask about next, or None when all eligible
    fields are answered or explicitly unknown.

    Ordering: priority ASC, then stage_min ASC (earlier stage first within
    the same priority band).
    """
    candidates = []
    for field, meta in FIELD_META.items():
        if field_states.get(field, PENDING) != PENDING:
            continue
        if not is_eligible(field, meta, profile, estimated_stage):
            continue
        candidates.append((meta["priority"], meta["stage_min"], field))

    if not candidates:
        return None

    candidates.sort()
    return candidates[0][2]


def completion_stats(
    field_states: Dict[str, str],
    profile: Dict[str, Any],
    estimated_stage: int,
) -> Dict[str, int]:
    """Counts eligible fields by state. Used for progress reporting."""
    counts: Dict[str, int] = {PENDING: 0, ANSWERED: 0, EXPLICITLY_UNKNOWN: 0, SKIPPED: 0}
    for field, meta in FIELD_META.items():
        if field in DERIVED_FIELDS:
            continue
        state = field_states.get(field, PENDING)
        if not is_eligible(field, meta, profile, estimated_stage):
            counts[SKIPPED] += 1
        else:
            counts[state] = counts.get(state, 0) + 1
    return counts


def is_complete(
    field_states: Dict[str, str],
    profile: Dict[str, Any],
    estimated_stage: int,
) -> bool:
    """True when no eligible field is still pending."""
    return completion_stats(field_states, profile, estimated_stage)[PENDING] == 0
