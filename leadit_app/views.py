import json
import os
import sys

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import logout

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Maps analysis['scores'] keys → ENGINES choices in models.py
_SCORE_AUTHOR = {
    'market':      'market',
    'commercial':  'commercial',
    'innovation':  'innovation',
    'scalability': 'scaling',   # ENGINES uses 'scaling', not 'scalability'
    'green':       'green',
}

_anthropic_client = None


def _resolve_anthropic_api_key():
    """
    Resolve Anthropic key from common env var names.
    Returns a stripped key or None.
    """
    for env_name in ('API_KEY_CLAUDE', 'ANTHROPIC_API_KEY', 'API_KEY'):
        value = os.getenv(env_name)
        if value:
            cleaned = value.strip().strip('"').strip("'")
            if cleaned:
                return cleaned
    return None


def _get_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        api_key = _resolve_anthropic_api_key()
        if not api_key:
            raise RuntimeError(
                'Anthropic API key missing. Set API_KEY_CLAUDE or ANTHROPIC_API_KEY in your .env file.'
            )
        _anthropic_client = Anthropic(api_key=api_key)
    return _anthropic_client


def call_llm(messages):
    client = _get_client()
    system = ''
    chat = []
    for m in messages:
        if m['role'] == 'system':
            system = m['content']
        else:
            chat.append(m)
    resp = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        system=system,
        messages=chat,
    )
    return resp.content[0].text


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _validated_metadata(profile: dict) -> dict:
    """
    Run profile through ProjectProfileData to catch type errors.
    Falls back to a simple None-filtered copy if validation fails.
    """
    try:
        from projects.schemas import ProjectProfileData
        from pydantic import ValidationError
        try:
            return ProjectProfileData(**profile).model_dump(exclude_none=True)
        except ValidationError:
            pass
    except ImportError:
        pass
    return {k: v for k, v in profile.items() if v is not None}


def _upsert_profile(session, profile: dict):
    """
    Create or update the ProjectProfile row for this session.
    Called on every turn that extracts something so partial profiles are always saved.
    Stores the project DB id in session to avoid duplicates.
    """
    from projects.models import ProjectProfile

    metadata = _validated_metadata(profile)
    sas = profile.get('self_assessed_stage')
    valid_sas = sas if isinstance(sas, int) and 1 <= sas <= 6 else None

    project_id = session.get('project_db_id')
    if project_id:
        try:
            p = ProjectProfile.objects.get(id=project_id)
            p.metadata = metadata
            if valid_sas is not None:
                p.self_assessed_stage = valid_sas
            p.save(update_fields=['metadata', 'self_assessed_stage', 'updated_at'])
            return p
        except ProjectProfile.DoesNotExist:
            pass

    # First time — create the row
    p = ProjectProfile.objects.create(
        lang_preference='fr',
        self_assessed_stage=valid_sas,
        metadata=metadata,
    )
    session['project_db_id'] = p.id
    return p


def _write_analysis_logs(project, analysis: dict) -> None:
    """Append one ProfileLog per engine run (diagnostic + 5 scorers)."""
    from projects.models import ProfileLog

    ProfileLog.objects.create(
        project=project,
        author='diagnostic',
        output_type='diagnosis_result',
        metadata={
            'assigned_stage':  analysis['assigned_stage'],
            'stopped_at':      analysis['stopped_at'],
            'confidence':      analysis['confidence'],
            'perception_gap':  analysis['perception_gap'],
            'blockers':        analysis['blockers'],
        },
    )

    for dim, result in analysis['scores'].items():
        ProfileLog.objects.create(
            project=project,
            author=_SCORE_AUTHOR.get(dim, dim),
            output_type=f'score.{dim}',
            metadata=result,
        )


