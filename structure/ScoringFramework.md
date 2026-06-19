# Scoring Framework

> LeadIt — Feature 2 (Explainable Multi-Dimensional Scoring)
> Ref: AINS Hackathon 2026, Section 2.4

## Purpose

The scoring engine evaluates **how strong a project is** across five dimensions. It answers a different question than the maturity taxonomy (Feature 1): a project can be at Stage 6 (Growth) with a weak Commercial Offer score, or at Stage 2 (Market Validation) with a high Innovation score. Stage is horizontal (where on the timeline); scoring is vertical (how healthy at that position).

Every score must be explainable (brief §2.4.5): "a score without a traceable justification is not an explainable score — it is an opaque label. Every criterion contribution must be surfaced."

---

## Architecture: Five Independent Scoring Engines

Five engines run **in parallel** — they don't depend on each other's output. Each reads the shared project profile and the diagnostic engine's `diagnosed_stage`, evaluates its own sub-criteria, and appends its scored output to the append-only log.

They share the same scoring mechanics (weighted sum with floor penalty) but each has its own sub-criteria, weights, profile fields, and anomaly rules.

They do **not** see each other's scores. Cross-score analysis is the Gap Analyzer's job.

---

## Data Preprocessing: LLM Extracts, Rules Decide

Before any scoring happens, the entrepreneur's raw natural-language answers are preprocessed by the LLM into structured profile fields during intake. The scoring engines never see raw text — they work with clean structured data.

```
Entrepreneur says: "on a un modèle freemium, 3 clients payants sur Sousse"

LLM extracts → {
    revenue_model_type: "freemium",
    has_paying_customers: true,
    customer_interview_count: 3,
    geographic_scope: "local"
}

Both raw input and extracted fields stored in the append-only log.
```

The scoring engines then apply documented rules to these structured fields. The LLM does not decide any score — it only cleans the input and, after scoring, generates the natural-language justification.

---

## The Five Composite Scores

Fixed by the brief (§2.4.2). All five must be implemented.

| Score | Core question |
|---|---|
| **Market** | Is there a real, reachable market that wants this? |
| **Commercial Offer** | Is the product/service clear, differentiated, and properly priced? |
| **Innovation** | Does this bring something meaningfully new to the Tunisian context? |
| **Scalability** | Can this grow without linear cost increase or manual dependency? |
| **Green** | Does this project contribute positively to environmental sustainability? |

---

## Sub-Criteria, Weights, and Justification

Brief §2.4.4 (Must): "criteria weights are documented" and "weighting methodology is described and defensible."

### Market Score

Top-level sub-criteria and their weights (must sum to 1.0):

| Sub-criterion | Weight | Structure | What it measures |
|---|---|---|---|
| **Market share** | **0.35** | **nested** | Market size + competitive density |
| Customer validation evidence | 0.25 | flat | Has anyone confirmed demand? |
| **Revenue model viability** | **0.20** | **nested** | Revenue model tested and sustainable |
| **Financial readiness** | **0.20** | **nested** | Project can sustain itself financially |

**Weight justification — Market share (0.35):** Brief §2.4.2 lists market share as a combined dimension. The old flat entries `Addressable market size` (0.20) and `Competitive landscape` (0.15) are merged into a single parent (0.20 + 0.15 = 0.35), removing the artificial split while preserving their relative influence within the parent. Customer validation evidence stays highest at 0.25 — real demand evidence is the strongest market signal.

#### Market share — nested leaves (parent weight 0.35)

Leaf weights are derived from the original top-level weights: `leaf_weight = old_weight / parent_weight`.

| Leaf | Leaf weight | Derivation | Leaf 0–10 rule | Key fields |
|---|---|---|---|---|
| `addressable_market_size` | **0.571** | 0.20 / 0.35 | national/international → 9, regional → 6, local → 3 | `target_market_size`, `geographic_scope`, `sector` |
| `competitive_landscape` | **0.429** | 0.15 / 0.35 | 0 competitors → 10, 1–3 → 7, 4–9 → 4, 10+ → 1; boosted by `differentiation_claimed` | `competitor_count`, `differentiation_claimed`, `local_competitors` |

