# Project Profile & System Pipeline

> LeadIt — Shared Data Layer & Full Pipeline Specification
> Ref: AINS Hackathon 2026, Sections 2.2–2.5

## Purpose

The shared project profile is the integration backbone of LeadIt. It is the single structured object that every engine reads from and writes to. This is the mechanism that makes the three mandatory features (Diagnostic, Scoring, Roadmap) genuinely interact through a shared project profile — not merely coexist as independent panels (brief §2.2).

The profile persists in PostgreSQL across sessions to support contextual project memory (brief §2.3.3) and the Mon Parcours tracking view (brief §2.5.3).

---

## Write Rules — Append-Only, Attributed

**No engine may overwrite existing data.** Every write is an append that includes:

1. **`author`** — the engine name (e.g. `diagnostic_engine`, `market_scoring`, `roadmap_engine`, `intake_preprocessor`)
2. **`timestamp`** — ISO 8601 datetime
3. **`data`** — the output or extracted fields

The profile is an **immutable log**. If the diagnostic engine runs twice, both results are preserved. The system reads the latest entry by timestamp but never loses the previous one.

### Why append-only

- **Explainability** (brief §1.3.4): any output traces to the exact engine and moment that produced it
- **Score evolution** (brief §2.4.3): Mon Parcours shows how scores changed over time
- **Debugging**: conflicting engine outputs show what each saw and when
- **Cross-module safety**: the scoring engine cannot overwrite a diagnostic result; the roadmap engine cannot erase a previous recommendation

### Write format

```json
{
  "author": "diagnostic_engine",
  "timestamp": "2026-06-18T15:42:00Z",
  "field": "diagnosed_stage",
  "value": 3,
  "metadata": {
    "evidence_sources": ["profile_field:has_validated_problem", "doc:interview_notes_01"]
  }
}
```

### Reading convention

Engines read the **latest entry by timestamp** for each field. Historical entries remain accessible for tracking and audit.

---

## Full System Pipeline