def _analysis_payload_for_frontend(analysis: dict, presentation: str = "", roadmap_data=None,
                                   project_id=None) -> dict:
    def _score_payload(res: dict) -> dict:
        leaves_in = res.get('leaves') or []
        leaves_out = []
        total_weight = 0.0
        scored_weight = 0.0
        weighted_sum = 0.0

        for leaf in leaves_in:
            weight = float(leaf.get('weight') or 0.0)
            score = leaf.get('score')
            total_weight += weight
            if score is not None:
                s = float(score)
                scored_weight += weight
                weighted_sum += s * weight
            leaves_out.append({
                'criterion': leaf.get('criterion'),
                'label': leaf.get('label_fr'),
                'weight': weight,
                'score': score,
            })

        weighted_score = None if scored_weight == 0 else round(weighted_sum / scored_weight, 2)
        floor = res.get('floor')
        return {
            'score': res.get('score'),
            'floor': floor,
            'floor_met': res.get('floor_met'),
            'leaves': leaves_out,
            'calc': {
                'weighted_sum': round(weighted_sum, 4),
                'scored_weight': round(scored_weight, 4),
                'total_weight': round(total_weight, 4),
                'weighted_score': weighted_score,
                'floor_delta': None if (weighted_score is None or floor is None) else round(weighted_score - float(floor), 2),
            },
        }

    scores_out = {
        dim: _score_payload(res)
        for dim, res in analysis.get('scores', {}).items()
    }
    metrics_in = analysis.get('metrics', {})
    return {
        'presentation':   presentation,
        'project_id':     project_id,
        'assigned_stage': analysis.get('assigned_stage'),
        'stopped_at':     analysis.get('stopped_at'),
        'confidence':     analysis.get('confidence'),
        'perception_gap': analysis.get('perception_gap'),
        'blockers':       analysis.get('blockers', {}).get('ranked_domains', []),
        'scores':         scores_out,
        'roadmap':        roadmap_data,
        'metrics': {
            k: v for k, v in metrics_in.items()
            if k in ('gross_margin_percentage', 'monthly_profit', 'breakeven_months',
                     'van_5_years', 'credit_eligibility_path', 'opex_months_covered')
        },
    }


def _first_assistant_message(messages) -> str:
    if not isinstance(messages, list):
        return ""
    for msg in messages:
        if isinstance(msg, dict) and msg.get('role') == 'assistant' and msg.get('content'):
            return str(msg['content'])
    return ""


# ── Session helpers ────────────────────────────────────────────────────────────

def _save_engine(session, engine):
    session['intake_project_name']     = engine.state.project_name
    session['intake_profile']          = engine.state.profile
    session['intake_field_states']     = engine.state.field_states
    session['intake_estimated_stage']  = engine.state.estimated_stage
    session['intake_history']          = engine.state.history
    session['intake_contradictions']   = engine.state.contradictions
    session['intake_current_question'] = engine.state.current_question


def _restore_engine(session):
    from intake import IntakeEngine
    from intake.field_metadata import FIELD_META
    from intake.planner import PENDING

    project_name    = session.get('intake_project_name', 'Projet')
    profile         = session.get('intake_profile', {})
    field_states    = session.get('intake_field_states', {f: PENDING for f in FIELD_META})
    estimated_stage = session.get('intake_estimated_stage', 3)
    history         = session.get('intake_history', [])
    contradictions  = session.get('intake_contradictions', [])

    current_question = session.get('intake_current_question')

    engine = IntakeEngine(project_name=project_name, call_llm=call_llm)
    engine.state.profile          = profile
    engine.state.field_states     = field_states
    engine.state.estimated_stage  = estimated_stage
    engine.state.history          = history
    engine.state.contradictions   = contradictions
    engine.state.current_question = current_question
    return engine


# ── Views ──────────────────────────────────────────────────────────────────────

@ensure_csrf_cookie
def index(request):
    intake_history = request.session.get('intake_history', [])
    intake_profile = request.session.get('intake_profile', {})
    project_name = request.session.get('intake_project_name', 'Nouveau diagnostic')
    analysis = request.session.get('analysis_result')
    analyst_history = request.session.get('analyst_history', [])

    stats = None
    if request.session.get('intake_field_states') is not None:
        try:
            stats = _restore_engine(request.session)._stats()
        except Exception:
            stats = None

    analysis_payload = None
    roadmap_data = None
    project_id = request.session.get('project_db_id')
    if project_id:
        try:
            from projects.models import ProjectProfile
            p = ProjectProfile.objects.get(id=project_id)
            snap = p.roadmap or {}
            roadmap_data = snap.get('roadmap') if isinstance(snap, dict) else None
        except Exception:
            roadmap_data = None
    if analysis:
        analysis_payload = _analysis_payload_for_frontend(
            analysis,
            presentation=_first_assistant_message(analyst_history),
            roadmap_data=roadmap_data,
            project_id=project_id,
        )

    bootstrap_data = {
        'project_name': project_name,
        'intake_history': intake_history,
        'intake_profile': intake_profile,
        'stats': stats,
        'analysis': analysis_payload,
    }
    return render(request, 'index.html', {'bootstrap_data': bootstrap_data})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return render(request, 'registration/logged_out.html')
    return render(request, 'registration/logout.html')