#### Revenue model viability — nested leaves (parent weight 0.20)

Derived from old `score += N` logic (max raw points = 3 + 3 + 2 + 2 = 10).
`leaf_weight = leaf_max_points / total_max_points`

| Leaf | Leaf weight | Derivation | Leaf 0–10 rule |
|---|---|---|---|
| `paying_customers` | **0.30** | 3 / 10 | `has_paying_customers = True` → 10, else → 0 |
| `margin_health` | **0.30** | 3 / 10 | `gross_margin_pct > 0.30` → 10, `> 0.15` → 5, `≤ 0` → 0 *(also raises floor flag on this leaf)* |
| `van_positive` | **0.20** | 2 / 10 | `van_5_years > 0` → 10, else → 0 |
| `breakeven_under_24mo` | **0.20** | 2 / 10 | `breakeven_months < 24` → 10, `24–36` → 5, else → 0 |

#### Financial readiness — nested leaves (parent weight 0.20)

Derived from old `score += N` logic (max raw points = 3 + 2 + 3 + 2 = 10, before penalty).

| Leaf | Leaf weight | Derivation | Leaf 0–10 rule |
|---|---|---|---|
| `opex_financing` | **0.30** | 3 / 10 | `has_opex_financing = True` → 10, else → 0 |
| `opex_runway` | **0.20** | 2 / 10 | `opex_months_covered ≥ 6` → 10, `≥ 3` → 5, `< 3` → 0 |
| `credit_path` | **0.30** | 3 / 10 | `commercial_bank` → 10, `bts_fonapra` → 7, `none` (needs credit) → 3 |
| `repayment_capacity` | **0.20** | 2 / 10 | `ratio < 0.30` → 10, `0.30–0.40` → 5, `> 0.40` → 0 |

**Post-rollup penalty on `repayment_capacity` leaf:** when `repayment_capacity_ratio > 0.40`, subtract 1 point from the rolled-up `financial_readiness` sub-criterion score *after* computing the weighted sum. Rationale: the original logic applied `score -= 1` as an overload warning, not as a leaf absence — keeping it as a post-rollup correction preserves that intent while staying consistent with the leaf-weight derivation method.

### Commercial Offer Score

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Value proposition clarity | 0.25 | Can the founder articulate the offer? | `value_proposition_text`, `value_prop_clarity_rating` |
| Product/service readiness | 0.25 | Is the product functional? | `product_stage`, `demo_available` |
| Pricing strategy coherence | 0.25 | Is pricing viable and competitive? | `gross_margin_percentage` (computed), `price_vs_local_market` (computed), `price_vs_foreign_market` (computed), `pricing_tested` |
| Offer-need alignment | 0.25 | Does the offer solve the validated problem? | Cross-reference: `value_proposition_text` vs `has_validated_problem` |

**Weight justification:** Four equal weights (0.25 each). `Pricing strategy coherence` is now nested — it uses real computed margins and price ratios instead of a single yes/no. The other three sub-criteria stay flat (§A.2: do not manufacture sub-leaves where the brief lists flat sets).

#### Pricing strategy coherence — nested leaves (parent weight 0.25)

Derived from old `score += N` logic (max raw points = 3 + 3 + 2 = 8).

| Leaf | Leaf weight | Derivation | Leaf 0–10 rule |
|---|---|---|---|
| `margin_health` | **0.375** | 3 / 8 | `gross_margin_pct > 0.40` → 10, `> 0.20` → 7, `> 0` → 3, `≤ 0` → 0 *(also raises floor flag on parent)* |
| `price_positioning` | **0.375** | 3 / 8 | competitive range (0.7–1.3 vs local) → 10; premium + differentiation → 7; cheaper than market → 3; premium, no differentiation → 0 *(anomaly flag)*; if foreign: cheaper by > 20% → 10, comparable → 7, more expensive → 3 |
| `pricing_tested` | **0.25** | 2 / 8 | `pricing_tested = True` → 10, else → 0 |

