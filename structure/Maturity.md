# Maturity Engine (Feature 1)

Current, code-verified notes.

Last verified: 2026-06-24

## Purpose

The maturity engine classifies project stage from structured criteria. It is rule-based and deterministic.

Primary implementation:

- `diagnostic/services.py`
- `criteria/criteria_nested.py`
- `criteria/calculations.py`

## Stage Order

Source of truth: `criteria/criteria_nested.py`.

Current UI mapping uses:

- `IDEATION`
- `MARKET_VALIDATION`
- `STRUCTURATION`
- `FUNDRAISING`
- `LAUNCH_PLANNING`
- `GROWTH`

## Core Behavior

- Stage starts at `IDEATION`.
- For each next stage, criteria are evaluated.
- A stage is assigned only when all required criteria for that stage pass.
- Classification stops at the first stage with unmet or missing required criteria.

Outputs include:

- `assigned_stage`
- `stopped_at`
- detailed `evidence`
- `failed_criteria`
- `blockers` by domain + ranked domains
- confidence estimate (`compute_confidence`)
- perception gap (`detect_perception_gap`)

## Intake Relationship

LeadIt uses a conversational intake engine (`intake/engine.py`, `intake/consultant.py`) to populate profile fields used by diagnostic/scoring.

Important current behavior:

- Intake question generation is LLM-assisted.
- Language policy in intake supports French and Arabic and mirrors the founder language.
- Diagnostic calculation itself remains deterministic once fields are available.

## HTTP Wiring

- Classification + scoring are triggered in `POST /api/analysis/start/` (`leadit_app/views.py`).
- Follow-up analyst Q&A uses `POST /api/analysis/ask/`.

## What Is Deterministic vs LLM

Deterministic:

- stage classification
- blocker extraction/ranking
- confidence/perception gap formulas

LLM-driven:

- interview phrasing and question text
- analyst presentation text
