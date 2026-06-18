# Maturity Taxonomy

## Purpose

The maturity taxonomy classifies an entrepreneurial project into one of six ordered stages based on factual, verifiable criteria. It answers the question **"where is this project in its lifecycle?"** — not how strong or healthy the project is (that is the scoring engine's job).

Classification is evidence-linked: every stage assignment traces back to specific data points collected from the entrepreneur's profile. No stage is assigned by intuition, self-report alone, or LLM inference.

---

## The Six Stages

Stages are ordered chronologically. A project sits at the **highest stage whose criteria all pass**. If a project satisfies Growth criteria but fails a Structuration criterion, it is classified at the stage just before the first failure — the system does not skip gaps.

| # | Stage          | What it means      |     Entry condition                           |
|---|----------------|--------------|--------------------------------------------------------|
| 1 | **Ideation** | Idea exists; problem articulated; no external validation yet | Default — no criteria required |
| 2 | **Market Validation** | Evidence that the problem resonates with real users | Proof of problem validation |
| 3 | **Structuration** | The project is taking organisational and legal shape | Business model + team + legal form |
| 4 | **Fundraising** | A validated, registered enterprise preparing to raise or reinvest | Paying customers + financial docs + legal registration |
| 5 | **Launch Planning** | Financing secured; distribution being tested in real conditions | Funding confirmed + distribution channel tested |
| 6 | **Growth** | Repeatable revenue; scaling beyond manual effort and pilot users | Recurring revenue (3+ months) + client base beyond pilot |

---

## Criteria per Stage

Each criterion is a factual check against the project profile. It returns one of three values:

| Return | Meaning | Implication |
|---|---|---|
| `True` | Criterion satisfied | Evidence present, checkpoint passed |
| `False` | Criterion not satisfied | A real, identified gap — the project has not reached this milestone |
| `None` | Data missing | The system cannot determine the answer — uncertainty is surfaced, not hidden as failure |

The three-way return is a deliberate design choice. Treating missing data as `False` would penalise incomplete profiles. Treating it as `True` would mask real gaps. `None` forces the system to be honest about what it doesn't know.

### Stage 1 — Ideation

No criteria. Every project enters here by default. The diagnostic engine's job is to determine how far beyond Ideation the evidence supports.

### Stage 2 — Market Validation

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Problem validation evidence | `has_validated_problem` | At least one form of external validation: customer interviews, pre-orders, letter of intent, pilot usage, or survey results | marché |

One criterion, but it must reflect real external contact — not the founder's belief that the problem exists.

### Stage 3 — Structuration

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Business model documented | `business_model_documented` | A written business model canvas, pricing grid, or equivalent — not a verbal description | organisationnel |
| Core team sufficient | `team_core_complete` OR `founder_has_required_skills` | Either the key roles are covered by the team, or the founder can credibly cover the missing roles | organisationnel |
| Legal form initiated | `legal_form_status` | Status is `in_progress` or `registered` — the entrepreneur has begun or completed legal incorporation | légal |

All three must pass. A project with a strong team but no documented business model stays at Market Validation.

### Stage 4 — Fundraising

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Paying customers | `has_paying_customers` | Real transactions — not letters of intent, verbal commitments, or free-tier usage | financier |
| Financial documents exist | `financial_docs_exist` | A financial forecast, pitch deck with projections, or accounting records | financier |
| Legal form registered | `legal_form_status` | Status is `registered` — the enterprise is legally constituted | légal |

This is where the perception gap is sharpest. Founders frequently self-assess as "financing-ready" while missing one or more of these criteria — particularly `has_paying_customers`. The system must not accept self-reported revenue claims without evidence.

### Stage 5 — Launch Planning

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Funding secured | `funding_secured` OR `self_financing_confirmed` | External financing obtained or sufficient self-financing confirmed — either path satisfies this | financier |
| Distribution channel tested | `distribution_channel_tested` | At least one channel (retail, online, B2B direct, distributor) tested in real market conditions — not a plan or simulation | marché |

### Stage 6 — Growth

| Criterion | Profile field | Logic | Domain |
|---|---|---|---|
| Recurring revenue | `revenue_recurring_months` | Revenue recorded in at least 3 consecutive months — not a single spike | financier |
| Client base beyond pilot | `client_base_beyond_pilot` | Customers extend beyond the initial pilot group, early adopters, or personal network | marché |

---

## Classification Algorithm

```
function classify(profile):
    assigned_stage = IDEATION
    evidence = {}
    
    for stage in [MARKET_VALIDATION, STRUCTURATION, FUNDRAISING, LAUNCH_PLANNING, GROWTH]:
        results = evaluate_criteria(stage, profile)
        evidence[stage] = results
        
        if all(r.value == True for r in results):
            assigned_stage = stage
        else:
            break  # stop at first stage with any failure or unknown
    
    return assigned_stage, evidence
```

The classifier walks the stages in order and stops at the first stage where any criterion is `False` or `None`. The assigned stage is the last stage where all criteria passed. The full evidence map is returned for explainability — the user and the system can see exactly which criteria passed, failed, or lacked data at every stage.

---

## Perception-Reality Gap Detection

The diagnostic engine's headline differentiator. The entrepreneur is asked for their **self-assessed stage** during intake. The system independently computes the **diagnosed stage** using the criteria above. If these diverge, the system:

1. Flags the gap explicitly (e.g. "You assessed yourself at Fundraising; the system classifies you at Structuration")
2. Identifies the **specific criteria** that caused the divergence (e.g. `business_model_documented = False`)
3. Tags each diverging criterion with its **blocker domain** (financier, légal, marché, organisationnel, technique)

This output feeds directly into the roadmap engine: the diverging criteria become the priority items for resource retrieval.

### Example

```
Self-assessed:  Stage 4 (Fundraising)
Diagnosed:      Stage 3 (Structuration)
Divergence:     1 stage gap

Failing criteria at Stage 4:
  - has_paying_customers = False  [financier]
    → No evidence of real transactions provided
  - financial_docs_exist = None   [financier]
    → Data not collected; flagged for follow-up

Blocker summary:
  - Primary domain: financier (2 criteria)
  - Action: surface financing-readiness resources from KB
```

---

## Blocker Identification

Each failed or unknown criterion carries a `category` tag (its blocker domain). The diagnostic engine aggregates these into a **blocker profile**:

| Domain | What it covers |
|---|---|
| `financier` | Revenue, funding, financial documentation, pricing |
| `légal` | Legal form, registration, regulatory compliance |
| `marché` | Market validation, customer base, distribution |
| `organisationnel` | Team, business model, processes, governance |
| `technique` | Product/technology readiness, technical infrastructure |

Blockers are ranked by how many criteria they affect and at which stage they appear. A blocker at Stage 3 is more fundamental than one at Stage 5 — it blocks all subsequent progress.

---

## Open Decisions

**None propagation rule:** When a criterion returns `None` at a stage above the current classification, the system must decide whether to:
- **Block** — treat `None` as a hard stop, classifying the project at the stage before the unknown (conservative; avoids false advancement)
- **Hold provisionally** — not used in MVP

The current implementation will use the **block** approach as the default, with a clear "missing data" indicator in the diagnostic output prompting the entrepreneur to provide the missing information.

**Confidence levels:** Not yet implemented. A future iteration could assign a confidence score to each stage classification based on the ratio of `True` to `None` results.

---

## Connection to Other Modules

- **→ Scoring Engine:** The diagnosed stage contextualises the scores. A high Innovation score at Ideation means something different than at Growth. The scoring engine receives the stage as input context.
- **→ Roadmap Engine:** Failed criteria and their blocker domains are the primary filter for KB retrieval. A `légal` blocker at Structuration triggers retrieval of legal-form and registration resources.
- **→ Shared Profile:** the diagnosis result is written back with evidence_sources so roadmap retrieval stays traceable.