### Innovation Score

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Local novelty | 0.30 | Is this new to Tunisia/MENA? | `local_competitors`, `inspired_by_foreign_model`, `first_in_market_claimed`, `market_price_local` (null = doesn't exist locally) |
| Technology intensity | 0.25 | Is tech a structural advantage? | `tech_stack_described`, `tech_is_core_to_offer`, `automation_level` |
| Barrier to entry | 0.20 | How hard to replicate? | `ip_protected`, `proprietary_data`, `network_effects` |
| Departure from existing | 0.25 | Meaningfully different from alternatives? | `differentiation_description`, `comparison_to_alternatives`, `price_vs_local_market` (computed — price disruption counts as departure) |

**Weight justification:** Local novelty weighted highest (0.30) because the brief is explicitly about the Tunisian context. New addition: `market_price_local = null` (product doesn't exist locally) is a strong novelty signal. Price disruption (`price_vs_local_market < 0.5`) counts as departure from existing offerings even without technology innovation.

### Scalability Score

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Replicability | 0.30 | Can it expand without rebuilding? | `delivery_model`, `standardised_process`, `replicability_evidence` |
| Manual dependency | 0.25 | Does growth require proportional effort? | `manual_dependency_level`, `automation_level`, `team_size_vs_customers` |
| Unit economics at scale | 0.25 | Do the numbers improve with volume? | `unit_cost`, `fixed_costs_monthly`, `gross_margin_percentage` (computed), `breakeven_units` (computed) |
| Addressable reach | 0.20 | Can it expand geographically? | `geographic_scope`, `multi_segment_potential`, `language_adaptability` |

**Weight justification:** Replicability remains highest (0.30). `Unit economics at scale` is now nested — the three distinct computed signals (leverage, margin, headroom) each become a leaf with a derived weight. Other sub-criteria stay flat (§A.2).

#### Unit economics at scale — nested leaves (parent weight 0.25)

Derived from old `score += N` logic (max raw points = 3 + 3 + 3 = 9; equal contribution → equal weights).

| Leaf | Leaf weight | Derivation | Leaf 0–10 rule |
|---|---|---|---|
| `operating_leverage` | **0.333** | 3 / 9 | `fixed_ratio > 0.6` → 10, `> 0.4` → 7, else → 3 |
| `margin_health` | **0.333** | 3 / 9 | `gross_margin_pct > 0.40` → 10, `> 0.20` → 7, `> 0` → 3, `≤ 0` → 0 |
| `breakeven_headroom` | **0.333** | 3 / 9 | `headroom > 2.0` → 10, `> 1.2` → 7, `> 1.0` → 3, `≤ 1.0` → 0 |

where `fixed_ratio = fixed_costs_monthly / (fixed_costs_monthly + monthly_variable_costs)` and `headroom = expected_monthly_units / breakeven_units`.

### Green Score

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Environmental impact | 0.30 | Does it reduce environmental harm? | `environmental_impact_type`, `carbon_reduction_claimed` |
| SDG alignment | 0.25 | Maps to UN SDGs? | `sdg_alignment`, `sdg_evidence` |
| Resource efficiency | 0.25 | Minimises waste/energy/materials? | `resource_efficiency_measures` |
| Circular economy | 0.20 | Reuses, recycles, extends lifecycle? | `circular_practices_described`, `waste_reduction_measures` |

**Weight justification:** Environmental impact weighted highest (0.30) as the most direct measure. SDG alignment without real impact should not inflate the score.

---

## Scoring Mechanics

### Sub-criterion scoring (0–10)

Three methods depending on the field type:

**Method 1 — Boolean fields:** Direct mapping.
```python
True  → 8    (evidence present)
False → 2    (evidence absent)
None  → None (missing data, not zero)
```

**Method 2 — Numeric fields:** Normalised to 0–10 scale.
```python
customer_interview_count:
  0      → 0
  1–4    → 3
  5–9    → 5
  10–19  → 7
  20+    → 9
```

**Method 3 — Free-text fields (LLM-assisted):** For fields like `value_proposition_text` or `differentiation_description`, the LLM scores against a **documented rubric**:
```
Rubric for value_proposition_text:
  0–2: Missing, empty, or incomprehensible
  3–4: Vague — could describe any project
  5–6: Clear but generic — what, not why
  7–8: Specific and differentiated — what, why, for whom
  9–10: Compelling, concrete, and immediately actionable
```

The rubric is documented and reproducible. The LLM applies it but does not invent the scoring criteria.

### Handling None (missing data) — two-level cascade

**Leaf level (nested sub-criteria only):** if a leaf field is `None`, redistribute its weight across the scored sibling leaves within the same parent. The parent sub-criterion score is computed from scored leaves only:

```python
# Within a nested parent (e.g. Revenue model viability):
scored_leaves = [(leaf, score, weight) for leaf, score, weight in leaves if score is not None]
if not scored_leaves:
    parent_score = None          # all leaves missing → parent is None
else:
    total_w = sum(w for _, _, w in scored_leaves)
    parent_score = sum(s * (w / total_w) for _, s, w in scored_leaves)
```

**Sub-criterion level (flat + nested parents):** if a sub-criterion score is `None`, redistribute its weight across scored sub-criteria at the composite level — existing behaviour, unchanged.

**Determinism requirement:** identical input → identical output. Weight redistribution is purely arithmetic; no randomness, no LLM involvement.

**None field path recording:** every None leaf is recorded with a dotted path in `none_fields`, e.g. `revenue_model_viability.van_positive`. This feeds the "missing data prompts" in the dashboard.

### Floor penalty — applied at sub-criterion level, NOT leaf level

Compute all leaf scores → roll up to the sub-criterion's 0–10 value → **then** test the floor. A single weak leaf must not floor the entire composite; a weak *rolled-up sub-criterion* does.

```python
# After rolling each parent's leaves into a sub-criterion score:
if any(sub.score < FLOOR_THRESHOLD for sub in sub_criteria_scored):  # FLOOR_THRESHOLD = 2
    composite = min(composite, FLOOR_CAP)                              # FLOOR_CAP = 4.0
```

Rationale (§2.4.5): "a fundamental weakness" refers to a dimension of the project (e.g. pricing coherence), not a single data point within it (e.g. one leaf of pricing). Flooring at leaf level would make a missing VAN collapse the entire Market score — too aggressive and non-explainable.

### No single overall score

The five composite scores are **not aggregated into one number**. The brief does not ask for one, and collapsing five dimensions destroys the explainability. The five scores are presented as a radar chart.

---

## Explainability Requirements

Brief §2.4.3 and §2.4.4 (Must): every score must include:

1. **Composite score** (0–10, one decimal)
2. **Sub-score breakdown** — each sub-score with weight and contribution
3. **Natural-language justification** — plain-language explanation of what drove the result (generated by LLM from sub-scores, not invented)
4. **Highest-leverage gap** — the sub-criterion with the largest improvement potential, paired with a concrete suggested action (brief §2.4.4, Should)
5. **Anomaly flags** — contradictions in the profile

### Anomaly & Inconsistency Detection

Brief §2.4.4 (Should): "at least 2 demonstrated cases of contradictory or unsubstantiated signals flagged."

| Case | Anomaly | Detection logic |
|---|---|---|
| Case 1 | Selling below cost | `selling_price < unit_cost` → `gross_margin_percentage < 0` → floor penalty on Market AND Commercial |
| Case 2 | Claims scalability but linear costs | `manual_dependency_level = "high"` AND `fixed_ratio < 0.3` (variable-cost-heavy) |
| Case 3 | Premium pricing, no differentiation | `price_vs_local_market > 1.3` AND `differentiation_claimed = False` |
| Case 4 | Project never breaks even | `monthly_profit <= 0` → `breakeven_months = null` → flag on Market |
| Case 5 | VAN negative over 5 years | `van_5_years < 0` → project destroys value at current numbers |
| Case 6 | Needs credit but ineligible | `needs_credit = True` AND `credit_eligibility_path = "none"` → financial readiness blocked |
| Case 7 | Debt overload | `repayment_capacity_ratio > 0.40` → more than 40% of profit goes to repayment |
| Case 8 | No operating runway | `opex_months_covered < 3` AND `has_paying_customers = False` → can't survive to first sale |
| Case 9 | Claims positive environmental impact with no evidence | `environmental_impact_type = "positive"` + no `sdg_alignment` + no `resource_efficiency_measures` |

---

## Score Evolution

Brief §2.4.4 (Should): "profile update triggers score recalculation with change highlighted."

When the profile is updated, all five scores recompute. The system tracks:

- **Previous scores** (in the append-only log)
- **Current scores** (freshly computed, appended)
- **Delta per sub-criterion** — which inputs changed and how they affected the score

Mon Parcours reads the full log chronologically to display score progression over time.

---

## Scoring Output Format

Each engine appends to the log:

```json
{
  "author": "market_scoring",
  "timestamp": "2026-06-18T15:42:05Z",
  "output": {
    "dimension": "Market",
    "composite_score": 5.8,
    "floor_penalty_applied": false,
    "sub_scores": [
      {"name": "Addressable market size", "score": 7, "weight": 0.20, "contribution": 1.40,
       "evidence": "geographic_scope=national, sector=agri-food"},
      {"name": "Competitive landscape", "score": 6, "weight": 0.15, "contribution": 0.90,
       "evidence": "competitor_count=3, differentiation_claimed=true"},
      {"name": "Customer validation", "score": 4, "weight": 0.25, "contribution": 1.00,
       "evidence": "customer_interview_count=3, pilot_users=0, has_validated_problem=true"},
      {"name": "Market share", "score": 7.0, "weight": 0.35, "contribution": 2.45,
       "components": [
         {"name": "addressable_market_size", "score": 9, "weight": 0.571, "contribution": 5.14, "evidence": "geographic_scope=national"},
         {"name": "competitive_landscape",   "score": 4, "weight": 0.429, "contribution": 1.72, "evidence": "competitor_count=3, differentiation_claimed=true"}
       ]},
      {"name": "Revenue model viability", "score": 6.0, "weight": 0.20, "contribution": 1.20,
       "components": [
         {"name": "paying_customers",     "score": 10, "weight": 0.30, "contribution": 3.0, "evidence": "has_paying_customers=true"},
         {"name": "margin_health",        "score": 10, "weight": 0.30, "contribution": 3.0, "evidence": "gross_margin_percentage=0.58"},
         {"name": "van_positive",         "score": 10, "weight": 0.20, "contribution": 2.0, "evidence": "van_5_years=45230"},
         {"name": "breakeven_under_24mo", "score":  0, "weight": 0.20, "contribution": 0.0, "evidence": "breakeven_months=null", "none": true}
       ]},
      {"name": "Financial readiness", "score": 5.0, "weight": 0.20, "contribution": 1.00,
       "components": [
         {"name": "opex_financing",      "score": 10, "weight": 0.30, "contribution": 3.0, "evidence": "has_opex_financing=true"},
         {"name": "opex_runway",         "score":  5, "weight": 0.20, "contribution": 1.0, "evidence": "opex_months_covered=4"},
         {"name": "credit_path",         "score":  7, "weight": 0.30, "contribution": 2.1, "evidence": "credit_eligibility_path=bts_fonapra"},
         {"name": "repayment_capacity",  "score":  5, "weight": 0.20, "contribution": 1.0, "evidence": "repayment_capacity_ratio=null", "none": true}
       ]}
    ],
    "none_fields": ["revenue_model_viability.breakeven_under_24mo", "financial_readiness.repayment_capacity"],
    "justification_fr": "Le projet cible un marché national avec une concurrence modérée. La marge unitaire est saine (58%) et le projet devient rentable en 14 mois avec une VAN positive. Le financement d'exploitation est couvert pour 4 mois. Éligible au crédit BTS/FONAPRA. La validation client reste le point faible — seulement 3 entretiens.",
    "highest_leverage_gap": {
      "sub_criterion": "Customer validation",
      "leaf": null,
      "current": 4, "weight": 0.25,
      "suggested_action_fr": "Mener 10+ entretiens clients structurés et lancer un pilote payant avec au moins 5 utilisateurs."
    },
    "anomalies": []
  }
}
```

### Dashboard render depth (two audiences)

- **Default (entrepreneur view):** radar chart (5 composites) + level-1 sub-score panel with contribution bars. The `components` array is not shown by default.
- **Expand-on-demand (judge/explainability view):** clicking a sub-score panel that has a `components` key reveals the leaf breakdown. This satisfies §2.4.5 ("Technical Depth") without overwhelming the non-technical entrepreneur.
- **The full tree is always present in the log/JSON** regardless of UI depth. Mon Parcours delta tracking diffs at leaf level — the "highest-leverage gap" can now say "your margin is thin" instead of just "Revenue model viability is weak."

When `highest_leverage_gap` points to a nested sub-criterion, `leaf` identifies the specific leaf that is lowest-scoring within that parent. When the gap is a flat sub-criterion, `leaf` is `null`.

---

## What the Scoring Engines Do NOT Do

- **Do not classify maturity stage** — that is Feature 1, already completed before scoring runs
- **Do not talk to each other** — cross-score analysis is the Gap Analyzer's job
- **Do not query the KB** — they identify what's weak; the roadmap decides what to do
- **Do not use the LLM for scoring decisions** — the LLM preprocesses raw answers before scoring and generates the justification after scoring; the score computation itself is deterministic
- **Do not overwrite** — append-only log

---

## Connection to Downstream Engines

- **→ Gap Analyzer:** Receives all 5 composite scores, sub-scores, anomalies, and `none_fields`. Merges with diagnostic blockers into a unified weakness profile.
- **→ Roadmap Engine (via Gap Analyzer):** Low sub-scores and their domains drive KB retrieval — a low Green score triggers SDG-aligned programme retrieval.
- **→ Explainable Report:** The dashboard renders scores as a radar chart with expandable sub-score panels.
- **→ Grounded Assistant:** Score breakdowns and justifications are injected into the assistant's context so it can explain scores without re-computing.

---

## Evaluation Protocol

Brief §2.4.4 (Should): "scoring consistency or inter-rater agreement measured on a test set."

**Metric:** Scoring consistency — given the same profile data, does the system produce the same scores every time? (Determinism check.) Plus: inter-rater comparison — do the scores align with human expert assessment on a small set?

**Test set:** 5–10 synthetic profiles with team-assigned "expected" scores per dimension.

**Protocol:**
1. Run all 5 scoring engines on each test profile
2. Verify determinism: run twice, confirm identical output
3. Compare composite scores to team-assigned expected scores
4. Report mean absolute error per dimension
5. Document any dimension where the system and the team disagree by > 2 points, with analysis of why

---

## Acceptance Criteria Checklist (from brief §2.4.4)

| Criterion | Priority | How LeadIt addresses it |
|---|---|---|
| Five composite scores implemented | Must | Market, Commercial, Innovation, Scalability, Green — all computed and displayed |
| Sub-scores are explicit | Must | Each composite decomposes into 3–4 sub-dimensions with visible contributions |
| Criteria weights are documented | Must | Weights per sub-criterion with written justification (this document) |
| Natural-language justification | Must | LLM-generated from sub-scores, in French |
| Anomaly detection works | Should | 9 demonstrated cases including financial anomalies (selling below cost, VAN negative, debt overload, no runway) |
| Improvement guidance is specific | Should | Highest-leverage gap per score with concrete action |
| Score evolution tracked | Should | Append-only log; Mon Parcours shows progression |
| Evaluation protocol | Should | Scoring consistency + inter-rater comparison on test set |
