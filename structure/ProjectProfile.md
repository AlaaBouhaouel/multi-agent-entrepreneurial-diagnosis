# Project Profile & System Pipeline

> LeadIt — Shared Data Layer & Full Pipeline Specification
> Ref: AINS Hackathon 2026, Sections 2.2–2.5

## Purpose

The shared project profile is the integration backbone of LeadIt. It is the single structured object that every engine reads from and writes to. This is the mechanism that makes the three mandatory features (Diagnostic, Scoring, Roadmap) genuinely interact through a shared project profile — not merely coexist as independent panels (brief §2.2).

The profile persists in PostgreSQL across sessions to support contextual project memory (brief §2.3.3) and the Mon Parcours tracking view (brief §2.5.3).

**Canonical field registry:** `projects/schemas.py` — `ProjectProfileData` (Pydantic model). Every field the system reads must be declared there. This document describes intent, pipeline mechanics, and write rules. Field definitions live in the code.

---

## Write Rules — Append-Only, Attributed

**No engine may overwrite existing data.** Every write is an append to `ProfileLog` that includes:

1. **`author`** — the engine key from the `ENGINES` choices list (e.g. `"diagnostic"`, `"market"`, `"roadmap"`)
2. **`output_type`** — labels what the metadata contains (e.g. `"diagnosis_result"`, `"score.market"`, `"intake_extract"`)
3. **`timestamp`** — set automatically by `auto_now_add=True`
4. **`metadata`** — the full engine output as a single atomic dict

One `ProfileLog` row per engine run. The entire output for that run lives in `metadata` — never split across multiple rows. This prevents reading a mix of fields from different runs.

### Why append-only

- **Explainability** (brief §1.3.4): any output traces to the exact engine and moment that produced it
- **Score evolution** (brief §2.4.3): Mon Parcours shows how scores changed over time by reading the full log chronologically
- **Debugging**: conflicting engine outputs show what each saw and when
- **Cross-module safety**: no engine can accidentally overwrite another engine's output

### Write format

```json
{
  "author": "diagnostic",
  "output_type": "diagnosis_result",
  "metadata": {
    "assigned_stage": "STRUCTURATION",
    "assigned_stage_index": 3,
    "perception_gap": 1,
    "gap_direction": "overestimate",
    "blockers": [ "..." ],
    "confidence": { "level": "medium", "score": 0.75 }
  }
}
```

### Reading convention

- **Latest diagnosed stage:** `ProfileLog.objects.filter(project=p, author="diagnostic").order_by("-timestamp").first()`
- **Score history:** `ProfileLog.objects.filter(project=p, author__in=["market","commercial","innovation","scaling","green"]).order_by("timestamp")`
- **Full audit log:** `profile.logs.all()` (ordered newest-first by default)

Historical entries are never used for current computation — only the latest entry per `output_type` drives the current result.

---

## Full System Pipeline

```
┌─────────────────────┐
│    ADAPTIVE INTAKE   │ ← LLM preprocesses raw answers into structured fields
└──────────┬──────────┘
           ↓ fills metadata (validated via ProjectProfileData)
┌─────────────────────┐
│   SHARED PROJECT     │ ← PostgreSQL: ProjectProfile + ProfileLog (append-only)
│      PROFILE         │
└──────────┬──────────┘
           ↓ read by
┌─────────────────────┐
│  DIAGNOSTIC ENGINE   │ ← Rule-based: criteria_nested.py → stage + gap + blockers
└──────────┬──────────┘
           ↓ diagnosed_stage read by
┌───┬───┬───┬───┬─────┐
│ M │ C │ I │ S │  G  │ ← 5 scoring engines (parallel, rule-based + LLM for justification)
└───┴───┴───┴─┬─┴─────┘
              ↓ all feed into
┌─────────────────────┐
│    GAP ANALYZER      │ ← Pure logic: merges diagnostic blockers + low scores → ranked gaps
└──────────┬──────────┘
           ↓ feeds into
┌──────────┴──────────┐
│   ROADMAP ENGINE     │◄── TUNISIAN KB (Qdrant, 30+ real resources)
│                      │    Structured filtering + semantic retrieval
└──────────┬──────────┘
           ↓ all outputs displayed by
┌─────────────────────┐
│  EXPLAINABLE REPORT  │ ← Next.js dashboard: stage, radar chart, gaps, roadmap, Mon Parcours
└──────────┬──────────┘
           ↓ grounds
┌─────────────────────┐
│  GROUNDED ASSISTANT  │ ← Thin LLM layer; reads report + KB only; not the core product
└─────────────────────┘
```

