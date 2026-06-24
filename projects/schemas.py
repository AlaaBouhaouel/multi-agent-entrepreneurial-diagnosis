"""
projects/schemas.py

Canonical field registry for the LeadIt shared project profile.

Every field the system reads — from criteria, scorers, diagnostic engine,
gap analyzer, or roadmap engine — must be declared here. The ProjectProfile
Django model stores profile data as a JSONB blob (metadata); this Pydantic
model validates that blob at write time so field-name and type drift is
caught immediately rather than silently producing wrong scores.

This registry holds exactly the 48 analysis-bearing fields: each one is read
by the maturity classifier, a scoring engine, a derived metric, or the roadmap
eligibility filter. Identity fields (gérant / associés / enterprise name) and
pure-data fields that fed no analysis were removed.

Usage:
    from projects.schemas import ProjectProfileData

    data = ProjectProfileData(**raw_dict)          # validates + coerces
    profile.metadata = data.model_dump()           # store to DB
    data = ProjectProfileData(**profile.metadata)  # read from DB
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ProjectProfileData(BaseModel):
    """
    Shared project profile — single source of truth for all engines.

    All fields are optional (None = not yet collected).
    extra="forbid" ensures unknown field names raise ValidationError immediately.
    """

    model_config = ConfigDict(extra="forbid")

    # ── Self-Assessment ────────────────────────────────────────────────────
    # Integer 1–6 only; intake must convert stage name before writing.
    self_assessed_stage: Optional[int] = None  # 1=Ideation … 6=Growth

    @field_validator("self_assessed_stage")
    @classmethod
    def _stage_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in range(1, 7):
            raise ValueError(f"self_assessed_stage must be 1–6, got {v}")
        return v

    # ── Founder & Team ─────────────────────────────────────────────────────

    founder_has_prior_experience: Optional[bool]      = None  # Classifier: Stage 2
    founder_has_required_skills:  Optional[bool]      = None  # Classifier: Stage 2/3
    team_core_complete:           Optional[bool]      = None  # Classifier: Stage 2/3
    prior_accompaniment:          Optional[List[str]] = None  # Roadmap eligibility

    # ── Legal & Administrative ─────────────────────────────────────────────

    legal_form_status:  Optional[str]  = None  # none | in_progress | registered
    legal_form_type:    Optional[str]  = None  # SARL, SUARL, SA, etc. (roadmap eligibility)
    rne_registered:     Optional[bool] = None  # Registered in RNE (Classifier: Stage 4)
    startup_label:      Optional[bool] = None  # Startup Act label (roadmap eligibility)

    # ── Market & Validation ────────────────────────────────────────────────

    target_customer_defined:   Optional[bool]      = None  # Classifier: Stage 2
    geographic_scope:          Optional[str]       = None  # local | regional | national | international
    validation_type:           Optional[List[str]] = None  # interview | pilot | pre_order | survey
    customer_interview_count:  Optional[int]       = None  # Classifier: Stage 2 (min 1)
    pilot_users:               Optional[int]       = None  # Classifier: Stage 2 (min 1)
    pre_orders:                Optional[int]       = None  # Classifier: Stage 2 (min 1)
    differentiation_claimed:   Optional[bool]      = None  # Classifier: Stage 2

    # ── Innovation ─────────────────────────────────────────────────────────

    idea_is_new:               Optional[bool] = None  # Classifier: Stage 2 (market_context_assessed)
    foreign_model_studied:     Optional[bool] = None  # Classifier: Stage 2 (market_context_assessed)
    business_model_documented: Optional[bool] = None  # Classifier: Stage 3

    # ── Financial Inputs (raw inputs used to compute metrics) ──────────────
    # These feed scorers/economics.py, scorers/projections.py, scorers/financing.py.

    selling_price:             Optional[float] = None  # Price per unit (TND)
    unit_cost:                 Optional[float] = None  # Direct cost per unit (TND)
    expected_monthly_units:    Optional[int]   = None  # Projected monthly sales volume
    monthly_revenue:           Optional[float] = None  # Current monthly revenue (TND)
    personnel_monthly_cost:    Optional[float] = None  # Monthly payroll total (TND)
    rent_monthly:              Optional[float] = None  # Monthly rent (TND)
    other_fixed_costs_monthly: Optional[float] = None  # Other fixed overhead (TND)
    initial_investment:        Optional[float] = None  # Total capex at launch (TND)
    cogs_percentage:           Optional[float] = None  # COGS as fraction of revenue (0.0–1.0)
    market_price_local:        Optional[float] = None  # Local competitor benchmark price (TND)
    market_price_foreign:      Optional[float] = None  # Foreign equivalent benchmark price (TND)

    # ── Financial State ────────────────────────────────────────────────────

    has_paying_customers:     Optional[bool]  = None  # Classifier: Stage 4
    revenue_recurring_months: Optional[int]   = None  # Classifier: Stage 6 (min 3)
    financial_docs_exist:     Optional[bool]  = None  # Classifier: Stage 4
    funding_secured:          Optional[bool]  = None  # Classifier: Stage 5
    self_financing_confirmed: Optional[bool]  = None  # Classifier: Stage 5

    # ── Credit & Financing ─────────────────────────────────────────────────

    needs_credit:                Optional[bool]      = None
    credit_amount_needed:        Optional[float]     = None  # (TND)
    has_guarantee:               Optional[bool]      = None  # Collateral available
    has_premises:                Optional[bool]      = None  # Physical premises confirmed
    apport_personnel:            Optional[float]     = None  # Personal equity contribution (TND)
    annual_debt_service:         Optional[float]     = None  # Annual loan repayment (TND)
    has_opex_financing:          Optional[bool]      = None
    credit_eligibility_blockers: Optional[List[str]] = None  # e.g. ["fichage_bct"]

    # ── Distribution & Operations ──────────────────────────────────────────

    distribution_channel_tested: Optional[bool] = None  # Classifier: Stage 5
    client_base_beyond_pilot:    Optional[bool] = None  # Classifier: Stage 6

    # ── Sustainability & Green ─────────────────────────────────────────────

    environmental_impact_type:        Optional[str]       = None
    environmental_impact_description: Optional[str]       = None
    sdg_alignment:                    Optional[List[str]] = None  # SDG numbers as strings: ["7", "12"]
