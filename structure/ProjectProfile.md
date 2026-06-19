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
  "metadata": { ... }
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
| `founder_name` | string | Intake (anonymised in outputs) |
| `sector` | string | Intake |
| `sub_sector` | string, optional | Intake |
| `geographic_location` | string | Intake |
| `language_preference` | `fr` \| `ar` | Intake |

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
| `founder_has_required_skills` | boolean \| null | **Diagnostic** (Stage 2 criterion — `domain_competence`, `any_true` with `team_core_complete`) |
| `founder_has_prior_experience` | boolean \| null | **Diagnostic** (Stage 2 criterion — `prior_professional_experience`) |
| `team_core_complete` | boolean \| null | **Diagnostic** (Stage 2 criterion — `domain_competence`) + **Diagnostic** (Stage 3 criterion) |
| `team_roles` | list[string], optional | Scoring context |
| `prior_accompaniment` | list[string], optional | Roadmap (avoid re-recommending completed programs) |

### Legal & Administrative

| Field | Type | Used by |
|---|---|---|
| `legal_form_status` | `none` \| `in_progress` \| `registered` \| null | `classifier`, `roadmap_eligibility` — **Diagnostic** (Stage 3 + 4 criteria) |
| `rne_registered` | boolean \| null | `classifier`, `roadmap_eligibility` — **Diagnostic** (Stage 4 — `rne_registered` criterion); confirms RNE registration; asked when `legal_form_status = registered` |
| `legal_form_type` | `personne_physique` \| `SARL` \| `SUARL` \| `SA` \| `SAS` \| `autre` \| null | `roadmap_eligibility`, `feasibility` — roadmap eligibility filter (some financing requires personne morale); asked when `legal_form_status ∈ {in_progress, registered}` |
| `associes` | list[{name, parts_sociales}], optional | `feasibility`, `scoring:scalability` — asked when `legal_form_type ∈ {SARL, SUARL, SA, SAS}`; coherence check: SARL ≥ 2, SUARL = 1 |
| `gerant` | string, optional | `feasibility`, `scoring:commercial` — asked when `legal_form_type ∈ {SARL, SUARL, SA, SAS}` |
| `needs_premises` | boolean \| null | branch gate only — triggers `has_premises` question |
| `has_premises` | boolean \| null | `roadmap_eligibility`, `feasibility` — `True` → eligible as fonds de commerce / garantie in credit path; `needs_premises = True & has_premises = False` → roadmap blocker |
| `registration_date` | date, optional | Scoring context |
| `startup_label` | boolean \| null | Roadmap (Startup Act eligibility) |

### Market & Validation

| Field | Type | Used by |
|---|---|---|
| `target_customer_defined` | boolean \| null | **Diagnostic** (Stage 2 — `target_customer_defined`) |
| `geographic_scope` | `local` \| `regional` \| `national` \| `international` \| null | **Diagnostic** (Stage 2 — `geographic_scope_defined`) + Scoring (Market, Scalability) |
| `idea_is_new` | boolean \| null | **Diagnostic** (Stage 2 — `market_context_assessed`, `any_true` with `foreign_model_studied`): True = original idea locally, False = adapted from foreign model |
| `foreign_model_studied` | boolean \| null | **Diagnostic** (Stage 2 — `market_context_assessed`, `any_true` with `idea_is_new`): True if founder studied the foreign equivalent |
| `differentiation_claimed` | boolean \| null | **Diagnostic** (Stage 2 — `differentiation_articulated`) + Scoring (Market, Innovation) |
| `differentiation_description` | string, optional | Scoring (Innovation — LLM rubric) |
| `has_validated_problem` | boolean \| null | Scoring (Market) — evidence quality signal (subsumed into `customers_validation` for diagnostic purposes) |
| `validation_type` | list[string], optional | **Diagnostic** (Stage 2 — `customers_validation`) + Scoring (Market — evidence quality) |
| `customer_interview_count` | integer, optional | **Diagnostic** (Stage 2 — `customers_validation`) + Scoring (Market) |
| `pilot_users` | integer, optional | **Diagnostic** (Stage 2 — `customers_validation`) + Scoring (Market) |
| `pre_orders` | integer, optional | **Diagnostic** (Stage 2 — `customers_validation`) + Scoring (Market) |
| `target_market_size` | string, optional | Scoring (Market — addressable size) |
| `competitor_count` | integer, optional | Scoring (Market, Innovation) |
| `local_competitors` | list[string], optional | Scoring (Innovation — novelty) |

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