### What each engine reads and writes

| Engine | Reads | Writes (`output_type`) |
|---|---|---|
| Adaptive Intake | Entrepreneur's raw answers | `"intake_extract"` |
| Diagnostic Engine | Profile metadata + `self_assessed_stage` | `"diagnosis_result"` |
| 5 Scoring Engines | Profile metadata + latest `"diagnosis_result"` | `"score.market"` / `"score.commercial"` / `"score.innovation"` / `"score.scaling"` / `"score.green"` |
| Gap Analyzer | Latest diagnostic + 5 scoring logs | `"gap_analysis"` |
| Roadmap Engine | Gap analysis + profile context + KB | `"roadmap_result"` |
| Explainable Report | All latest log entries (read-only) | Nothing |
| Grounded Assistant | Report snapshot + matched KB (read-only) | Nothing |

---

## Profile Schema

The `ProjectProfile` Django model stores:

| Column | Type | Notes |
|---|---|---|
| `id` | AutoField | Primary key |
| `project_name` | CharField(255) | |
| `sector` | CharField(120), nullable | |
| `lang_preference` | CharField, choices: `fr` / `ar` | |
| `self_assessed_stage` | PositiveSmallIntegerField, nullable | Integer 1–6; intake converts stage name before writing |
| `metadata` | JSONField | Validated against `ProjectProfileData` at write time |
| `created_at` | DateTimeField, auto | |
| `updated_at` | DateTimeField, auto | |

**There is no `current_stage` column.** Latest diagnosed stage is read from the most recent `ProfileLog` entry with `author="diagnostic"`. This keeps the model truly append-only.

All profile content fields live in `metadata`. The `ProjectProfileData` Pydantic model (`projects/schemas.py`) is the authoritative field list. What follows is a section-by-section description of purpose and usage for each group of fields.

---

### Self-Assessment
*Written by: Intake. Never used for classification or scoring — only for perception-gap detection.*

| Field | Purpose |
|---|---|
| `self_assessed_stage` | Integer 1–6. The stage the entrepreneur believes they are at. |
| `self_assessed_readiness` | Free text: what the entrepreneur thinks they need next. |
| `self_assessed_strengths` | Cross-referenced with scoring anomaly detection. |
| `self_assessed_weaknesses` | Cross-referenced with scoring anomaly detection. |

**Stage integer mapping** — defined in `criteria/criteria_nested.py` as `STAGE_TO_INT`:

| Integer | Stage name | French label |
|---|---|---|
| 1 | IDEATION | Idéation |
| 2 | MARKET_VALIDATION | Validation marché |
| 3 | STRUCTURATION | Structuration |
| 4 | FUNDRAISING | Fundraising |
| 5 | LAUNCH_PLANNING | Lancement |
| 6 | GROWTH | Croissance |

Intake must call `stage_name_to_int()` before writing. All downstream gap calculations use integers only.

---

### Founder & Team
*Written by: Intake.*

| Field | Used by |
|---|---|
| `gerant` | Scoring — Commercial (`management_identified` criterion) |
| `founder_count` | Scoring context |
| `founder_has_prior_experience` | **Classifier** — Stage 2 (`founder_readiness`) |
| `founder_has_required_skills` | **Classifier** — Stage 2/3 (`domain_competence`, `team_core_sufficient`) |
| `associes` | Scoring — Scalability (`team_depth` criterion) |
| `team_size` | Scoring — Scalability context |
| `team_core_complete` | **Classifier** — Stage 2/3 + Scoring (Scalability) |
| `team_roles` | Scoring context |
| `prior_accompaniment` | Roadmap (avoid re-recommending completed programs) |

---

### Legal & Administrative
*Written by: Intake.*

