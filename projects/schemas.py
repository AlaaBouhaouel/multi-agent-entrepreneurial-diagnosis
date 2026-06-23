"""
projects/schemas.py

Canonical field registry for the LeadIt shared project profile.

Every field the system reads — from criteria, scorers, diagnostic engine,
gap analyzer, or roadmap engine — must be declared here. The ProjectProfile
Django model stores profile data as a JSONB blob (metadata); this Pydantic
model validates that blob at write time so field-name and type drift is
caught immediately rather than silently producing wrong scores.

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
    # Never used for classification or scoring — only for gap detection.
    # Integer 1–6 only; intake must convert stage name before writing.

    self_assessed_stage:      Optional[int]       = None  # 1=Ideation … 6=Growth
    self_assessed_readiness:  Optional[str]       = None
    self_assessed_strengths:  Optional[List[str]] = None
    self_assessed_weaknesses: Optional[List[str]] = None

    @field_validator("self_assessed_stage")
    @classmethod
    def _stage_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in range(1, 7):
            raise ValueError(f"self_assessed_stage must be 1–6, got {v}")
        return v

    # ── Founder & Team ─────────────────────────────────────────────────────

    gerant:                      Optional[str]       = None  # Name of the managing director
    founder_count:               Optional[int]       = None
    founder_has_prior_experience: Optional[bool]     = None  # Classifier: Stage 2
    founder_has_required_skills:  Optional[bool]     = None  # Classifier: Stage 2/3
    associes:                    Optional[List[str]] = None  # Names of co-founders
    team_size:                   Optional[int]       = None
    team_core_complete:          Optional[bool]      = None  # Classifier: Stage 2/3
    team_roles:                  Optional[List[str]] = None
    prior_accompaniment:         Optional[List[str]] = None  # Programs already attended

    # ── Legal & Administrative ─────────────────────────────────────────────

    legal_form_status:  Optional[str]  = None  # none | in_progress | registered
    legal_form_type:    Optional[str]  = None  # SARL, SUARL, SA, etc.
    registration_date:  Optional[str]  = None  # ISO date string
    rne_registered:     Optional[bool] = None  # Registered in RNE (Classifier: Stage 4)
    startup_label:      Optional[bool] = None  # Startup Act label obtained

    # ── Market & Validation ────────────────────────────────────────────────

    target_customer_defined:   Optional[bool]      = None  # Classifier: Stage 2
    geographic_scope:          Optional[str]       = None  # local | regional | national | international
    has_validated_problem:     Optional[bool]      = None  # Summary flag set by intake
    validation_type:           Optional[List[str]] = None  # interview | pilot | pre_order | survey
    customer_interview_count:  Optional[int]       = None  # Classifier: Stage 2 (min 1)
    pilot_users:               Optional[int]       = None  # Classifier: Stage 2 (min 1)
    pre_orders:                Optional[int]       = None  # Classifier: Stage 2 (min 1)
    target_market_size:        Optional[str]       = None
    competitor_count:          Optional[int]       = None
    differentiation_claimed:   Optional[bool]      = None  # Classifier: Stage 2
    differentiation_description: Optional[str]    = None
    local_competitors:         Optional[List[str]] = None

    # ── Innovation ─────────────────────────────────────────────────────────

    idea_is_new:              Optional[bool] = None  # Classifier: Stage 2 (market_context_assessed)
    foreign_model_studied:    Optional[bool] = None  # Classifier: Stage 2 (market_context_assessed)
    business_model_documented: Optional[bool] = None  # Classifier: Stage 3

    # ── Product & Offer ────────────────────────────────────────────────────

    product_stage:           Optional[str] = None  # concept | prototype | mvp | production
    demo_available:          Optional[bool] = None
    value_proposition_text:  Optional[str] = None
    value_prop_clarity_rating: Optional[int] = None  # 1–5, set by intake LLM rubric
    pricing_model:           Optional[str] = None
    pricing_tested:          Optional[bool] = None
    pricing_documented:      Optional[bool] = None

    # ── Financial Inputs (raw inputs used to compute metrics) ──────────────
    # These feed scorers/economics.py, scorers/projections.py, scorers/financing.py.
    # Engines never receive raw text — only these structured values.

    selling_price:             Optional[float] = None  # Price per unit (TND)
    unit_cost:                 Optional[float] = None  # Direct cost per unit (TND)
    expected_monthly_units:    Optional[int]   = None  # Projected monthly sales volume
    monthly_revenue:           Optional[float] = None  # Current monthly revenue (TND)
    personnel_monthly_cost:    Optional[float] = None  # Monthly payroll total (TND)
    rent_monthly:              Optional[float] = None  # Monthly rent (TND)
    other_fixed_costs_monthly: Optional[float] = None  # Other fixed overhead (TND)
    fixed_costs_monthly:       Optional[float] = None  # Direct fixed cost input (alternative to the three above)
    initial_investment:        Optional[float] = None  # Total capex at launch (TND)
    equipment_investment:      Optional[float] = None  # Equipment portion of capex (TND)
    equipment_lifespan_years:  Optional[int]   = None  # For depreciation calculation
    ca_growth_rate:            Optional[float] = None  # Monthly revenue growth rate (0.0–1.0)
    cogs_percentage:           Optional[float] = None  # COGS as fraction of revenue (0.0–1.0)
    tfse_percentage:           Optional[float] = None  # Social charges rate — Tunisia-specific
    tax_rate:                  Optional[float] = None  # Corporate tax rate (0.0–1.0)
    market_price_local:        Optional[float] = None  # Local competitor benchmark price (TND)
    market_price_foreign:      Optional[float] = None  # Foreign equivalent benchmark price (TND)

    # ── Financial State ────────────────────────────────────────────────────

    has_paying_customers:    Optional[bool]  = None  # Classifier: Stage 4
    revenue_model_type:      Optional[str]   = None  # subscription | transactional | freemium | B2B
    revenue_recurring_months: Optional[int]  = None  # Classifier: Stage 6 (min 3)
    financial_docs_exist:    Optional[bool]  = None  # Classifier: Stage 4
    funding_secured:         Optional[bool]  = None  # Classifier: Stage 5
    funding_amount:          Optional[float] = None  # External financing amount (TND)
    funding_source:          Optional[str]   = None  # bank | VC | grant | family | etc.
    self_financing_confirmed: Optional[bool] = None  # Classifier: Stage 5
    cost_structure_type:     Optional[str]   = None  # fixed_heavy | variable_heavy | mixed
    marginal_cost_estimate:  Optional[str]   = None

    # ── Credit & Financing ─────────────────────────────────────────────────

    needs_credit:                    Optional[bool]      = None
    credit_amount_needed:            Optional[float]     = None  # (TND)
    credit_duration_years:           Optional[int]       = None
    has_guarantee:                   Optional[bool]      = None  # Collateral available
    has_premises:                    Optional[bool]      = None  # Physical premises confirmed
    apport_personnel:                Optional[float]     = None  # Personal equity contribution (TND)
    opex_months_covered:             Optional[int]       = None  # Months of operating costs covered
    has_opex_financing:              Optional[bool]      = None
    annual_cash_flow:                Optional[float]     = None  # (TND)
    annual_debt_service:             Optional[float]     = None  # Annual loan repayment (TND)
    existing_credit_monthly_payment: Optional[float]     = None  # (TND)
    credit_eligibility_blockers:     Optional[List[str]] = None  # e.g. ["fichage_bct"]

    # ── Distribution & Operations ──────────────────────────────────────────

    distribution_channel_tested: Optional[bool]      = None  # Classifier: Stage 5
    distribution_channels:       Optional[List[str]] = None
    delivery_model:              Optional[str]       = None
    manual_dependency_level:     Optional[str]       = None  # low | medium | high
    automation_level:            Optional[str]       = None  # none | partial | high
    standardised_process:        Optional[bool]      = None
    client_base_beyond_pilot:    Optional[bool]      = None  # Classifier: Stage 6

    # ── Technology ─────────────────────────────────────────────────────────

    tech_stack_described:  Optional[bool] = None
    tech_is_core_to_offer: Optional[bool] = None
    ip_protected:          Optional[bool] = None
    proprietary_data:      Optional[bool] = None
    network_effects:       Optional[bool] = None

    # ── Sustainability & Green ─────────────────────────────────────────────
    # environmental_impact_type values: économie_énergie | réduction_déchets | eau | biodiversité | aucun

    environmental_impact_type:        Optional[str]       = None
    environmental_impact_description: Optional[str]       = None
    carbon_reduction_claimed:         Optional[bool]      = None
    waste_reduction_measures:         Optional[str]       = None  # Description of waste practices
    energy_reduction_measures:        Optional[str]       = None  # Description of energy practices
    water_reduction_measures:         Optional[str]       = None  # Description of water practices
    resource_efficiency_measures:     Optional[str]       = None  # Description of resource efficiency
    circular_practices_described:     Optional[str]       = None  # Description (string, not bool)
    sdg_alignment:                    Optional[List[str]] = None  # SDG numbers as strings: ["7", "12"]
    sdg_evidence:                     Optional[str]       = None

    # ── Scalability ────────────────────────────────────────────────────────

    replicability_evidence:  Optional[str]  = None
    multi_segment_potential: Optional[bool] = None
    language_adaptability:   Optional[bool] = None
    team_size_vs_customers:  Optional[str]  = None
