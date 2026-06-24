"""
intake/engine.py

Conversational intake orchestrator.

The engine drives a consultant-style interview: each turn makes one LLM call
that both extracts fields from the last answer AND generates the next
highest-value question. The LLM owns question selection — not a fixed list.

Usage
-----
    from intake import IntakeEngine

    def call_llm(messages): ...   # your Anthropic / OpenAI client

    engine = IntakeEngine(project_name="BioPackTN", call_llm=call_llm)
    print(engine.start())         # opening question

    while True:
        answer = input("> ")
        result = engine.respond(answer)
        if result.is_done:
            break
        print(result.question)

    profile = engine.get_profile()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .consultant import ConsultResult, consult
from .field_metadata import DERIVED_FIELDS, FIELD_META
from .planner import (
    ANSWERED,
    EXPLICITLY_UNKNOWN,
    PENDING,
    completion_stats,
    is_complete,
)


@dataclass
class IntakeState:
    project_name: str
    profile: Dict[str, Any] = field(default_factory=dict)
    field_states: Dict[str, str] = field(default_factory=lambda: {f: PENDING for f in FIELD_META})
    history: List[Dict[str, str]] = field(default_factory=list)
    estimated_stage: int = 3       # broadened until self_assessed_stage is known
    current_question: Optional[str] = None
    # Tracks fields whose value changed after first being answered.
    # Each entry: {"field": str, "old": any, "new": any}
    # Passed to consult() so the LLM can confirm with the founder.
    contradictions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TurnResult:
    question: Optional[str]           # next question to display (None if done)
    extracted: Dict[str, Any]         # fields extracted this turn
    explicitly_unknown: List[str]     # fields user said they don't know
    is_done: bool
    stats: Dict[str, int]             # {pending, answered, explicitly_unknown, skipped}


class IntakeEngine:

    def __init__(
        self,
        project_name: str,
        call_llm: Callable[[List[Dict[str, str]]], str],
        initial_profile: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._call_llm = call_llm
        self.state = IntakeState(project_name=project_name)

        if initial_profile:
            for k, v in initial_profile.items():
                if k in FIELD_META and v is not None:
                    self.state.profile[k] = v
                    self.state.field_states[k] = ANSWERED

        self._sync_estimated_stage()

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self) -> str:
        """Generate and return the opening question. Call once before the loop."""
        result = consult(
            project_name=self.state.project_name,
            profile=self.state.profile,
            field_states=self.state.field_states,
            estimated_stage=self.state.estimated_stage,
            conversation_history=[],
            last_user_message=None,
            call_llm=self._call_llm,
        )
        question = result.next_question or "حدثني عن مشروعك وفريقك؟ / Pouvez-vous me parler de votre projet et de votre équipe ?"
        self.state.current_question = question
        self.state.history.append({"role": "assistant", "content": question})
        return question

    def respond(self, user_message: str) -> TurnResult:
        """
        Process one founder answer. Returns the next question or is_done=True.
        Normally one LLM call per turn. A second call is made only when _apply()
        detects a contradiction, so the LLM can acknowledge it in the same turn.
        """
        self.state.history.append({"role": "user", "content": user_message})

        result = consult(
            project_name=self.state.project_name,
            profile=self.state.profile,
            field_states=self.state.field_states,
            estimated_stage=self.state.estimated_stage,
            conversation_history=self.state.history[:-1],
            last_user_message=user_message,
            call_llm=self._call_llm,
            contradictions=self.state.contradictions,
        )

        self._apply(result)

        # _apply() may have detected that this turn's extracted values conflict
        # with previously answered fields.  Re-run consult() with the contradiction
        # context so the LLM folds an acknowledgment into the very next question
        # rather than surfacing it one exchange too late.
        # Extractions are authoritative from the first call; only the question is replaced.
        if self.state.contradictions:
            followup = consult(
                project_name=self.state.project_name,
                profile=self.state.profile,
                field_states=self.state.field_states,
                estimated_stage=self.state.estimated_stage,
                conversation_history=self.state.history[:-1],
                last_user_message=user_message,
                call_llm=self._call_llm,
                contradictions=self.state.contradictions,
            )
            result = ConsultResult(
                extracted=result.extracted,
                explicitly_unknown=result.explicitly_unknown,
                meta_response=followup.meta_response,
                next_question=followup.next_question,
            )
            self.state.contradictions = []

        # Meta-question: user asked "why?" — explain then re-ask the same question.
        if result.meta_response:
            current_q = self.state.current_question or next(
                (m["content"] for m in reversed(self.state.history) if m["role"] == "assistant"),
                None,
            )
            combined = f"{result.meta_response}\n\n{current_q}" if current_q else result.meta_response
            self.state.history.append({"role": "assistant", "content": combined})
            return TurnResult(
                question=combined,
                extracted=result.extracted,
                explicitly_unknown=result.explicitly_unknown,
                is_done=False,
                stats=self._stats(),
            )

        if is_complete(self.state.field_states, self.state.profile, self.state.estimated_stage):
            return TurnResult(
                question=None,
                extracted=result.extracted,
                explicitly_unknown=result.explicitly_unknown,
                is_done=True,
                stats=self._stats(),
            )

        question = result.next_question
        if not question:
            # LLM failed to return a question — session is done or fallback needed.
            return TurnResult(
                question=None,
                extracted=result.extracted,
                explicitly_unknown=result.explicitly_unknown,
                is_done=True,
                stats=self._stats(),
            )

        self.state.current_question = question
        self.state.history.append({"role": "assistant", "content": question})

        return TurnResult(
            question=question,
            extracted=result.extracted,
            explicitly_unknown=result.explicitly_unknown,
            is_done=False,
            stats=self._stats(),
        )

    def get_profile(self) -> Dict[str, Any]:
        """Returns the current profile dict, ready for ProjectProfileData(**profile)."""
        return dict(self.state.profile)

    def get_history(self) -> List[Dict[str, str]]:
        return list(self.state.history)

    # ── Internal ───────────────────────────────────────────────────────────

    def _apply(self, result: ConsultResult) -> None:
        self.state.contradictions = []
        for field_name, value in result.extracted.items():
            old = self.state.profile.get(field_name)
            if old is not None and old != value:
                self.state.contradictions.append(
                    {"field": field_name, "old": old, "new": value}
                )
            self.state.profile[field_name] = value
            if field_name not in DERIVED_FIELDS:
                self.state.field_states[field_name] = ANSWERED

        for field_name in result.explicitly_unknown:
            meta = FIELD_META.get(field_name, {})
            if meta.get("can_be_explicitly_unknown", True):
                self.state.field_states[field_name] = EXPLICITLY_UNKNOWN

        self._sync_estimated_stage()
        self._compute_derived()

    def _sync_estimated_stage(self) -> None:
        stage = self.state.profile.get("self_assessed_stage")
        if isinstance(stage, int) and 1 <= stage <= 6:
            self.state.estimated_stage = stage

    def _compute_derived(self) -> None:
        # No derived fields. Demand validation is read directly from
        # customer_interview_count / pilot_users / pre_orders / validation_type;
        # the old has_validated_problem summary flag was removed.
        return

    def _stats(self) -> Dict[str, int]:
        return completion_stats(
            self.state.field_states,
            self.state.profile,
            self.state.estimated_stage,
        )