| Field | Used by |
|---|---|
| `legal_form_status` | **Classifier** — Stage 3 (`in_progress` or `registered`) + Stage 4 (`registered` only) |
| `legal_form_type` | Roadmap context (SARL, SUARL, SA, etc.) |
| `registration_date` | Scoring context |
| `rne_registered` | **Classifier** — Stage 4 (`legal_constitution`) + Roadmap eligibility |
| `startup_label` | Roadmap (Startup Act programme eligibility) |

---

### Market & Validation
*Written by: Intake.*

| Field | Used by |
|---|---|
| `target_customer_defined` | **Classifier** — Stage 2 (`market_knowledge`) |
| `geographic_scope` | **Classifier** — Stage 2 + Scoring (Market, Scalability) |
| `has_validated_problem` | Summary flag set by intake; Scoring (Market) |
| `validation_type` | Scoring (Market — evidence quality); **Classifier** — Stage 2 (contains `"survey"`) |
| `customer_interview_count` | **Classifier** — Stage 2 (min 1) + Scoring (Market) |
| `pilot_users` | **Classifier** — Stage 2 (min 1) + Scoring (Market) |
| `pre_orders` | **Classifier** — Stage 2 (min 1) + Scoring (Market) |
| `target_market_size` | Scoring (Market — addressable size) |
| `competitor_count` | Scoring (Market, Innovation) |
| `differentiation_claimed` | **Classifier** — Stage 2 + Scoring (Market, Innovation) |
| `differentiation_description` | Scoring (Innovation — LLM rubric) |
| `local_competitors` | Scoring (Innovation — local novelty) |

---

### Innovation
*Written by: Intake.*

| Field | Used by |
|---|---|
| `idea_is_new` | **Classifier** — Stage 2 (`market_context_assessed`, `any` rule) + Scoring (Innovation) |
| `foreign_model_studied` | **Classifier** — Stage 2 (`market_context_assessed`, `any` rule) + Scoring (Innovation) |
| `business_model_documented` | **Classifier** — Stage 3 (`organisation`) |

---

### Product & Offer
*Written by: Intake.*

| Field | Used by |
|---|---|
| `product_stage` | Scoring (Commercial — product readiness): `concept \| prototype \| mvp \| production` |
| `demo_available` | Scoring (Commercial) |
| `value_proposition_text` | Scoring (Commercial — LLM rubric) |
| `value_prop_clarity_rating` | Scoring (Commercial); integer 1–5, set by intake LLM rubric |
| `pricing_model` | Scoring (Commercial) |
| `pricing_tested` | Scoring (Commercial, Market) |
| `pricing_documented` | Scoring (Commercial) |

---

### Financial Inputs
*Written by: Intake. Raw numerical inputs used by `scorers/economics.py`, `scorers/projections.py`, and `scorers/financing.py` to compute derived metrics. Engines never score raw text.*

| Field | Unit | Notes |
|---|---|---|
| `selling_price` | TND | Price per unit sold |
| `unit_cost` | TND | Direct production cost per unit |
| `expected_monthly_units` | units | Projected monthly sales volume |
| `monthly_revenue` | TND | Current monthly revenue |
| `personnel_monthly_cost` | TND | Total monthly payroll |
| `rent_monthly` | TND | Monthly rent |
| `other_fixed_costs_monthly` | TND | Other fixed overhead |
| `fixed_costs_monthly` | TND | Direct total fixed cost (alternative to the three above) |
| `initial_investment` | TND | Total capex at launch |
| `equipment_investment` | TND | Equipment portion of capex |
| `equipment_lifespan_years` | years | For depreciation calculation |
| `ca_growth_rate` | 0.0–1.0 | Monthly revenue growth rate |
| `cogs_percentage` | 0.0–1.0 | COGS as fraction of revenue (alternative to `unit_cost`) |
| `tfse_percentage` | 0.0–1.0 | Social charges rate — Tunisia-specific |
| `tax_rate` | 0.0–1.0 | Corporate tax rate |
| `market_price_local` | TND | Local competitor benchmark price |
| `market_price_foreign` | TND | Foreign equivalent benchmark price |

Computed metrics derived from these inputs (produced once per pipeline run by `diagnostic/metrics.py` and passed to all scorers as a shared bundle — never recomputed per scorer):

