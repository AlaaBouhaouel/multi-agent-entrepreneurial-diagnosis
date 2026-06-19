# Maturity Taxonomy & Diagnostic Engine

> LeadIt — Feature 1 (Adaptive Diagnostic Engine)
> Ref: AINS Hackathon 2026, Section 2.3

## Purpose

The maturity taxonomy classifies an entrepreneurial project into one of six ordered stages based on factual, verifiable criteria. It answers **"where is this project in its lifecycle?"** — not how strong or healthy the project is (that is the scoring engine's job, Feature 2).

Classification is evidence-linked: every stage assignment traces back to specific data points collected from the entrepreneur's profile. No stage is assigned by intuition, self-report alone, or LLM inference. The diagnostic engine is deterministic and rule-based.

---

## Adaptive Intake

The intake is not a static form. Questions evolve in response to prior answers. The branching logic is part of what will be evaluated (brief §2.3.2).

### Branching rules

- A project in **sector = agri-food** triggers sector-specific questions (certifications, supply chain, seasonal dependencies)
- A project claiming **market traction** triggers validation-evidence probes: how many customers? paid or free? interviews or assumptions?
- A project with **legal_form_status = "registered"** skips legal-form questions and advances to financial-evidence probes
- A project claiming **self_assessed_stage >= 4 (Fundraising)** triggers deeper probes on paying customers, financial docs, and revenue evidence — because this is where the perception gap is sharpest
- A project with **environmental_impact_type = "positive"** triggers Green-specific follow-ups (SDG alignment, resource efficiency, circular practices)

### Minimum branching demonstration

The system must produce **meaningfully different question sequences for at least 3 distinct profiles** (brief §2.3.4, Must):

| Profile | Sector | Self-assessed stage | Key branching path |
|---|---|---|---|
| Profile A | Agri-food, Médenine | 4 (Fundraising) | Sector-specific → validation probes → financial evidence deep-dive → perception gap triggered |
| Profile B | Fintech, Tunis | 2 (Market Validation) | Tech-core questions → market validation evidence → minimal financial probing |
| Profile C | Artisanat, Kébili | 1 (Ideation) | Basic problem articulation → team composition → legal status → short path |

### LLM role in intake

The LLM **preprocesses** the entrepreneur's natural-language answers into structured profile fields. It does not decide the classification.

```
Entrepreneur says: "on a testé avec 3 clients à Sousse qui ont payé"

LLM extracts → {
    has_paying_customers: true,
    customer_interview_count: 3,
    geographic_scope: "local",
    distribution_channel_tested: true
}

Both the raw input and the extracted fields are stored in the append-only log
for traceability.
```

### Language

The intake operates in **French and/or Arabic** (brief §2.3.5). The LLM preprocessor handles both languages. All criterion labels are stored in French (`label_fr` in taxonomy.py) for user-facing output.

---

## The Six Stages

Stages are ordered chronologically. A project sits at the **highest stage whose criteria all pass**. If a project satisfies Growth criteria but fails a Structuration criterion, it is classified at the stage just before the first failure — the system does not skip gaps.

| # | Stage | What it means | Entry condition |
|---|---|---|---|
| 1 | **Ideation** | Idea exists; problem articulated; no external validation yet | Default — no criteria required |
| 2 | **Market Validation** | Market is defined, context assessed, differentiation articulated, domain competence established, and real demand evidence collected | 7 criteria — see Criteria per Stage |
| 3 | **Structuration** | The project is taking organisational and legal shape | Business model + team + legal form |
| 4 | **Fundraising** | A validated, registered enterprise preparing to raise or reinvest | Paying customers + financial docs + legal registration |
| 5 | **Launch Planning** | Financing secured; distribution being tested in real conditions | Funding confirmed + distribution channel tested |
| 6 | **Growth** | Repeatable revenue; scaling beyond manual effort and pilot users | Recurring revenue (3+ months) + client base beyond pilot |

Scope discipline (brief §2.3.5): six stages with clear, defensible boundaries — not ten ambiguous ones.

---

## Criteria per Stage

Each criterion is a factual check against the project profile. It returns one of three values:

| Return | Meaning | Implication |
|---|---|---|
| `True` | Criterion satisfied | Evidence present, checkpoint passed |
| `False` | Criterion not satisfied | A real, identified gap — the project has not reached this milestone |
| `None` | Data missing | The system cannot determine the answer — uncertainty is surfaced, not hidden as failure (brief §2.3.4, Should: "handles ambiguity") |

### Stage 1 — Ideation

No criteria. Every project enters here by default.

### Stage 2 — Market Validation

All seven criteria must pass.

| Criterion | Profile field(s) | Logic | Domain |
|---|---|---|---|
| Target customer defined | `target_customer_defined` | Founder has identified their target customer segment | marché |
| Geographic scope defined | `geographic_scope` | Founder has defined whether the project targets local or international market | marché |
| Market context assessed | `idea_is_new` OR `foreign_model_studied` | Either the idea is original locally, or the founder has studied the foreign equivalent and knows what they bring new | marché |
| Differentiation articulated | `differentiation_claimed` | Founder clearly articulates what is new vs. existing alternatives | marché |
| Domain competence | `founder_has_required_skills` OR `team_core_complete` | Founder has sufficient domain knowledge, or the team covers key competencies | organisationnel |
| Prior professional experience | `founder_has_prior_experience` | Founder has relevant professional experience before this project | organisationnel |
| Customer validation | `pre_orders`, `pilot_users`, `customer_interview_count`, `validation_type` | At least one form of real demand evidence: pre-orders, pilot users, surveys, or structured interviews | marché |

### Stage 3 — Structuration

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Business model documented | `business_model_documented` | A written business model canvas, pricing grid, or equivalent — not a verbal description | organisationnel |
| Core team complete | `team_core_complete` | Key roles staffed beyond the solo founder | organisationnel |
| Legal form initiated | `legal_form_status` | Status is `in_progress` or `registered` | légal |

All three must pass.

### Stage 4 — Fundraising

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Paying customers | `has_paying_customers` | Real transactions — not intentions or free-tier usage | financier |
| Financial documents exist | `financial_docs_exist` | Forecast, pitch deck with projections, or accounting records | financier |
| Legal form registered | `legal_form_status` | Status is `registered` — legally constituted | légal |

This is where the perception gap is sharpest. Founders frequently self-assess here while missing one or more criteria.

### Stage 5 — Launch Planning

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Funding secured | `funding_secured` OR `self_financing_confirmed` | External financing or sufficient self-financing — either path satisfies | financier |
| Distribution channel tested | `distribution_channel_tested` | At least one channel tested in real market conditions | marché |

### Stage 6 — Growth

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Recurring revenue | `revenue_recurring_months` | Revenue in at least 3 consecutive months | financier |
| Client base beyond pilot | `client_base_beyond_pilot` | Customers beyond the pilot/early-adopter circle | marché |

---

## Classification Algorithm

```python
def classify(profile):
    assigned_stage = IDEATION
    evidence = {}

    for stage in [MARKET_VALIDATION, STRUCTURATION, FUNDRAISING, LAUNCH_PLANNING, GROWTH]:
        results = evaluate_criteria(stage, profile)
        evidence[stage] = results

        if all(r.value == True for r in results):
            assigned_stage = stage
        else:
            break  # stop at first stage with any failure or unknown

    confidence = compute_confidence(evidence)
    return assigned_stage, evidence, confidence
```

The classifier walks stages in order and stops at the first failure or unknown. The full evidence map is returned for explainability (brief §2.3.4, Must: "classification is traceable — every maturity stage assignment links to specific collected data points").

### Confidence assessment

Confidence is computed as a ratio: `score = resolved_criteria / total_criteria_evaluated`, where resolved means the criterion returned True or False (not None).

| Score | Level | Meaning |
|---|---|---|
| ≥ 0.80 | `high` | Most criteria are resolved — classification is definitive |
| ≥ 0.50 | `medium` | Significant missing data — classification is provisional |
| < 0.50 | `low` | Majority of criteria unknown — insufficient data for reliable classification |

### None propagation rule

When a criterion returns `None`, the system uses the **block** approach: classify the project at the stage before the unknown. A "missing data" indicator in the output prompts the entrepreneur to provide the information. This keeps classifications defensible and avoids false advancement.

---

## Perception-Reality Gap Detection

The diagnostic engine's headline differentiator (brief §2.3.5: "perception gap is a feature, not a side effect — design for it explicitly"). The entrepreneur provides their `self_assessed_stage` during intake. The system independently computes the `diagnosed_stage`. If these diverge:

1. Flags the gap explicitly
2. Identifies the **specific criteria** that caused the divergence
3. Tags each diverging criterion with its **blocker domain**

### Minimum demonstration: 3 divergence cases (brief §2.3.4, Must)

| Case | Self-assessed | Diagnosed | Diverging criteria | Financial context |
|---|---|---|---|---|
| Case 1 | 4 (Fundraising) | 2 (Market Validation) | `business_model_documented = False`, `team_core_complete = False` | Founder claims financing readiness but hasn't documented their model. VAN not computable — no unit economics provided. |
| Case 2 | 5 (Launch Planning) | 3 (Structuration) | `has_paying_customers = False`, `financial_docs_exist = None` | `selling_price` and `unit_cost` provided → system computed `gross_margin = 42%` and `van_5_years = +32,000 DT` — the numbers are healthy but no real sales exist yet. The system surfaces: "your financial projections are viable but unvalidated — Stage 5 requires real transactions." |
| Case 3 | 4 (Fundraising) | 4 (Fundraising) — confirmed, but with financial warnings | All Stage 4 criteria pass | `credit_eligibility_path = "none"` (needs > 150k, no guarantee), `repayment_capacity_ratio = 0.52`. Stage is correct but the system warns: "you're at Fundraising but your credit path is blocked and debt load is high — the roadmap will prioritise financing alternatives." |

Case 2 demonstrates the system's ability to separate **stage milestones** (you haven't sold anything = not Fundraising) from **financial health** (your numbers work on paper). Case 3 shows a correctly staged project that still has critical financial blockers — the diagnostic is right, but the roadmap needs to address the financing gap.

