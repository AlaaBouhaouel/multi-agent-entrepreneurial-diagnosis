"""
roadmap/kb/schema.py

Knowledge-base schema helpers for Feature 3.

The KB is a flat JSON list of resource entries (support programs, financing,
incubators, …). Each entry is authored with these fields:

    resource_id, name, provider, category, description, source_url,
    stage_tags, blocker_domains, eligibility, benefits, trust_level, status

This module is the single bridge between the diagnostic stage vocabulary and the
KB stage-tag vocabulary, and it prepares each entry for retrieval by computing
the `text_blob` the embedder indexes (KBRetriever.index reads entry["text_blob"]).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


# ─────────────────────────────────────────────────────────────────────────────
# Stage vocabulary bridge
# The diagnostic engine emits UPPER_SNAKE stage names (criteria STAGE_ORDER);
# the KB tags stages with lowercase short tags. This map is the only place the
# two vocabularies meet.
# ─────────────────────────────────────────────────────────────────────────────

STAGE_NAME_TO_TAG: Dict[str, str] = {
    "IDEATION":          "ideation",
    "MARKET_VALIDATION": "validation",
    "STRUCTURATION":     "structuration",
    "FUNDRAISING":       "fundraising",
    "LAUNCH_PLANNING":   "launch_planning",
    "GROWTH":            "growth",
}


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_entry(entry: Dict[str, Any]) -> List[str]:
    """
    Return a list of human-readable problems with a KB entry (empty = clean).
    Used by the test harness to report KB quality without failing the pipeline.
    """
    problems: List[str] = []
    if not entry.get("resource_id"):
        problems.append("missing resource_id")
    if not entry.get("name"):
        problems.append("missing name")
    if not entry.get("source_url"):
        problems.append("missing source_url")
    if not entry.get("stage_tags"):
        problems.append("no stage_tags")
    if not entry.get("blocker_domains"):
        problems.append("no blocker_domains")
    return problems


# ─────────────────────────────────────────────────────────────────────────────
# Text blob (what the embedder indexes)
# ─────────────────────────────────────────────────────────────────────────────

def _build_text_blob(entry: Dict[str, Any]) -> str:
    """
    Concatenate the semantically meaningful fields into one FR string. The
    retriever embeds this blob; describing the resource's purpose, benefits and
    eligibility is what lets a weakness-query match the right resource.
    """
    parts: List[str] = []
    for key in ("name", "category", "provider", "description", "benefits", "eligibility"):
        val = entry.get(key)
        if val:
            parts.append(str(val))
    domains = entry.get("blocker_domains") or []
    if domains:
        parts.append("domaines : " + ", ".join(str(d) for d in domains))
    return ". ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Loader
# ─────────────────────────────────────────────────────────────────────────────

def load_kb(path: str) -> List[Dict[str, Any]]:
    """
    Load the KB JSON list and prepare each entry for retrieval.

    - Reads UTF-8.
    - Skips entries with no resource_id (they cannot be referenced or traced).
    - Adds a computed `text_blob` to every entry (the field KBRetriever.index
      embeds). Existing `text_blob` values, if any, are preserved.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if not isinstance(raw, list):
        raise ValueError(f"KB at {path} must be a JSON list of entries, got {type(raw).__name__}")

    entries: List[Dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("resource_id"):
            continue  # unreferenceable — never surface it
        if not entry.get("text_blob"):
            entry["text_blob"] = _build_text_blob(entry)
        entries.append(entry)

    return entries