`gross_margin_ratio`, `breakeven_months`, `breakeven_units`, `monthly_profit`, `monthly_fixed_costs`, `van_5_years`, `repayment_capacity_ratio`, `credit_eligibility_path`, `opex_months_covered`, `credit_gap_exists`, `planned_credit_covers_gap`

---

### Financial State
*Written by: Intake.*

| Field | Used by |
|---|---|
| `has_paying_customers` | **Classifier** — Stage 4 + Scoring (Market) |
| `revenue_model_type` | Scoring (Market) |
| `revenue_recurring_months` | **Classifier** — Stage 6 (min 3 months) |
| `financial_docs_exist` | **Classifier** — Stage 4 |
| `funding_secured` | **Classifier** — Stage 5 (`funding_ready`, `any` with `self_financing_confirmed`) |
| `funding_amount` | Roadmap context (TND) |
| `funding_source` | Roadmap context |
| `self_financing_confirmed` | **Classifier** — Stage 5 (`funding_ready`, `any` with `funding_secured`) |
| `cost_structure_type` | Scoring (Scalability): `fixed_heavy \| variable_heavy \| mixed` |
| `marginal_cost_estimate` | Scoring (Scalability) |

---

### Credit & Financing
*Written by: Intake. Used by `scorers/financing.py` to determine credit eligibility path and repayment capacity.*

| Field | Notes |
|---|---|
| `needs_credit` | Gate: if `False`, credit sub-criteria scored differently |
| `credit_amount_needed` | TND |
| `credit_duration_years` | Loan term |
| `has_guarantee` | Affects credit eligibility path (commercial bank vs BTS/FONAPRA) |
| `has_premises` | Affects credit eligibility |
| `apport_personnel` | Personal equity contribution (TND) |
| `opex_months_covered` | Months of operating costs covered |
| `has_opex_financing` | Explicit opex financing flag |
| `annual_cash_flow` | TND — for repayment capacity calculation |
| `annual_debt_service` | TND — existing annual debt payments |
| `existing_credit_monthly_payment` | TND — existing monthly obligations |
| `credit_eligibility_blockers` | e.g. `["fichage_bct"]` — blocks commercial bank path |

---

### Distribution & Operations
*Written by: Intake.*

| Field | Used by |
|---|---|
| `distribution_channel_tested` | **Classifier** — Stage 5 |
| `distribution_channels` | Scoring context |
| `delivery_model` | Scoring (Scalability — replicability) |
| `manual_dependency_level` | Scoring (Scalability): `low \| medium \| high` |
| `automation_level` | Scoring (Scalability, Innovation): `none \| partial \| high` |
| `standardised_process` | Scoring (Scalability) |
| `client_base_beyond_pilot` | **Classifier** — Stage 6 |

---

### Technology
*Written by: Intake.*

| Field | Used by |
|---|---|
| `tech_stack_described` | Scoring (Innovation) |
| `tech_is_core_to_offer` | Scoring (Innovation) |
| `ip_protected` | Scoring (Innovation — barrier to entry) |
| `proprietary_data` | Scoring (Innovation — barrier to entry) |
| `network_effects` | Scoring (Innovation, Scalability) |

---

### Sustainability & Green
*Written by: Intake.*

`environmental_impact_type` accepted values: `économie_énergie` | `réduction_déchets` | `eau` | `biodiversité` | `aucun`

| Field | Used by |
|---|---|
| `environmental_impact_type` | Scoring (Green — `impact_declared`) |
| `environmental_impact_description` | Scoring (Green — boosts `impact_declared` score when present) |
| `carbon_reduction_claimed` | Scoring (Green) |
| `waste_reduction_measures` | Scoring (Green — `waste_reduction`); string description |
| `energy_reduction_measures` | Scoring (Green) |
| `water_reduction_measures` | Scoring (Green) |
| `resource_efficiency_measures` | Scoring (Green — LLM rubric) |
| `circular_practices_described` | Scoring (Green — `circular_economy`); **string description, not boolean** |
| `sdg_alignment` | Scoring (Green — `sdg_commitment`); list of SDG numbers as strings: `["7", "12"]` |
| `sdg_evidence` | Scoring (Green — boosts `sdg_commitment` score when present) |

