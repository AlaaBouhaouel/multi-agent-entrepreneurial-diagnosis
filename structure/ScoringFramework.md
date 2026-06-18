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

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Addressable market size | 0.25 | Is the target market large enough? | `target_market_size`, `geographic_scope`, `sector` |
| Competitive landscape | 0.20 | How crowded is the space? | `competitor_count`, `differentiation_claimed`, `local_competitors` |
| Customer validation evidence | 0.30 | Has anyone confirmed demand? | `has_validated_problem`, `customer_interview_count`, `pilot_users`, `pre_orders` |
| Revenue model viability | 0.25 | Is the revenue model tested? | `revenue_model_type`, `has_paying_customers`, `pricing_tested`, `monthly_revenue` |

**Weight justification:** Customer validation weighted highest (0.30) because in the Tunisian early-stage context, market size estimates are unreliable — real validation evidence is the strongest signal.

### Commercial Offer Score

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Value proposition clarity | 0.30 | Can the founder articulate the offer? | `value_proposition_text`, `value_prop_clarity_rating` |
| Product/service readiness | 0.25 | Is the product functional? | `product_stage`, `demo_available` |
| Pricing strategy coherence | 0.20 | Is pricing documented and tested? | `pricing_tested`, `pricing_model`, `pricing_documented` |
| Offer-need alignment | 0.25 | Does the offer solve the validated problem? | Cross-reference: `value_proposition_text` vs `has_validated_problem` |

**Weight justification:** Value proposition clarity weighted highest (0.30) because in the MENA early-stage ecosystem, the gap between "the founder knows what they sell" and "a customer understands what they're buying" is where most commercial failures occur.

### Innovation Score

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Local novelty | 0.30 | Is this new to Tunisia/MENA? | `local_competitors`, `inspired_by_foreign_model`, `first_in_market_claimed` |
| Technology intensity | 0.25 | Is tech a structural advantage? | `tech_stack_described`, `tech_is_core_to_offer`, `automation_level` |
| Barrier to entry | 0.20 | How hard to replicate? | `ip_protected`, `proprietary_data`, `network_effects` |
| Departure from existing | 0.25 | Meaningfully different from alternatives? | `differentiation_description`, `comparison_to_alternatives` |

**Weight justification:** Local novelty weighted highest (0.30) because the brief is explicitly about the Tunisian context. Adapting a proven foreign model to Tunisia still carries innovation value.

### Scalability Score

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Replicability | 0.30 | Can it expand without rebuilding? | `delivery_model`, `standardised_process`, `replicability_evidence` |
| Manual dependency | 0.25 | Does growth require proportional effort? | `manual_dependency_level`, `automation_level`, `team_size_vs_customers` |
| Deployment cost structure | 0.20 | Do costs scale linearly? | `cost_structure_type`, `marginal_cost_estimate` |
| Addressable reach | 0.25 | Can it expand geographically? | `geographic_scope`, `multi_segment_potential`, `language_adaptability` |

**Weight justification:** Replicability weighted highest (0.30) because in Tunisia, many viable projects depend entirely on the founder's personal involvement — the definition of non-scalable.

### Green Score

| Sub-criterion | Weight | What it measures | Key profile fields |
|---|---|---|---|
| Environmental impact | 0.40 | Does it reduce environmental harm? | `environmental_impact_type`, `carbon_reduction_claimed` |
| SDG alignment | 0.30 | Maps to UN SDGs? | `sdg_alignment`, `sdg_evidence` |
| Resource efficiency | 0.20 | Minimises waste/energy/materials? | `resource_efficiency_measures` |
| Circular economy | 0.10 | Reuses, recycles, extends lifecycle? | `circular_practices_described`, `waste_reduction_measures` |

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

### Handling None (missing data)

If a profile field is `None`, the sub-criterion score is `None`. Its weight is redistributed proportionally across scored sub-criteria:

```python
scored = [(sub, score, weight) for sub, score, weight in criteria if score is not None]
total_weight = sum(w for _, _, w in scored)
composite = sum(s * (w / total_weight) for _, s, w in scored)
```

The output flags which sub-criteria were unscorable and why.

### Floor penalty (brief §2.4.5: "composite scores are not averages")

If any sub-criterion scores **below 2/10**, the composite is **capped at 4.0/10**. A fundamental weakness cannot be masked by strong sub-scores elsewhere.

```python
if any(sub.score < FLOOR_THRESHOLD for sub in scored):
    composite = min(composite, FLOOR_CAP)  # 4.0/10
```

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

| Case | Anomaly | Conflicting fields |
|---|---|---|
| Case 1 | Claims strong market traction but has no paying customers | `self_assessed_readiness` mentions "traction" + `has_paying_customers = False` |
| Case 2 | Claims high scalability but depends heavily on manual effort | `self_assessed_strengths` includes "scalable" + `manual_dependency_level = "high"` |
| Case 3 | Claims first-in-market but names local competitors | `first_in_market_claimed = True` + `local_competitors` list non-empty |
| Case 4 | Claims positive environmental impact with no evidence | `environmental_impact_type = "positive"` + no `sdg_alignment` + no `resource_efficiency_measures` |

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
    "composite_score": 5.2,
    "floor_penalty_applied": false,
    "sub_scores": [
      {"name": "Addressable market size", "score": 7, "weight": 0.25, "contribution": 1.75,
       "evidence": "geographic_scope=national"},
      {"name": "Competitive landscape", "score": 6, "weight": 0.20, "contribution": 1.20,
       "evidence": "competitor_count=3, differentiation_claimed=true"},
      {"name": "Customer validation", "score": 3, "weight": 0.30, "contribution": 0.90,
       "evidence": "customer_interview_count=3, pilot_users=0"},
      {"name": "Revenue model viability", "score": 5, "weight": 0.25, "contribution": 1.25,
       "evidence": "revenue_model_type=subscription, pricing_tested=false"}
    ],
    "none_fields": [],
    "justification_fr": "Le projet cible un marché national avec une concurrence modérée, mais la validation client reste faible — seulement 3 entretiens. Le modèle de revenus est documenté mais non testé.",
    "highest_leverage_gap": {
      "sub_criterion": "Customer validation",
      "current": 3, "weight": 0.30,
      "suggested_action_fr": "Mener 10+ entretiens clients structurés et lancer un pilote payant."
    },
    "anomalies": [
      {"type": "contradiction",
       "description": "Claims traction but has_paying_customers=false",
       "fields": ["self_assessed_readiness", "has_paying_customers"]}
    ],
    "evidence_sources": ["profile_field:has_validated_problem", "doc:interview_notes_01"]
  } 
}
```

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
| Anomaly detection works | Should | 4 demonstrated contradiction cases |
| Improvement guidance is specific | Should | Highest-leverage gap per score with concrete action |
| Score evolution tracked | Should | Append-only log; Mon Parcours shows progression |
| Evaluation protocol | Should | Scoring consistency + inter-rater comparison on test set |
