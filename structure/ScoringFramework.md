# Scoring Framework (Feature 2)

Current, code-verified notes.

Last verified: 2026-06-24

## Purpose

The scoring layer computes 5 health dimensions from profile + derived metrics.

Primary implementation:

- orchestrator: `diagnostic/scoring.py`
- metrics bundle: `diagnostic/metrics.py`
- engines: `scorers/market.py`, `commercial.py`, `innovation.py`, `scalability.py`, `green.py`
- shared scoring utilities: `scorers/scoring_utils.py`

## Scoring Contract

Each dimension returns:

- `score` (0-10 or `None`)
- `floor`
- `floor_met`
- `leaves` (criterion-level details)

Frontend payload additionally includes calculation transparency from `leadit_app/views.py`:

- `calc.weighted_sum`
- `calc.scored_weight`
- `calc.total_weight`
- `calc.weighted_score`
- `calc.floor_delta`

## None Handling and Rollup

Source of truth: `scorers/scoring_utils.py`.

- Missing leaves return `score=None`.
- `rollup()` computes weighted average over scored leaves only (renormalized).
- If all leaves are missing, composite score is `None`.

This is important: unanswered criteria are not auto-scored as 0 by engine logic.

## Floors (Current)

- Market floor: `5.0`
- Commercial floor: `4.0`
- Innovation floor: `4.0`
- Scalability floor: `4.0`
- Green floor: `4.0`

`floor_met` is a pass/fail flag; it does not mutate the raw composite score.

## Current Leaves by Dimension

### Market (`scorers/market.py`)

- gross_margin_viability (0.30)
- breakeven_reachability (0.25)
- opex_runway (0.20)
- credit_access (0.15)
- investment_gap_covered (0.10)

### Commercial (`scorers/commercial.py`)

- pricing_coherence (0.30)
- local_price_positioning (0.30)
- foreign_price_positioning (0.20)
- volume_vs_breakeven (0.15)

### Innovation (`scorers/innovation.py`)

- idea_novelty (0.35)
- market_research_depth (0.30)
- differentiation_strength (0.25)
- price_advantage_vs_foreign (0.10)

### Scalability (`scorers/scalability.py`)

- unit_economics_at_scale (0.30)
- volume_headroom (0.25)
- team_depth (0.25)
- fixed_cost_leverage (0.20)

### Green (`scorers/green.py`)

- impact_declared (0.60)
- sdg_commitment (0.40)

## Determinism

All numeric scoring is deterministic and code-based.
LLMs are not used to calculate scores.