---

### Scalability
*Written by: Intake.*

| Field | Used by |
|---|---|
| `replicability_evidence` | Scoring (Scalability) |
| `multi_segment_potential` | Scoring (Scalability — addressable reach) |
| `language_adaptability` | Scoring (Scalability — addressable reach) |
| `team_size_vs_customers` | Scoring (Scalability — manual dependency) |

---

## Engine Output Storage

All engine outputs follow the same append-only format in `ProfileLog`:

| Engine | `author` | `output_type` | Key metadata fields |
|---|---|---|---|
| Intake preprocessor | `"intake"` | `"intake_extract"` | `raw_input`, `extracted_fields` |
| Diagnostic | `"diagnostic"` | `"diagnosis_result"` | `assigned_stage`, `assigned_stage_index`, `perception_gap`, `gap_direction`, `blockers`, `confidence`, `evidence` |
| Market scoring | `"market"` | `"score.market"` | `score`, `floor`, `floor_met`, `leaves`, `anomalies` |
| Commercial scoring | `"commercial"` | `"score.commercial"` | same structure |
| Innovation scoring | `"innovation"` | `"score.innovation"` | same structure |
| Scalability scoring | `"scaling"` | `"score.scaling"` | same structure |
| Green scoring | `"green"` | `"score.green"` | same structure |
| Gap Analyzer | `"unifier"` | `"gap_analysis"` | `gaps_ranked`, `domain_summary`, `perception_gap_enriched`, `missing_data_fields` |
| Roadmap | `"roadmap"` | `"roadmap_result"` | `roadmap` (3 horizons), `matched_resources`, `unmatched_gaps` |

### Diagnostic output example

```json
{
  "assigned_stage":       "STRUCTURATION",
  "assigned_stage_index": 3,
  "stopped_at":           "FUNDRAISING",
  "perception_gap":       1,
  "gap_direction":        "overestimate",
  "perception_gap_criteria": [
    {"criterion": "has_paying_customers", "stage": "FUNDRAISING", "value": false, "domain": "financier"}
  ],
  "evidence":    { "MARKET_VALIDATION": [...], "STRUCTURATION": [...], "FUNDRAISING": [...] },
  "blockers":    { "by_domain": {...}, "ranked_domains": ["financier"], "total": 2 },
  "confidence":  { "level": "medium", "score": 0.75, "none_count": 1, "total_evaluated": 4 },
  "diagnosed_at": "2026-06-21T14:32:07Z"
}
```

### Intake extract example

```json
{
  "raw_input": "on a fait un petit test avec 3 clients à Sousse qui ont payé",
  "extracted_fields": {
    "has_paying_customers": true,
    "customer_interview_count": 3,
    "geographic_scope": "local",
    "distribution_channel_tested": true
  }
}
```

---

## Perception-Reality Gap

Computed by the diagnostic engine; written into the `"diagnosis_result"` log entry.

| Field | Type | Notes |
|---|---|---|
| `perception_gap` | int (signed) | `self_assessed_stage − assigned_stage_index`. Positive = overestimate, negative = underestimate |
| `gap_direction` | str | `"overestimate"` / `"underestimate"` / `"aligned"` |
| `perception_gap_criteria` | list | Criteria whose failure caused the divergence, with stage and domain tags |

Both stages are always integers. `self_assessed_stage` is converted to integer at intake via `stage_name_to_int()`. The diagnostic engine produces `assigned_stage_index` (1-based) from `get_stage_index()` (0-based) + 1.

---

## Mon Parcours — Persistent Tracking

Brief §2.5.3: reads the full `ProfileLog` chronologically and presents:

- **Stage progression** — all `"diagnosis_result"` entries ordered by timestamp
- **Score evolution** — all `"score.*"` entries per dimension over time
- **Blockers resolved** — which gap criteria changed from `False`/`None` to `True` across runs
- **Roadmap history** — all `"roadmap_result"` entries
- **Missing data resolved** — which `None` fields were filled between sessions

Each entry is a complete snapshot from a single engine run. No partial state is ever stored.

---

## Adaptive Intake — Branching Logic