---

## Blocker Identification

Each failed or unknown criterion carries a `category` tag (its blocker domain). The diagnostic engine aggregates these into a **blocker profile** (brief §2.3.2: "a structured catalogue of common entrepreneurial blockers mapped to maturity stages and domains"):

| Domain | What it covers | Examples of computed enrichment |
|---|---|---|
| `financier` | Revenue, funding, financial documentation, pricing | `credit_eligibility_path = "none"` enriches a funding blocker; `van_5_years < 0` enriches a revenue model blocker; `repayment_capacity_ratio > 0.40` flags debt overload |
| `légal` | Legal form, registration, regulatory compliance | — |
| `marché` | Market validation, customer base, distribution | `breakeven_units > expected_monthly_units` enriches a market viability blocker |
| `organisationnel` | Team, business model, processes, governance | — |
| `technique` | Product/technology readiness, technical infrastructure | — |

Blockers are ranked by:
1. **Stage position** — a blocker at Stage 3 is more fundamental than one at Stage 5
2. **Count per domain** — a domain with 3 failing criteria is systemic
3. **Severity** — `False` (confirmed gap) outranks `None` (unknown)
4. **Financial severity** — blockers enriched with computed financial data (VAN negative, no credit path, no operating runway) are escalated in priority

The diagnostic engine itself does not compute VAN or credit paths — those come from the computed fields in the profile. But it reads them when they exist to **enrich** the blocker context. A `funding_secured = False` blocker at Stage 5 is more severe when paired with `credit_eligibility_path = "none"` than when paired with `credit_eligibility_path = "bts_fonapra"`.