```
┌─────────────────────┐
│    ADAPTIVE INTAKE   │ ← LLM preprocesses raw answers into structured fields
└──────────┬──────────┘
           ↓ fills
┌─────────────────────┐
│   SHARED PROJECT     │ ← PostgreSQL, append-only log
│      PROFILE         │
└──────────┬──────────┘
           ↓ read by
┌─────────────────────┐
│  DIAGNOSTIC ENGINE   │ ← Rule-based: taxonomy.py criteria → stage + gap + blockers
└──────────┬──────────┘
           ↓ read by
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

| Engine | Reads | Writes (appends) |
|---|---|---|
| Adaptive Intake | Entrepreneur's raw answers | Structured profile fields + raw input log |
| Diagnostic Engine | Profile fields (factual criteria) + self_assessed_stage | diagnosed_stage, evidence, gap, blockers, confidence |
| 5 Scoring Engines | Profile fields + diagnosed_stage | composite_score, sub_scores, justification, anomalies, highest_leverage_gap |
| Gap Analyzer | Diagnostic output + 5 scoring outputs | gaps_ranked, domain_summary, perception_gap_enriched, missing_data_fields |
| Roadmap Engine | Gap analyzer output + profile context + KB | roadmap (3 horizons), matched_resources, unmatched_gaps |
| Explainable Report | All engine outputs (read-only) | Nothing — display only |
| Grounded Assistant | Report snapshot + matched KB entries (read-only) | Nothing — conversational only |

---

## Profile Schema

### Identity & Context

| Field | Type | Source |
|---|---|---|
| `project_id` | UUID | System-generated |
| `created_at` | datetime | System |
| `updated_at` | datetime | System |
| `project_name` | string | Intake |
| `founder_name` | string | Private intake metadata only — never used in outputs |
| `sector` | string | Intake |
| `sub_sector` | string, optional | Intake |
| `geographic_location` | string | Intake |
| `language_preference` | `fr` \| `ar` | Intake |
| `profile_version` | integer | System |
| `evidence_sources` | list[string] | System / all engines |

### Self-Assessment (never used for classification or scoring — only for gap detection)

| Field | Type | Purpose |
|---|---|---|
| `self_assessed_stage` | integer 1–6 | Perception-gap detection |
| `self_assessed_readiness` | string, optional | What the entrepreneur thinks they need next |
| `self_assessed_strengths` | list[string], optional | Anomaly detection cross-reference |
| `self_assessed_weaknesses` | list[string], optional | Anomaly detection cross-reference |

### Team & Organisation

| Field | Type | Used by |
|---|---|---|
| `founder_count` | integer | Scoring (Commercial) |
| `team_size` | integer | Scoring (Scalability) |
| `team_core_complete` | boolean \| null | **Diagnostic** (Stage 3 criterion) |
| `team_roles` | list[string], optional | Scoring context |
| `prior_accompaniment` | list[string], optional | Roadmap (avoid re-recommending completed programs) |
| `founder_has_required_skills` | boolean \| null | Diagnostic (Stage 3 alternative to team completeness) |

### Legal & Administrative

| Field | Type | Used by |
|---|---|---|
| `legal_form_status` | `none` \| `in_progress` \| `registered` \| null | **Diagnostic** (Stage 3 + 4 criteria) |
| `legal_form_type` | string, optional | Roadmap context |
| `registration_date` | date, optional | Scoring context |
| `startup_label` | boolean \| null | Roadmap (Startup Act eligibility) |

### Market & Validation

| Field | Type | Used by |
|---|---|---|
| `has_validated_problem` | boolean \| null | **Diagnostic** (Stage 2 criterion) + **Scoring** (Market) |
| `validation_type` | list[string], optional | Scoring (Market — evidence quality) |
| `customer_interview_count` | integer, optional | Scoring (Market — customer validation) |
| `pilot_users` | integer, optional | Scoring (Market) |
| `pre_orders` | integer, optional | Scoring (Market) |
| `target_market_size` | string, optional | Scoring (Market — addressable size) |
| `geographic_scope` | `local` \| `regional` \| `national` \| `international` \| null | Scoring (Market, Scalability) |
| `competitor_count` | integer, optional | Scoring (Market, Innovation) |
| `differentiation_claimed` | boolean \| null | Scoring (Market, Innovation) |
| `differentiation_description` | string, optional | Scoring (Innovation — LLM rubric) |
| `local_competitors` | list[string], optional | Scoring (Innovation — novelty) |
| `business_model_documented` | boolean \| null | Diagnostic (Stage 3 criterion) + Scoring context |
| `comparison_to_alternatives` | string, optional | Scoring (Innovation) |
| `first_in_market_claimed` | boolean \| null | Scoring (Innovation) |
| `inspired_by_foreign_model` | boolean \| null | Scoring (Innovation) |

### Product & Offer

| Field | Type | Used by |
|---|---|---|
| `product_stage` | `concept` \| `prototype` \| `mvp` \| `production` \| null | Scoring (Commercial) |
| `demo_available` | boolean \| null | Scoring (Commercial) |
| `value_proposition_text` | string, optional | Scoring (Commercial — LLM rubric) |
| `value_prop_clarity_rating` | integer 1–5, optional | Scoring (Commercial) |
| `pricing_model` | string, optional | Scoring (Commercial) |
| `pricing_tested` | boolean \| null | Scoring (Commercial, Market) |
| `pricing_documented` | boolean \| null | Scoring (Commercial) |

### Financial

| Field | Type | Used by |
|---|---|---|
| `has_paying_customers` | boolean \| null | **Diagnostic** (Stage 4 criterion) + **Scoring** (Market) |
| `revenue_model_type` | string, optional | Scoring (Market) |
| `monthly_revenue` | float, optional | Scoring (Market) |
| `revenue_recurring_months` | integer, optional | **Diagnostic** (Stage 6 criterion) |
| `financial_docs_exist` | boolean \| null | **Diagnostic** (Stage 4 criterion) |
| `funding_secured` | boolean \| null | **Diagnostic** (Stage 5 criterion) |
| `funding_amount` | float, optional | Roadmap context |
| `funding_source` | string, optional | Roadmap context |
| `self_financing_confirmed` | boolean \| null | **Diagnostic** (Stage 5 criterion) |
| `cost_structure_type` | `fixed_heavy` \| `variable_heavy` \| `mixed` \| null | Scoring (Scalability) |
| `marginal_cost_estimate` | string, optional | Scoring (Scalability) |

### Distribution & Operations

| Field | Type | Used by |
|---|---|---|
| `distribution_channel_tested` | boolean \| null | **Diagnostic** (Stage 5 criterion) |
| `distribution_channels` | list[string], optional | Scoring context |
| `delivery_model` | string, optional | Scoring (Scalability) |
| `manual_dependency_level` | `low` \| `medium` \| `high` \| null | Scoring (Scalability) |
| `automation_level` | `none` \| `partial` \| `high` \| null | Scoring (Scalability, Innovation) |
| `standardised_process` | boolean \| null | Scoring (Scalability) |
| `client_base_beyond_pilot` | boolean \| null | **Diagnostic** (Stage 6 criterion) |

### Technology

| Field | Type | Used by |
|---|---|---|
| `tech_stack_described` | boolean \| null | Scoring (Innovation) |
| `tech_is_core_to_offer` | boolean \| null | Scoring (Innovation) |
| `ip_protected` | boolean \| null | Scoring (Innovation) |
| `proprietary_data` | boolean \| null | Scoring (Innovation) |
| `network_effects` | boolean \| null | Scoring (Innovation, Scalability) |

### Sustainability & Green

| Field | Type | Used by |
|---|---|---|
| `environmental_impact_type` | `positive` \| `neutral` \| `negative` \| null | Scoring (Green) |
| `carbon_reduction_claimed` | boolean \| null | Scoring (Green) |
| `sdg_alignment` | list[integer], optional | Scoring (Green) |
| `sdg_evidence` | string, optional | Scoring (Green — LLM rubric) |
| `resource_efficiency_measures` | string, optional | Scoring (Green — LLM rubric) |
| `circular_practices_described` | boolean \| null | Scoring (Green) |
| `waste_reduction_measures` | string, optional | Scoring (Green) |

### Scalability-specific

| Field | Type | Used by |
|---|---|---|
| `replicability_evidence` | string, optional | Scoring (Scalability) |
| `multi_segment_potential` | boolean \| null | Scoring (Scalability) |
| `language_adaptability` | boolean \| null | Scoring (Scalability) |
| `team_size_vs_customers` | string, optional | Scoring (Scalability) |

---

## Adaptive Intake — Branching Logic

The intake does not ask every field (brief §2.3.2: "questions must evolve in response to prior answers"). The LLM preprocessor collects answers conversationally; branching logic determines which fields to probe:

| If the entrepreneur says... | Then probe... | Skip... |
|---|---|---|
| sector = agri-food | Certifications, supply chain, seasonality | Tech stack depth |
| self_assessed_stage >= 4 | `has_paying_customers`, `financial_docs_exist`, `revenue_recurring_months` | Basic problem articulation |
| legal_form_status = registered | `registration_date`, `startup_label` | Legal form questions |
| environmental_impact_type = positive | `sdg_alignment`, `resource_efficiency_measures`, `circular_practices_described` | — |
| has_paying_customers = true | `monthly_revenue`, `revenue_recurring_months`, `revenue_model_type` | — |

Uncollected fields remain `null` in the profile. Both the diagnostic and scoring engines handle `null` via the `None` return type — uncertainty surfaced, not hidden.

### Traceability of extraction

Every intake interaction is logged:

```json
{
  "author": "intake_preprocessor",
  "timestamp": "2026-06-18T14:30:00Z",
  "raw_input": "on a fait un petit test avec 3 clients à Sousse qui ont payé",
  "extracted_fields": {
    "has_paying_customers": true,
    "customer_interview_count": 3,
    "geographic_scope": "local",
    "distribution_channel_tested": true
  }
}
```

Raw input and extracted fields both saved. If the LLM misinterprets, the log shows the error.

---

## Engine Output Storage

All engine outputs follow the same append-only format:

```json
{
  "author": "<engine_name>",
  "timestamp": "<ISO 8601>",
  "output": { ... }
}
```

### Engines and their `author` tags

| Engine | `author` value | Output type |
|---|---|---|
| LLM preprocessor | `intake_preprocessor` | Extracted structured fields from raw answers |
| Diagnostic | `diagnostic_engine` | Stage, evidence, gap, blockers, confidence |
| Market scoring | `market_scoring` | Composite score, sub-scores, justification, anomalies |
| Commercial scoring | `commercial_scoring` | Same structure |
| Innovation scoring | `innovation_scoring` | Same structure |
| Scalability scoring | `scalability_scoring` | Same structure |
| Green scoring | `green_scoring` | Same structure |
| Gap Analyzer | `gap_analyzer` | Ranked gaps, domain summary, enriched perception gap |
| Roadmap | `roadmap_engine` | Ordered actions with KB citations, 3 time horizons |

---

## Privacy & Anonymisation

Brief §1.5: "any sensitive data (personal, financial, project-specific) must be masked or anonymised."

- `founder_name` stored but **never exposed in outputs** to third parties. Outputs reference `project_id` or `project_name` only.
- Financial fields (`monthly_revenue`, `funding_amount`) used for scoring computation but maskable in dashboard views with a toggle.
- Profile is scoped to the authenticated user. No data shared between entrepreneurs. Support officers see diagnostic and scoring outputs only with explicit consent.

---

## Non-Functional Requirements (brief §1.5)

### Responsiveness
The pipeline must return results within a few seconds. The five scoring engines run in parallel. The diagnostic and gap analyzer are pure logic (sub-millisecond). The roadmap's KB query is the bottleneck — structured filtering over 30+ entries is fast; semantic search over Qdrant is bounded by top-K.

### Reliability
Missing, dirty, or incomplete data must not crash the system. The `None` return in the taxonomy model and the weight-redistribution in scoring handle this. The intake preprocessor validates extracted fields before writing to the profile.

### Scalability mindset
- PostgreSQL handles concurrent users and growing profiles
- Qdrant handles growing KB corpus without rebuild
- The multi-engine architecture allows horizontal scaling of scoring (each engine is independent)
- New scoring dimensions or KB sources can be added without restructuring the pipeline

---

## Mon Parcours — Persistent Tracking

Brief §2.5.3: "a persistent view where the entrepreneur sees their current stage, past recommendations, actions taken, and next steps."

Mon Parcours reads the full append-only log chronologically and presents:

- **Stage progression** — diagnosed_stage over time (did they advance?)
- **Score evolution** — how each composite score changed between runs
- **Blockers resolved** — which gaps were closed by new data or actions
- **Roadmap history** — past recommendations vs. current recommendations
- **Missing data resolved** — which `None` fields were filled

Each entry in Mon Parcours is a snapshot from the log at a point in time. The entrepreneur sees their project evolving — not just a static report.

---

## Explainable Report — Dashboard Layout

Brief §2.5.3: "a visual interface presenting maturity level, composite scores with sub-score breakdowns, priority blockers, recommended next actions, and the roadmap."

The dashboard reads all engine outputs (read-only) and renders:

| Section | Source engine | What it shows |
|---|---|---|
| Maturity stage + perception gap | Diagnostic | Stage progress bar, gap warning, confidence level |
| Score radar chart | 5 scoring engines | 5-axis radar, expandable sub-score panels |
| Blockers & gaps | Gap analyzer | Ranked weakness list, domain severity, missing data prompts |
| Roadmap | Roadmap engine | Three-column timeline (immediate / short / medium), each action with KB source link |
| Anomalies | Scoring engines | Contradiction warnings |
| Mon Parcours | Full log | Historical progression view |

The dashboard does **not** compute anything. If a number appears on screen, an engine produced it and it's in the log.

---

## Grounded Conversational Assistant

Brief §2.5.3: "a secondary conversational layer that responds to questions using the diagnostic results, scores, roadmap, and knowledge base as its grounding context — it does not operate independently."

Brief §1.6: "the conversational assistant is NOT the core product."

### What it receives as context

A read-only snapshot of the full engine output chain, injected as the LLM's system prompt:

```python
system_prompt = f"""
You are the LeadIt assistant for project "{project_name}".
You answer questions ONLY from the data below.
If the answer is not in this data, say you don't have that information.
Do NOT invent program names, amounts, or advice.
Respond in {language_preference}.

DIAGNOSTIC: {diagnosis_summary}
SCORES: {scores_with_justifications}
GAPS: {gaps_ranked}
ROADMAP: {roadmap_actions}
KB EXCERPTS: {matched_kb_entries_only}
"""
```

### What it can do

- Explain why a stage was assigned ("you're at Stage 2 because team_core_complete is False")
- Explain a score ("your Market score is 5.2 because customer validation is weak — only 3 interviews")
- Explain a roadmap action ("we recommend BTS microcredit because your funding gap is the top blocker")
- Answer questions about KB resources ("BFPME offers co-financing for projects between 100kDT and 15MDT")

### What it cannot do

- Answer questions from general knowledge — if the answer isn't in the diagnostic, scores, roadmap, or matched KB entries, it says so
- Re-run the diagnostic or scoring — it reads results, it doesn't produce them
- Recommend resources not in the KB — it can only reference matched entries
- Modify the profile — read-only access

### Traceability

Brief §2.5.4 (Should): "assistant responses reference diagnostic results, scores, or knowledge base items — not generic LLM output."

Every assistant response should cite where its information came from: a diagnostic result, a score, a gap, or a KB resource_id. If the LLM would need to go outside the provided context to answer, it refuses.

---

## Versioning & Schema Evolution

The profile is append-only by design, so versioning is built in:

1. **New fields default to null** — adding a field never breaks existing profiles
2. **No data is ever deleted** — every engine output retained with author and timestamp
3. **`updated_at` timestamp** — tracks last modification by any source
4. **Rollback** — if re-diagnosis produces a worse result after bad data, the previous diagnosis remains in the log

---

## Acceptance Criteria Coverage (brief §2.5.4)

| Criterion | Priority | How the profile/pipeline enables it |
|---|---|---|
| Knowledge base is real | Must | KB stored in Qdrant; 30+ documented resources (see KB spreadsheet) |
| Retrieval is traceable | Must | Every roadmap action carries `resource_id` + `source_url` from KB |
| Roadmap is personalised | Must | Different diagnostic outputs → different gap analyzer input → different KB queries → different roadmaps |
| Cross-module coherence | Must | Diagnostic gaps + low scores drive roadmap retrieval via the gap analyzer (shared profile is the integration mechanism) |
| Dashboard is functional | Must | Explainable Report renders all engine outputs in one interface |
| Mon Parcours view exists | Should | Append-only log enables full historical tracking |
| Conversational assistant is grounded | Should | System prompt contains only diagnostic, scores, roadmap, and matched KB — no general knowledge |
| Evaluation protocol | Should | See Maturity.md and ScoringFramework.md for metrics |
| Knowledge base is updatable | Could | New resources added to Qdrant without rebuilding the pipeline |