The intake does not ask every field (brief §2.3.2). Branching logic determines which fields to probe:

| If the entrepreneur says... | Then probe... |
|---|---|
| `sector = agri-food` | Certifications, supply chain, seasonality |
| `self_assessed_stage >= 4` | `has_paying_customers`, `financial_docs_exist`, `revenue_recurring_months` |
| `legal_form_status = registered` | `registration_date`, `rne_registered`, `startup_label` |
| `environmental_impact_type != aucun` | `sdg_alignment`, `resource_efficiency_measures`, `circular_practices_described` |
| `has_paying_customers = true` | `monthly_revenue`, `revenue_recurring_months`, `revenue_model_type` |
| `needs_credit = true` | `credit_amount_needed`, `credit_duration_years`, `has_guarantee`, `apport_personnel` |

Uncollected fields remain `None`. The `None` return type in `criteria_nested.py` and weight redistribution in `scorers/scoring_utils.py` handle missing data — uncertainty is surfaced, not hidden.

**Stage name conversion:** before writing `self_assessed_stage`, intake calls `stage_name_to_int(stage_str)` from `criteria/criteria_nested.py`. The integer is stored in both `ProjectProfile.self_assessed_stage` (model column) and `ProjectProfile.metadata["self_assessed_stage"]`.

---

## Privacy & Anonymisation

Brief §1.5:

- `founder_name` (if collected) never exposed in third-party outputs. Outputs reference `project_id` or `project_name` only.
- Financial fields (`monthly_revenue`, `funding_amount`, `selling_price`) used for scoring computation; maskable in dashboard views.
- Profile is scoped to the authenticated user. Support officers see diagnostic and scoring outputs only with explicit consent.

---

## Versioning & Schema Evolution

The profile is append-only by design:

1. **Add a field** → add it to `ProjectProfileData` in `projects/schemas.py`. New fields default to `None`. No existing profile breaks. No Django migration needed.
2. **Remove a field** → remove from `ProjectProfileData`. Old `ProfileLog` entries retain the data. Add `extra="ignore"` temporarily if needed during transition.
3. **Rename a field** → add the new name, keep old with `None` default + deprecation comment, remove after all profiles migrated.
4. **Rollback** → previous `"diagnosis_result"` entries are preserved in the log. Mon Parcours reads all of them.

Schema evolution = one Python file change (`projects/schemas.py`). No Django migration needed for content fields.

---

## Non-Functional Requirements (brief §1.5)

### Responsiveness
Five scoring engines run in parallel in `score_project()` (`diagnostic/scoring.py`), each receiving the same pre-computed metrics bundle from `derive_all_metrics()`. Diagnostic and gap analyzer are pure Python logic. KB retrieval is the bottleneck — bounded by top-K over Qdrant.

### Reliability
`ProjectProfileData` with `extra="forbid"` catches unknown field names at write time. The `None` return in `criteria_nested.py` and `rollup()` in `scorers/scoring_utils.py` handle missing fields without crashing.

### Scalability mindset
- PostgreSQL handles concurrent users and growing ProfileLog tables
- Qdrant handles growing KB corpus without rebuild
- Each scoring engine is independent — horizontal scaling is natural
- New dimensions or KB sources can be added without restructuring the pipeline

---

## Acceptance Criteria Coverage (brief §2.5.4)

| Criterion | Priority | How the profile/pipeline enables it |
|---|---|---|
| Knowledge base is real | Must | KB stored in Qdrant; 30+ documented resources |
| Retrieval is traceable | Must | Every roadmap action carries `resource_id` + `source_url` |
| Roadmap is personalised | Must | Different diagnostic outputs → different gap input → different KB queries |
| Cross-module coherence | Must | Diagnostic blockers + low scores drive roadmap via gap analyzer |
| Dashboard is functional | Must | Explainable Report renders all engine outputs in one interface |
| Mon Parcours view exists | Should | Append-only ProfileLog enables full historical tracking |
| Conversational assistant is grounded | Should | System prompt contains only diagnostic, scores, roadmap, and matched KB |
| Evaluation protocol | Should | See maturity.md and ScoringFramework.md |
| Knowledge base is updatable | Could | New resources added to Qdrant without rebuilding the pipeline |
