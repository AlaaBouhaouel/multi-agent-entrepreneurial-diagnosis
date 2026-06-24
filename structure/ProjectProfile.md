# Project Profile and Pipeline

Current, code-verified notes.

Last verified: 2026-06-24

## Data Models

Source: `projects/models.py`

## `ProjectProfile`

- `id`
- `sector` (optional)
- `lang_preference` (`fr`/`ar`)
- `self_assessed_stage` (optional)
- `metadata` (JSON profile payload)
- `roadmap` (JSON snapshot from roadmap generation)
- `created_at`, `updated_at`

## `ProfileLog`

Append-only engine outputs:

- `project` FK
- `author` (`intake`, `diagnostic`, `market`, `commercial`, `innovation`, `scaling`, `green`, `unifier`, `roadmap`, `assistant`)
- `timestamp`
- `output_type`
- `metadata` (JSON)

`__str__` is valid and currently returns:

`Project #<id> - <author> (<output_type>)`

## Pipeline Overview

1. Intake session starts (`/api/session/start/`) and stores working state in Django session.
2. Intake turns (`/api/session/message/`) update extracted profile fields.
3. Analysis (`/api/analysis/start/`) runs:
   - stage diagnosis
   - scoring
   - analyst presentation text
4. Analysis response returns structured payload used by `templates/index.html`.
5. Logs are persisted via `ProfileLog`.
6. Roadmap flow is separate (`/roadmap/generate/<project_id>/`) and stores a self-contained snapshot on `ProjectProfile.roadmap`.

## Session State Used by `leadit_app/views.py`

Common keys:

- `intake_profile`
- `intake_history`
- `intake_field_states`
- `intake_estimated_stage`
- `intake_current_question`
- `project_db_id`
- `analysis_result`
- `analyst_history`

## Frontend Bootstrap Contract

`index()` injects `bootstrap_data` into `templates/index.html` with:

- project/session intake state
- latest analysis payload (if available)
- roadmap payload (if available from `ProjectProfile.roadmap`)

## Roadmap Snapshot Shape (Stored on ProjectProfile)

From `roadmap/views.py` generate endpoint:

- `diagnostic`
- `scores`
- `roadmap`
- `generated_at`

This snapshot is reused by the roadmap assistant endpoint.
