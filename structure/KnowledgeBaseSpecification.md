# Knowledge Base Specification

## Purpose

The Knowledge Base (KB) is the source of truth for all Tunisian entrepreneurial support resources used by the roadmap engine.

It enables:

* Personalized recommendations
* Eligibility filtering
* Source-grounded retrieval
* Explainable roadmap generation

The KB is not a chatbot memory. It is a structured database of real Tunisian programs, institutions, services, funding opportunities, incubators, accelerators, and administrative resources.

---

# Current Status

Current Dataset:

* 23 structured resources
* Funding programs
* Administrative services
* Support organizations
* Incubators & accelerators
* Entrepreneurial ecosystem actors

Target before final submission:

* 30+ verified resources
* 100% source coverage
* Eligibility metadata for all entries
* Traceable recommendations

---

# Resource Schema

Each KB entry must follow the same structure.

| Field           | Description                              |
| --------------- | ---------------------------------------- |
| resource_id     | Unique identifier                        |
| name            | Resource name                            |
| provider        | Organization providing it                |
| category        | Funding, incubation, legal, export, etc. |
| description     | Short summary                            |
| source_url      | Official source                          |
| stage_tags      | Compatible maturity stages               |
| blocker_domains | Problems it helps solve                  |
| eligibility     | Human-readable requirements              |
| benefits        | What the entrepreneur receives           |
| trust_level     | official / ecosystem / international     |
| status          | active / expired / unknown               |

---

# Stage Tags

Resources must be tagged with one or more stages.

Possible values:

* ideation
* validation
* structuration
* fundraising
* launch_planning
* growth

Example:

```json
{
  "stage_tags": [
    "validation",
    "structuration"
  ]
}
```

---

# Blocker Domains

Resources must be mapped to the weaknesses they solve.

Possible values:

* financier
* légal
* marché
* organisationnel
* technique
* green

Examples:

| Resource              | Blocker Domain |
| --------------------- | -------------- |
| BTS                   | financier      |
| BFPME                 | financier      |
| Startup Label         | légal          |
| CEPEX                 | marché         |
| Technopole            | technique      |
| Green Support Program | green          |

---

# Trust Levels

Used for ranking.

official

* Government institutions
* Public agencies
* Official programs

ecosystem

* Incubators
* Accelerators
* Associations

international

* UNDP
* GIZ
* World Bank
* International initiatives

---

# Retrieval Pipeline

The roadmap engine never performs pure semantic search.

Retrieval order:

1. Read diagnosed stage
2. Read scores
3. Read blocker domains
4. Apply eligibility filters
5. Query Qdrant
6. Rank results
7. Generate roadmap

Pipeline:

Project Profile
+
Diagnosis
+
Scores
↓
Eligibility Filter
↓
Qdrant Retrieval
↓
Roadmap

---

# Recommendation Ranking

Resources are ranked using:

* Stage compatibility
* Blocker-domain match
* Eligibility match
* Sector relevance
* Trust level
* Semantic similarity

---

# Recommendation Output

Each recommendation must contain:

```json
{
  "resource_id": "startup_label",
  "title": "Obtain Startup Label",
  "why_this_matches": "Legal blocker at Structuration stage",
  "priority": "high",
  "source_url": "...",
  "timeline": "immediate"
}
```

---

# Traceability Rules

Every recommendation must include:

* resource_id
* source_url
* provider
* explanation

No recommendation may be generated without a KB source.

If no KB source exists, the roadmap engine must return:

"Resource not found in knowledge base."

---

# Roadmap Integration

Diagnostic Engine
↓
Scoring Engines
↓
Unified Assessment Layer
↓
Knowledge Base Retrieval
↓
Roadmap Generation

The KB is the bridge between assessment and action.

Without the KB, the system can identify problems but cannot recommend solutions.

---

# Acceptance Criteria

The KB is considered complete when:

* 30+ resources exist
* Every resource has a source URL
* Every resource has stage tags
* Every resource has blocker domains
* Every resource has a trust level
* Every recommendation is traceable
* Retrieval works with eligibility filtering

---

# One-Sentence Summary

The Knowledge Base is a structured, source-grounded repository of Tunisian entrepreneurial resources that powers personalized and explainable roadmap generation.
