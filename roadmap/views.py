"""
roadmap/views.py

Django wiring for Feature 3. Connects the roadmap engine and grounded assistant
to the existing `roadmap` app (already in INSTALLED_APPS).

Endpoints
---------
POST /roadmap/generate/<project_id>/
    Runs diagnose → score → gap analysis → retrieval → roadmap synthesis,
    appends the result to the project's ProfileLog, returns the roadmap JSON.

POST /roadmap/assistant/<project_id>/
    Grounded conversation. Loads the latest roadmap log entry, builds the
    Sonnet grounding context, forwards the user's message turns.

Notes
-----
- The retriever is built once at module load (KB indexed in memory). For a
  Qdrant-backed deployment, swap KBRetriever's store and persist the index.
- Diagnostic + scoring are imported from the existing Feature 1/2 modules.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from projects.models import ProjectProfile, ProfileLog

from diagnostic.services import diagnose_project
from diagnostic.scoring import score_project

from .retrieval import KBRetriever
from .engine import RoadmapEngine
from .llm import RoadmapLLM
from .assistant import GroundedAssistant, build_assistant_context

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Singletons (built once; KB indexed in memory)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_retriever() -> KBRetriever:
    kb_path = getattr(settings, "ROADMAP_KB_PATH",
                      os.path.join(os.path.dirname(__file__), "kb", "sample_kb.json"))
    embedder_pref = getattr(settings, "ROADMAP_EMBEDDER", "auto")  # "auto"|"bge"|"hashing"
    from .embeddings import get_embedding_backend
    retriever = KBRetriever.from_file(kb_path, embedder=get_embedding_backend(embedder_pref))
    retriever.index()
    return retriever


@lru_cache(maxsize=1)
def _get_engine() -> RoadmapEngine:
    model = getattr(settings, "ROADMAP_RAG_MODEL", "claude-opus-4-8")
    api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
    return RoadmapEngine(_get_retriever(), llm=RoadmapLLM(model=model, api_key=api_key))


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def generate_roadmap(request, project_id: int):
    try:
        profile = ProjectProfile.objects.get(pk=project_id)
    except ProjectProfile.DoesNotExist:
        raise Http404("Project not found")

    try:
        # Feature 1 + 2 (these append their own logs)
        diagnosis_result = diagnose_project(profile)
        diagnosis = diagnosis_result["metadata"]
        scoring = score_project(profile)

        # Feature 3
        engine = _get_engine()
        result = engine.generate(profile, diagnosis, scoring)
    except Exception as exc:
        logger.exception("generate_roadmap failure")
        return JsonResponse(
            {"error": f"roadmap generation failed: {exc.__class__.__name__}: {exc}"},
            status=500,
        )

    # Append to the project's immutable log (author='roadmap')
    try:
        ProfileLog.objects.create(
            project=profile,
            author="roadmap",
            output_type="roadmap_result",
            metadata=result["output"],
        )
    except Exception:
        logger.exception("roadmap log write failure")

    # Persist the clean, self-contained snapshot on the profile. The grounded
    # presenter reads its whole context from here (no ProfileLog query, no
    # re-running scoring per chat turn); future roadmap animations consume it too.
    snapshot = {
        "diagnostic":   diagnosis,            # diagnose_project(...)["metadata"]
        "scores":       scoring["scores"],    # score_project(...)["scores"]
        "roadmap":      result["output"],     # engine output (already clean JSON)
        "generated_at": result["timestamp"],
    }
    try:
        profile.roadmap = snapshot
        profile.save(update_fields=["roadmap", "updated_at"])
    except Exception:
        logger.exception("roadmap snapshot save failure")

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
@require_POST
def assistant(request, project_id: int):
    try:
        profile = ProjectProfile.objects.get(pk=project_id)
    except ProjectProfile.DoesNotExist:
        raise Http404("Project not found")

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("invalid JSON body")

    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return HttpResponseBadRequest("messages required: [{role, content}, ...]")

    # Ground the assistant from the self-contained snapshot saved at generate time.
    # No ProfileLog query, no re-running diagnosis/scoring on every chat turn.
    snap = profile.roadmap or {}
    if not snap.get("roadmap"):
        return HttpResponseBadRequest("generate a roadmap before using the assistant")

    context = build_assistant_context(
        snap.get("diagnostic", {}),
        {"scores": snap.get("scores", {})},
        snap["roadmap"],
    )
    assistant_client = GroundedAssistant(
        context, api_key=getattr(settings, "ANTHROPIC_API_KEY", None),
    )
    try:
        reply = assistant_client.ask(messages)
    except Exception as exc:
        logger.exception("roadmap assistant failure")
        return JsonResponse(
            {"error": f"roadmap assistant failed: {exc.__class__.__name__}: {exc}"},
            status=500,
        )
    return JsonResponse(reply, json_dumps_params={"ensure_ascii": False})
