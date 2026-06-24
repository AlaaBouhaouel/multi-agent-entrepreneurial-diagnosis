# LeadIt

Current, code-verified project documentation for the LeadIt platform.

Last verified: 2026-06-24

## What LeadIt Does

LeadIt is a Django application for entrepreneurial diagnostics with three connected layers:

1. Intake interview (adaptive, LLM-assisted)
2. Deterministic diagnostic + scoring (rule and formula based)
3. Roadmap generation from a grounded knowledge base

The web app is server-rendered (`templates/index.html`) with JSON API endpoints used by the same page.

## Tech Stack

- Backend: Django 6.x
- Database: SQLite in dev (`db.sqlite3`), Postgres via `DATABASE_URL` in deployment
- Frontend: Django template + vanilla JS/CSS (`templates/index.html`)
- LLM provider: Anthropic (intake analyst + roadmap synthesis/assistant)
- Static serving in production: WhiteNoise

## Main Apps and Modules

- `leadit_app/`: web views, intake/analysis APIs, login/logout flow
- `projects/`: `ProjectProfile` + `ProfileLog` models
- `diagnostic/`: maturity classification and diagnostics
- `scorers/`: 5 scoring engines + financial helpers
- `intake/`: conversational intake engine + analyst presenter
- `roadmap/`: KB retrieval, gap analysis, roadmap generation, grounded assistant
- `criteria/`: stage criteria tree and shared evaluation helpers

## Current HTTP Endpoints

### UI/Auth

- `GET /` -> main app page
- `GET /login/`, `POST /logout/`, `GET /logged-out/`

### Intake + Analysis API

- `POST /api/session/start/`
- `POST /api/session/message/`
- `POST /api/analysis/start/`
- `POST /api/analysis/ask/`

### Roadmap API

- `POST /roadmap/generate/<project_id>/`
- `POST /roadmap/assistant/<project_id>/`

## Data Model Snapshot

### `ProjectProfile`

- `sector`
- `lang_preference` (`fr`/`ar`)
- `self_assessed_stage`
- `metadata` (JSON, canonical profile payload)
- `roadmap` (JSON snapshot: diagnostic/scores/roadmap/generated_at)
- timestamps

### `ProfileLog`

Append-only engine logs:

- `project` FK
- `author` (engine identity)
- `timestamp`
- `output_type` (e.g. `diagnosis_result`, `score.market`, `roadmap_result`)
- `metadata` JSON

## Deployment Notes

This repo is prepared for Railway deployment:

- `Procfile`
- `requirements.txt`
- `runtime.txt`
- env-driven `LeadIt/settings.py`

Required env vars (production):

- `SECRET_KEY`
- `DATABASE_URL`
- `DEBUG=False`
- Optional: `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- Optional for LLM features: `ANTHROPIC_API_KEY`

## Local Run

```bash
python manage.py migrate
python manage.py runserver
```

## Notes on Determinism

- Stage diagnosis and score computations are deterministic and code-driven.
- LLMs are used for conversational behavior/presentation and roadmap phrasing, not for numeric score computation.