### Financial — Unit Economics (asked during intake)

| Field | Type | Intake question (FR) | Used by |
|---|---|---|---|
| `unit_cost` | float, optional | "Combien vous coûte la production/livraison d'une unité ?" (DT) | **Computed** (margin, breakeven, VAN) |
| `selling_price` | float, optional | "À quel prix comptez-vous le vendre ?" (DT) | **Computed** + Scoring (Commercial — pricing) |
| `expected_monthly_units` | integer, optional | "Combien d'unités pensez-vous vendre par mois ?" | **Computed** (breakeven, cash flow) |
| `market_price_local` | float \| null | "Quel est le prix du même produit sur le marché tunisien ?" (null if doesn't exist locally) | Scoring (Commercial — price positioning) |
| `market_price_foreign` | float \| null | "Si le produit existe à l'étranger, quel est son prix ?" (DT equivalent, null if N/A) | Scoring (Innovation — foreign model adaptation) |

### Financial — Operating Expenses & Financing (asked during intake)

| Field | Type | Intake question (FR) | Used by |
|---|---|---|---|
| `fixed_costs_monthly` | float, optional | "Quels sont vos charges fixes mensuelles estimées ?" (loyer, salaires, eau, électricité) | **Computed** (breakeven, cash flow) |
| `initial_investment` | float, optional | "Quel est l'investissement initial nécessaire pour démarrer ?" (DT) | **Computed** (VAN, breakeven time) |
| `has_opex_financing` | boolean \| null | "Avez-vous déjà le financement pour couvrir vos charges d'exploitation ?" | **Diagnostic** (readiness) + Scoring (Market) |
| `opex_financing_source` | string, optional | "Si oui, d'où vient ce financement ?" (épargne, famille, revenus existants) | Roadmap context |
| `opex_months_covered` | integer, optional | "Pour combien de mois pouvez-vous couvrir vos charges sans revenus ?" | Scoring (Market — runway) |

### Financial — Credit Situation (asked during intake)

| Field | Type | Intake question (FR) | Used by |
|---|---|---|---|
| `has_existing_credit` | boolean \| null | "Avez-vous déjà un crédit en cours ?" | Scoring (Market) + Roadmap (eligibility filter) |
| `existing_credit_amount` | float, optional | "Si oui, quel est le montant restant ?" (DT) | **Computed** (debt load) |
| `existing_credit_monthly_payment` | float, optional | "Quelle est votre échéance mensuelle actuelle ?" (DT) | **Computed** (capacity) |
| `existing_credit_remaining_years` | integer, optional | "Combien d'années restent ?" | Context |
| `is_credit_eligible` | boolean \| null | Computed — see eligibility rules below | Roadmap (financing resource eligibility) |
| `credit_eligibility_path` | `commercial_bank` \| `bts_fonapra` \| `none` \| null | Computed — which path they qualify for | Roadmap (route to correct institution) |
| `credit_eligibility_blockers` | list[string], optional | "Si non éligible, pourquoi ?" (impayés, fichage BCT, pas de garanties) | Gap Analyzer (financial blockers) |
| `has_guarantee` | boolean \| null | "Avez-vous une garantie à proposer ?" (bien immobilier, terrain, caution) | **Computed** (credit path) |
| `guarantee_type` | string, optional | "Si oui, de quel type ?" (immobilier, terrain, caution personnelle, nantissement) | Roadmap context |
| `needs_credit` | boolean \| null | "Avez-vous besoin d'un crédit pour lancer/développer votre projet ?" | Roadmap (trigger financing resources) |
| `credit_amount_needed` | float, optional | "Si oui, quel montant estimez-vous nécessaire ?" (DT) | **Computed** (loan schedule) |
| `credit_duration_years` | integer, optional | "Sur combien d'années ?" | **Computed** (loan schedule) |
| `has_other_financing` | boolean \| null | "Avez-vous d'autres sources de financement ?" (associé, investisseur, subvention, famille) | **Diagnostic** (Stage 5) + Scoring |
| `other_financing_type` | string, optional | "Si oui, de quel type ?" | Roadmap context |
| `other_financing_amount` | float, optional | "Quel montant ?" (DT) | **Computed** (total financing) |

### Financial — Credit Eligibility Rules (Tunisian context)

The system computes `credit_eligibility_path` automatically from the intake fields. These are the real rules in Tunisia — not generic logic:

```python
def compute_credit_path(profile):
    # Step 1 — Basic eligibility (applies to all paths)
    if profile.has_existing_credit and profile.credit_eligibility_blockers:
        if "fichage_bct" in profile.credit_eligibility_blockers:
            return "none"  # Filed with BCT = no credit anywhere
        if "impayes" in profile.credit_eligibility_blockers:
            return "none"  # Unpaid debts = blocked

    # Step 2 — Commercial bank path (requires real guarantee)
    if profile.has_guarantee and profile.guarantee_type in [
        "immobilier", "terrain", "caution_personnelle", "nantissement"
    ]:
        return "commercial_bank"
        # → Route to BFPME, Amen Bank, BIAT, BNA, STB, etc.
        # → No ceiling on credit amount (bank-dependent)

    # Step 3 — BTS / FONAPRA path (no personal guarantee needed)
    # FONAPRA = specifically for young founders who lack startup financing
    # BTS accepts the fonds de commerce itself as guarantee
    # (BTS leases it — the entrepreneur operates it but BTS holds it)
    # Ceiling: 150,000 DT (FONAPRA only — other BTS products have different ceilings)
    if profile.needs_credit and not profile.has_guarantee:
        if profile.credit_amount_needed <= 150000:
            return "bts_fonapra"
            # → Route to BTS FONAPRA
            # → Target: young founders without startup capital
            # → Fonds de commerce as guarantee
            # → Credit ceiling: 150,000 DT
            # → Rate: concessional

        # Other BTS products (lower ceilings, different conditions):
        # - BTS microcrédit: up to 5,000 DT via AMCs (rate 5%)
        # - BTS interest-free line: up to 10,000 DT (0%, periodic editions)
        # - BTS mésofinance: above microcredit ceiling, for graduates/TPE
        # These are surfaced separately by the roadmap via KB entries

    # Step 4 — Needs credit but exceeds BTS ceiling and no guarantee
    if profile.needs_credit and profile.credit_amount_needed > 150000:
        if not profile.has_guarantee:
            return "none"
            # → Flag: needs > 150k but no guarantee
            # → Roadmap suggests: find a guarantor, explore SOTUGAR,
            #   reduce investment scope, or seek equity instead

    return "none"
```

**What this enables in the roadmap:**

| Credit path | Roadmap action |
|---|---|
| `commercial_bank` | Surface BFPME co-financing, commercial bank products, SOTUGAR guarantee |
| `bts_fonapra` | Surface BTS FONAPRA (up to 150k DT, fonds de commerce as guarantee, for young founders without startup capital). Also surface smaller BTS products: microcredit (5k DT), interest-free line (10k DT), mésofinance |
| `none` (fichage/impayés) | Surface alternatives: Startup Act bourse, grants, investor matching, family financing |
| `none` (>150k, no guarantee) | Flag the gap: "Your project needs > 150,000 DT but you have no guarantee — explore reducing scope, finding a guarantor, or seeking equity" |

### Financial — Revenue & History (asked during intake)

| Field | Type | Used by |
|---|---|---|
| `has_paying_customers` | boolean \| null | **Diagnostic** (Stage 4 criterion) + **Scoring** (Market) |
| `revenue_model_type` | string, optional | Scoring (Market) |
| `monthly_revenue` | float, optional | Scoring (Market) + **Computed** |
| `revenue_recurring_months` | integer, optional | **Diagnostic** (Stage 6 criterion) |
| `financial_docs_exist` | boolean \| null | **Diagnostic** (Stage 4 criterion) |
| `funding_secured` | boolean \| null | **Diagnostic** (Stage 5 criterion) |
| `funding_amount` | float, optional | Roadmap context |
| `funding_source` | string, optional | Roadmap context |
| `self_financing_confirmed` | boolean \| null | **Diagnostic** (Stage 5 criterion) |

### Financial — Charges & Amortissement (asked during intake)

These questions capture the full cost structure. The intake adapts: a project at Ideation with no equipment gets simpler questions; a project at Structuration+ gets the full breakdown.

| Field | Type | Intake question (FR) | Used by |
|---|---|---|---|
| `personnel_count` | integer, optional | "Combien d'employés prévoyez-vous (hors fondateurs) ?" | **Computed** (charges de personnel) |
| `personnel_monthly_cost` | float, optional | "Quel est le coût salarial mensuel total estimé ?" (DT, charges comprises) | **Computed** (F.Personnel) |
| `rent_monthly` | float, optional | "Quel est votre loyer mensuel (local, atelier, bureau) ?" (DT) | **Computed** (charges fixes) |
| `equipment_investment` | float, optional | "Quel est le coût total de l'équipement/matériel nécessaire ?" (DT) | **Computed** (amortissement) |
| `equipment_lifespan_years` | integer, optional | "Sur combien d'années cet équipement est-il utilisable ?" (durée d'amortissement) | **Computed** (dotation aux amortissements) |
| `other_fixed_costs_monthly` | float, optional | "Autres charges fixes mensuelles ?" (eau, électricité, assurance, internet) | **Computed** |
| `ca_growth_rate` | float, optional | "De combien pensez-vous augmenter vos ventes chaque année ?" (%, e.g. 0.05 = 5%) | **Computed** (projection CA) |
| `cogs_percentage` | float, optional | "Quel pourcentage du CA représentent vos achats/matières premières ?" (e.g. 0.62 = 62%) — if not provided, computed from `unit_cost / selling_price` | **Computed** |
| `tfse_percentage` | float, optional | "Quel pourcentage du CA pour les frais de services extérieurs ?" (default 5% if unknown) | **Computed** |
| `tax_rate` | float | Fixed at 0.15 (15% impôt sur les sociétés) or 0.25 for certain sectors — configurable | **Computed** |

### Financial — Revenue & History (asked during intake)

| Field | Type | Used by |
|---|---|---|
| `has_paying_customers` | boolean \| null | **Diagnostic** (Stage 4 criterion) + **Scoring** (Market) |
| `revenue_model_type` | string, optional | Scoring (Market) |
| `monthly_revenue` | float, optional | Scoring (Market) + **Computed** |
| `revenue_recurring_months` | integer, optional | **Diagnostic** (Stage 6 criterion) |
| `financial_docs_exist` | boolean \| null | **Diagnostic** (Stage 4 criterion) |
| `funding_secured` | boolean \| null | **Diagnostic** (Stage 5 criterion) |
| `funding_amount` | float, optional | Roadmap context |
| `funding_source` | string, optional | Roadmap context |
| `self_financing_confirmed` | boolean \| null | **Diagnostic** (Stage 5 criterion) |

---

### Financial Projections Engine — Compte d'Exploitation Prévisionnel

This is the core financial intelligence. The entrepreneur provides simple intake answers; the system generates a **full projected income statement** identical to what a Tunisian bank director uses to evaluate loan applications — over 5 years.

This works at ANY stage. An Ideation-stage founder provides estimates; a Growth-stage founder provides actuals. The system labels which inputs are estimates vs. confirmed.

#### Step 1 — Compute Year 1 baseline

```python
# Revenue
ca_year1 = selling_price * expected_monthly_units * 12
# or use monthly_revenue * 12 if the entrepreneur already has real revenue

# Charges d'exploitation
achats = ca_year1 * cogs_percentage                    # Achats (matières premières / COGS)
tfse = ca_year1 * tfse_percentage                      # Taxes, Frais, Services Extérieurs
f_personnel = personnel_monthly_cost * 12              # Frais de personnel (annual)
loyer = rent_monthly * 12                              # Loyer
autres_charges = other_fixed_costs_monthly * 12         # Autres charges fixes

total_charges = achats + tfse + f_personnel + loyer + autres_charges

# Résultat Brut d'Exploitation
rbe = ca_year1 - total_charges

# Amortissement
if equipment_investment and equipment_lifespan_years:
    dotation_amortissement = equipment_investment / equipment_lifespan_years
else:
    dotation_amortissement = 0

# Frais de financement (from loan schedule)
if needs_credit and credit_amount_needed:
    f_financement = loan_schedule[0]["interest"] + loan_schedule[0]["tva_on_interest"]
else:
    f_financement = 0

# Add existing credit costs
if has_existing_credit:
    f_financement += existing_credit_monthly_payment * 12

# Résultat Net d'Exploitation
rne = rbe - dotation_amortissement - f_financement

# Impôt
impot = max(0, rne * tax_rate)

# Résultat Net après Impôt
rne_apres_impot = rne - impot

# Cash Flow (résultat net + amortissement car non-décaissé)
cash_flow = rne_apres_impot + dotation_amortissement

# Tombées (annuités de crédit — principal + intérêts + TVA)
if needs_credit:
    tombees = loan_schedule[0]["total_annuity"]
else:
    tombees = 0
if has_existing_credit:
    tombees += existing_credit_monthly_payment * 12

# Ratios
rentabilite_commerciale = rne_apres_impot / ca_year1 if ca_year1 > 0 else 0
capacite_remboursement = tombees / cash_flow if cash_flow > 0 else None
```

#### Step 2 — Project over 5 years

```python
projection = []
ca = ca_year1

for year in range(1, 6):
    if year > 1:
        ca = ca * (1 + ca_growth_rate)

    achats = ca * cogs_percentage
    tfse = ca * tfse_percentage
    f_personnel_yr = f_personnel * (1 + 0.03) ** (year - 1)  # 3% annual salary increase
    loyer_yr = loyer * (1 + 0.02) ** (year - 1)               # 2% annual rent increase
    autres_yr = autres_charges * (1 + 0.02) ** (year - 1)

    total_charges_yr = achats + tfse + f_personnel_yr + loyer_yr + autres_yr
    rbe_yr = ca - total_charges_yr

    # Amortissement (stops when equipment is fully depreciated)
    amort_yr = dotation_amortissement if year <= equipment_lifespan_years else 0

    # Financing costs (decrease as principal is repaid)
    if needs_credit and year <= credit_duration_years:
        fin_yr = loan_schedule[year - 1]["interest"] + loan_schedule[year - 1]["tva_on_interest"]
    else:
        fin_yr = 0
    if has_existing_credit and year <= existing_credit_remaining_years:
        fin_yr += existing_credit_monthly_payment * 12

    rne_yr = rbe_yr - amort_yr - fin_yr
    impot_yr = max(0, rne_yr * tax_rate)
    rne_apres_impot_yr = rne_yr - impot_yr
    cash_flow_yr = rne_apres_impot_yr + amort_yr

    # Tombées for this year
    if needs_credit and year <= credit_duration_years:
        tombees_yr = loan_schedule[year - 1]["total_annuity"]
    else:
        tombees_yr = 0

    projection.append({
        "year": year,
        "ca": round(ca),
        "achats": round(achats),
        "tfse": round(tfse),
        "f_personnel": round(f_personnel_yr),
        "loyer": round(loyer_yr),
        "autres_charges": round(autres_yr),
        "total_charges": round(total_charges_yr),
        "rbe": round(rbe_yr),
        "amortissement": round(amort_yr),
        "f_financement": round(fin_yr),
        "rne": round(rne_yr),
        "impot": round(impot_yr),
        "rne_apres_impot": round(rne_apres_impot_yr),
        "cash_flow": round(cash_flow_yr),
        "cash_flow_cumule": sum(p["cash_flow"] for p in projection) + round(cash_flow_yr),
        "rentabilite_commerciale": round(rne_apres_impot_yr / ca, 4) if ca > 0 else 0,
        "tombees": round(tombees_yr),
        "capacite_remboursement": round(tombees_yr / cash_flow_yr, 4) if cash_flow_yr > 0 else None,
    })
```

#### Step 3 — Compute key indicators

```python
# Breakeven — units per month
breakeven_units = (f_personnel / 12 + rent_monthly + other_fixed_costs_monthly) / gross_margin_per_unit

# Breakeven — time (when does cumulative cash flow turn positive)
breakeven_year = None
for p in projection:
    if p["cash_flow_cumule"] >= initial_investment:
        breakeven_year = p["year"]
        break

# VAN over 5 years
discount_rate = 0.10
van = -initial_investment
for p in projection:
    van += p["cash_flow"] / (1 + discount_rate) ** p["year"]

# TRI (Taux de Rendement Interne) — the discount rate at which VAN = 0
# Computed via iteration or numpy.irr equivalent
```

#### Step 4 — Final Verdict

The system delivers a clear, professional assessment:

```python
verdict = {
    "viable": None,
    "message_fr": "",
    "warnings": [],
    "recommendation": ""
}

# Rule 1: Selling below cost = structurally impossible
if selling_price <= unit_cost:
    verdict["viable"] = False
    verdict["message_fr"] = "❌ Projet non viable : votre prix de vente est inférieur au coût de production. Chaque vente creuse votre déficit."
    verdict["recommendation"] = "Revoir votre structure de coûts ou votre prix de vente."

# Rule 2: Never profitable
elif all(p["rne_apres_impot"] <= 0 for p in projection):
    verdict["viable"] = False
    verdict["message_fr"] = "❌ Projet non viable : le résultat net reste négatif sur 5 ans. Le projet ne devient jamais rentable aux conditions actuelles."
    verdict["recommendation"] = "Réduire les charges fixes, augmenter le prix, ou augmenter le volume de ventes."

# Rule 3: Breakeven > 3 years = bank rejection risk
elif breakeven_year and breakeven_year > 3:
    verdict["viable"] = "risky"
    verdict["message_fr"] = f"⚠️ Rentabilité tardive : le projet ne devient rentable qu'en année {breakeven_year}. Une banque commerciale risque de rejeter le dossier — les banques exigent un retour en moins de 3 ans."
    verdict["warnings"].append("breakeven_too_late")
    verdict["recommendation"] = "Réduire l'investissement initial, accélérer la montée en charge, ou chercher un financement patient (investisseur, subvention)."

# Rule 4: VAN negative
elif van < 0:
    verdict["viable"] = "risky"
    verdict["message_fr"] = f"⚠️ VAN négative ({round(van):,} DT) : le projet détruit de la valeur sur 5 ans. Le rendement est inférieur au coût du capital."
    verdict["warnings"].append("van_negative")
    verdict["recommendation"] = "Améliorer la marge ou augmenter le volume pour rendre le projet créateur de valeur."

# Rule 5: Debt overload
elif any(p["capacite_remboursement"] and p["capacite_remboursement"] > 0.40 for p in projection[:3]):
    verdict["viable"] = "risky"
    verdict["message_fr"] = "⚠️ Endettement élevé : plus de 40% du cash flow est absorbé par les remboursements pendant les 3 premières années."
    verdict["warnings"].append("debt_overload")
    verdict["recommendation"] = "Réduire le montant emprunté, allonger la durée, ou négocier une période de grâce."

# Rule 6: Viable
else:
    verdict["viable"] = True
    verdict["message_fr"] = f"✅ Projet viable : rentable en année {breakeven_year or 1}, VAN positive ({round(van):,} DT), capacité de remboursement saine."
    verdict["recommendation"] = "Poursuivre avec le plan actuel. Voir la feuille de route pour les prochaines étapes."
```

#### What the entrepreneur sees (dashboard — Financial Projections section)

```
═══════════════════════════════════════════════════════
  COMPTE D'EXPLOITATION PRÉVISIONNEL — Projection 5 ans
═══════════════════════════════════════════════════════

                        An 1        An 2        An 3        An 4        An 5
Chiffre d'Affaires    240,000     252,000     264,600     277,830     291,722
─────────────────────────────────────────────────────────────────────────────
Achats (62%)          148,800     156,240     164,052     172,255     180,868
TFSE (5%)              12,000      12,600      13,230      13,892      14,586
F.Personnel            36,000      37,080      38,192      39,338      40,518
Loyer                  18,000      18,360      18,727      19,102      19,484
Autres charges          6,000       6,120       6,242       6,367       6,494
─────────────────────────────────────────────────────────────────────────────
Total Charges         220,800     230,400     240,443     250,953     261,950
RBE                    19,200      21,600      24,157      26,877      29,772
Amortissement           8,000       8,000       8,000       8,000       8,000
F.Financement           5,850       5,200       4,550       3,900       3,250
─────────────────────────────────────────────────────────────────────────────
RNE                     5,350       8,400      11,607      14,977      18,522
Impôt (15%)               803       1,260       1,741       2,247       2,778
RNE après impôt         4,548       7,140       9,866      12,730      15,744

Cash Flow              12,548      15,140      17,866      20,730      23,744
Cash Flow cumulé       12,548      27,688      45,554      66,284      90,028

Rentabilité com.        1.9%        2.8%        3.7%        4.6%        5.4%
Tombées (crédit)       15,850      15,200      14,550      13,900      13,250
Cap. remboursement     126.3%      100.4%       81.4%       67.1%       55.8%

═══════════════════════════════════════════════════════

💰 Marge par unité : 7.60 DT (38%)
📊 Seuil de rentabilité : 789 unités/mois (vous en prévoyez 1,000)
📅 Retour sur investissement : année 3
📈 VAN sur 5 ans : +18,430 DT (positif ✓)
🏦 Éligibilité crédit : BTS/FONAPRA

⚠️ ATTENTION : la capacité de remboursement dépasse 40% les 3 premières 
années. La banque commerciale risque de rejeter — envisager une période 
de grâce ou réduire le montant emprunté.
```

---

#### Loan Schedule (Échéancier de crédit)

When the entrepreneur needs credit (`needs_credit = True`), the system computes the full repayment schedule:

```python
principal = credit_amount_needed
duration_years = credit_duration_years
annual_rate = 0.065  # TMM + margin, configurable per source (BFPME, BTS, bank)
tva_on_interest = 0.04  # TVA on interest
grace_years = 0  # configurable — some BFPME credits have 2-year grace

annual_principal = principal / (duration_years - grace_years)
schedule = []

for year in range(1, duration_years + 1):
    outstanding = principal - (annual_principal * max(0, year - grace_years - 1))
    if year <= grace_years:
        # Grace period: pay interest only, no principal
        principal_payment = 0
        outstanding = principal
    else:
        principal_payment = annual_principal

    interest = outstanding * annual_rate
    tva = interest * tva_on_interest
    annuity = principal_payment + interest + tva
    monthly_payment = annuity / 12

    schedule.append({
        "year": year,
        "outstanding": round(outstanding, 2),
        "principal_payment": round(principal_payment, 2),
        "interest": round(interest, 2),
        "tva_on_interest": round(tva, 2),
        "total_annuity": round(annuity, 2),
        "monthly_payment": round(monthly_payment, 2),
        "grace": year <= grace_years
    })
```

#### Anomaly Detection from Computed Fields

| Anomaly | Detection | Flag |
|---|---|---|
| Selling below cost | `selling_price < unit_cost` | "❌ Prix de vente inférieur au coût — chaque vente creuse votre déficit" |
| Never profitable in 5 years | all `rne_apres_impot <= 0` | "❌ Le projet ne devient jamais rentable sur 5 ans" |
| Breakeven > 3 years | `breakeven_year > 3` | "⚠️ Rentabilité tardive — une banque commerciale risque de rejeter le dossier" |
| VAN negative | `van_5_years < 0` | "⚠️ Le projet détruit de la valeur sur 5 ans" |
| Debt overload years 1–3 | `capacite_remboursement > 0.40` in first 3 years | "⚠️ Plus de 40% du cash flow absorbé par les remboursements" |
| No operating runway | `opex_months_covered < 3` AND `has_paying_customers = False` | "⚠️ Moins de 3 mois de trésorerie sans revenus" |
| Premium sans différenciation | `price_vs_local_market > 1.3` AND `differentiation_claimed = False` | "⚠️ Prix 30%+ au-dessus du marché sans différenciation" |
| Credit ineligible | `needs_credit = True` AND `credit_eligibility_path = "none"` | "⚠️ Besoin de crédit mais non éligible" |
| Needs > 150k, no guarantee | `credit_amount_needed > 150000` AND `has_guarantee = False` | "⚠️ Dépasse le plafond FONAPRA et pas de garantie pour banque commerciale" |
| Has guarantee, doesn't know it | `has_guarantee = None` AND `legal_form_status = "registered"` | Prompt: "Avez-vous un bien pouvant servir de garantie ?" |

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
| provides unit_cost and selling_price | System computes margin, breakeven, VAN automatically — no questions needed | — |
| has_opex_financing = false | `needs_credit`, `credit_amount_needed`, `credit_duration_years` | `opex_financing_source` |
| needs_credit = true | `has_guarantee`, `guarantee_type`, `has_existing_credit` | — |
| has_guarantee = true | `guarantee_type` → route to `commercial_bank` path | BTS/FONAPRA questions |
| has_guarantee = false AND credit_amount_needed <= 150000 | Route to `bts_fonapra` path — explain FONAPRA (fonds de commerce as guarantee) | Commercial bank questions |
| has_guarantee = false AND credit_amount_needed > 150000 | Flag: no credit path available — probe `has_other_financing`, `other_financing_type` | — |
| has_existing_credit = true | `existing_credit_amount`, `existing_credit_monthly_payment`, `existing_credit_remaining_years` | — |
| has_other_financing = true | `other_financing_type`, `other_financing_amount` | — |

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
| Financial analysis | Computed fields | Unit margin, breakeven (units + months), VAN, price vs market, loan schedule, repayment capacity |
| Blockers & gaps | Gap analyzer | Ranked weakness list, domain severity, missing data prompts, credit eligibility path |
| Roadmap | Roadmap engine | Three-column timeline (immediate / short / medium), each action with KB source link |
| Anomalies | Scoring engines | Contradiction warnings (selling below cost, VAN negative, debt overload, etc.) |
| Mon Parcours | Full log | Historical progression view |

The Financial analysis section displays the computed metrics in plain French:
```
💰 Marge par unité : 7 DT (58%)
📊 Seuil de rentabilité : 143 unités/mois (vous en prévoyez 200 ✓)
📅 Retour sur investissement : ~14 mois
📈 Valeur du projet sur 5 ans (VAN) : +45,230 DT ✓
💲 Votre prix vs le marché : 12 DT vs 15 DT (-20%, compétitif)
🏦 Éligibilité crédit : BTS/FONAPRA (fonds de commerce comme garantie, plafond 150k DT)
📋 Échéance mensuelle estimée : 1,250 DT/mois sur 7 ans
⚖️ Capacité de remboursement : 28% du bénéfice (sain < 30%)
```

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