Brief §2.3.4 (Should): "priority blockers are ranked and linked to the maturity stage."

---

## Contextual Project Memory

Brief §2.3.3: "persist the project profile across sessions so that the diagnosis refines over time as new information is added."

The diagnosis result is written to the shared project profile's **append-only log** (see ProjectProfile.md). Every engine write includes:

- `author`: `"diagnostic_engine"`
- `timestamp`: ISO 8601 datetime
- `output`: the full diagnosis (stage, evidence, gap, blockers, confidence)

Re-entering the system with updated information triggers reclassification. The old and new diagnoses coexist in the log — Mon Parcours reads both to show progression.

Brief §2.3.4 (Should): "re-entering the system with updated information refines the diagnosis."

---

## Diagnostic Output Format

```json
{
  "author": "diagnostic_engine",
  "timestamp": "2026-06-18T15:42:00Z",
  "output": {
    "diagnosed_stage": 2,
    "diagnosed_stage_name_fr": "Validation marché",
    "self_assessed_stage": 4,
    "perception_gap": 2,
    "perception_gap_direction": "overestimate",
    "perception_gap_criteria": [
      {"criterion": "team_core_complete", "stage": 3, "value": false, "domain": "organisationnel",
       "label_fr": "Équipe noyau complète"},
      {"criterion": "has_paying_customers", "stage": 4, "value": null, "domain": "financier",
       "label_fr": "Ventes réelles enregistrées"}
    ],
    "stage_evidence": { ... },
    "blockers": [ ... ],
    "blocker_summary": {"organisationnel": 1, "financier": 1},
    "confidence": "medium",
    "none_count": 1,
    "total_criteria_evaluated": 6
  }
}
```

