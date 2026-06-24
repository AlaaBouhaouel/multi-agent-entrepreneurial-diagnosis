# Knowledge Base and Roadmap (Feature 3)

Current, code-verified notes.

Last verified: 2026-06-24

## Status

Feature 3 is implemented.

Primary modules:

- `roadmap/views.py`
- `roadmap/engine.py`
- `roadmap/retrieval.py`
- `roadmap/gap_analyzer.py`
- `roadmap/llm.py`
- `roadmap/assistant.py`
- `roadmap/kb/schema.py`

## KB Source

Configured in `LeadIt/settings.py`:

- `ROADMAP_KB_PATH = kb/KB_merged.json`

Retriever is initialized once and indexed (`roadmap/views.py` with `_get_retriever()` cache).

## Endpoints

### Generate roadmap

`POST /roadmap/generate/<project_id>/`

Flow:

1. `diagnose_project(profile)`
2. `score_project(profile)`
3. `RoadmapEngine.generate(profile, diagnosis, scoring)`
4. Persist roadmap output log (`ProfileLog` with `author="roadmap"`, `output_type="roadmap_result"`)
5. Persist roadmap snapshot to `ProjectProfile.roadmap`

### Grounded roadmap assistant

`POST /roadmap/assistant/<project_id>/`

- Reads previously saved `ProjectProfile.roadmap`
- Builds grounded context
- Answers with Sonnet-backed assistant (if API key is configured)

If roadmap snapshot is missing, endpoint returns bad request asking to generate roadmap first.

## Roadmap Engine Output

`RoadmapEngine.generate(...)` returns output including:

- assigned stage and stage tag
- confidence + perception gap context
- verdict summary
- `roadmap_by_horizon`
- `roadmap_flat`
- `matched_resources`
- `unmatched_gaps`
- ranked blocker domains
- missing data fields
- synthesis source (`llm` or deterministic `template` fallback)

## Grounding Guarantees (Current Design)

From implementation intent in `roadmap/engine.py` and `roadmap/llm.py`:

- actions are tied to retrieved resources
- unmatched gaps are reported explicitly
- roadmap synthesis has deterministic fallback when LLM path is unavailable

## Frontend Relationship

The main analysis UI in `templates/index.html` can display roadmap content when `roadmap` is present in the analysis/bootstrap payload.