def logged_out(request):
    return render(request, 'registration/logged_out.html')


@require_POST
def session_start(request):
    data = json.loads(request.body)
    project_name = (data.get('project_name') or 'Projet').strip() or 'Projet'

    from intake import IntakeEngine
    from projects.models import ProjectProfile

    try:
        engine = IntakeEngine(project_name=project_name, call_llm=call_llm)
        question = engine.start()
    except Exception as exc:
        message = str(exc)
        auth_error = (
            'authentication method' in message.lower()
            or 'api key' in message.lower()
            or 'auth_token' in message.lower()
        )
        if auth_error:
            return JsonResponse(
                {
                    'error': 'llm_auth_missing',
                    'detail': (
                        'Anthropic authentication is not configured. '
                        'Set API_KEY_CLAUDE or ANTHROPIC_API_KEY in .env and restart the server.'
                    ),
                },
                status=503,
            )
        raise

    _save_engine(request.session, engine)
    request.session['analysis_result'] = None
    request.session['analyst_history'] = []

    # Create the DB row immediately — even an abandoned session has a record.
    p = ProjectProfile.objects.create(
        lang_preference='fr',
        metadata={},
    )
    request.session['project_db_id'] = p.id

    return JsonResponse({'question': question, 'stats': engine._stats()})


@require_POST
def session_message(request):
    data = json.loads(request.body)
    message = (data.get('message') or '').strip()
    if not message:
        return JsonResponse({'error': 'empty'}, status=400)

    engine = _restore_engine(request.session)
    try:
        result = engine.respond(message)
    except Exception as exc:
        message_text = str(exc)
        auth_error = (
            'authentication method' in message_text.lower()
            or 'api key' in message_text.lower()
            or 'auth_token' in message_text.lower()
        )
        if auth_error:
            return JsonResponse(
                {
                    'error': 'llm_auth_missing',
                    'detail': (
                        'Anthropic authentication is not configured. '
                        'Set API_KEY_CLAUDE or ANTHROPIC_API_KEY in .env and restart the server.'
                    ),
                },
                status=503,
            )
        raise
    _save_engine(request.session, engine)

    # Persist to DB on every turn that learned something new.
    if result.extracted or result.explicitly_unknown:
        try:
            _upsert_profile(request.session, engine.state.profile)
        except Exception:
            pass  # DB write failure must never break the interview

    return JsonResponse({
        'question':           result.question,
        'extracted':          result.extracted,
        'explicitly_unknown': result.explicitly_unknown,
        'is_done':            result.is_done,
        'stats':              result.stats,
    })


@require_POST
def analysis_start(request):
    profile = request.session.get('intake_profile', {})
    if not profile:
        return JsonResponse({'error': 'no profile'}, status=400)

    from intake.analyst import run_analysis, AnalystSession

    try:
        analysis = run_analysis(profile)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    analyst = AnalystSession(
        profile,
        analysis,
        call_llm,
        project_name=request.session.get('intake_project_name', 'Projet'),
    )
    presentation = analyst.present()

    request.session['analysis_result'] = analysis
    request.session['analyst_history'] = analyst._history

    roadmap_data = None
    # Persist final profile state + write all engine logs.
    try:
        project = _upsert_profile(request.session, profile)
        _write_analysis_logs(project, analysis)
        snap = project.roadmap or {}
        if isinstance(snap, dict):
            roadmap_data = snap.get('roadmap')
    except Exception:
        pass  # DB failure must not break the response

    return JsonResponse(_analysis_payload_for_frontend(
        analysis,
        presentation=presentation,
        roadmap_data=roadmap_data,
        project_id=request.session.get('project_db_id'),
    ))


@require_POST
def analysis_ask(request):
    data = json.loads(request.body)
    question = (data.get('question') or '').strip()
    if not question:
        return JsonResponse({'error': 'empty'}, status=400)

    profile  = request.session.get('intake_profile', {})
    analysis = request.session.get('analysis_result')
    if not analysis:
        return JsonResponse({'error': 'no analysis'}, status=400)

    from intake.analyst import AnalystSession
    analyst = AnalystSession(
        profile,
        analysis,
        call_llm,
        project_name=request.session.get('intake_project_name', 'Projet'),
    )
    analyst._history = request.session.get('analyst_history', [])

    answer = analyst.ask(question)
    request.session['analyst_history'] = analyst._history

    return JsonResponse({'answer': answer})