---

## What the Diagnostic Engine Does NOT Do

- **Does not score** the project — that is Feature 2
- **Does not recommend resources** — that is Feature 3 (roadmap engine)
- **Does not use the LLM for classification** — the LLM only preprocesses raw intake answers into structured fields; the classification is pure rule-based Python
- **Does not guess** — missing data returns `None`, never inferred as `True` or `False`
- **Does not overwrite** — every run appends a new timestamped entry to the log

---

## Connection to Downstream Engines

- **→ Scoring Engines (M/C/I/S/G):** Receive `diagnosed_stage` as context for score interpretation
- **→ Gap Analyzer:** Receives `blockers`, `perception_gap_criteria`, and `confidence` to merge with scoring anomalies into a unified weakness profile
- **→ Roadmap Engine (via Gap Analyzer):** Blocker domains are the primary filter for KB retrieval
- **→ Shared Profile:** Diagnosis persists across sessions for Mon Parcours tracking
- **→ Grounded Assistant:** The assistant's system prompt includes the diagnosis so it can answer questions about stage and gaps without re-running the engine

---

## Evaluation Protocol

Brief §2.3.4 (Should): "at least one classification metric reported on a labelled test set."

**Metric:** Classification accuracy — proportion of test profiles where the diagnostic engine assigns the correct maturity stage.

**Test set:** A small set of synthetic entrepreneur profiles (minimum 10, target 20) with ground-truth stage labels assigned by the team. Each profile includes all relevant fields and a documented justification for the ground-truth label.

**Protocol:**
1. Run the diagnostic engine on each test profile
2. Compare `diagnosed_stage` to `ground_truth_stage`
3. Report accuracy, plus a confusion matrix showing which stages are most often confused
4. For each misclassification, document which criteria caused the error

**Target:** ≥ 80% accuracy on the test set. Misclassifications within ±1 stage are flagged as "adjacent" errors (less severe than ±2 errors).

---

## Acceptance Criteria Checklist (from brief §2.3.4)

| Criterion | Priority | How LeadIt addresses it |
|---|---|---|
| Adaptive intake is real | Must | Branching logic produces different question sequences for 3+ profiles (see Adaptive Intake section) |
| Classification is traceable | Must | Every stage links to specific data points via the evidence map |
| Gap detection works | Must | 3 demonstrated divergence cases (see Perception-Reality Gap section) |
| End-to-end demo | Must | Intake → profile → diagnostic output runs without manual intervention |
| Blocker identification | Should | Priority blockers ranked by stage position, count, and severity |
| Handles ambiguity | Should | None return type + confidence levels + missing-data prompts |
| Persistent project context | Should | Append-only log in PostgreSQL; re-diagnosis on updated profiles |
| Evaluation protocol | Should | Classification accuracy on labelled test set |
