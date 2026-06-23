"""
intake/test_live.py

End-to-end live test: intake interview → analysis presentation → follow-up Q&A.

Run:
    python intake/test_live.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("API_KEY_CLAUDE")
if not api_key:
    sys.exit("API_KEY_CLAUDE not found in .env")

from anthropic import Anthropic
_client = Anthropic(api_key=api_key)


def call_llm(messages: list[dict]) -> str:
    system = ""
    chat = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            chat.append(m)
    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system,
        messages=chat,
    )
    return response.content[0].text


# ── Intake phase ────────────────────────────────────────────────────────────

def run_intake(project_name: str) -> dict:
    from intake import IntakeEngine

    engine = IntakeEngine(project_name=project_name, call_llm=call_llm)
    question = engine.start()

    while True:
        print(f"\n[Question] {question}")
        answer = input("> ").strip()

        if answer.lower() in ("quit", "exit", "stop", "/stop"):
            print("  (entretien interrompu par l'utilisateur)")
            break

        result = engine.respond(answer)

        if result.extracted:
            print(f"  → Extrait : {list(result.extracted.keys())}")
        if result.explicitly_unknown:
            print(f"  → Inconnu : {result.explicitly_unknown}")

        stats = result.stats
        total = stats["answered"] + stats["pending"]
        pct = int(stats["answered"] / total * 100) if total else 0
        print(f"  → Progression : {stats['answered']}/{total} champs ({pct}%)")

        if result.is_done:
            print("\n✓ Collecte terminée.")
            break

        question = result.question

    return engine.get_profile()


# ── Analysis phase ──────────────────────────────────────────────────────────

def run_analysis_session(profile: dict) -> None:
    from intake.analyst import run_analysis, AnalystSession

    print("\n" + "="*60)
    print("  Analyse en cours…")
    print("="*60)

    try:
        analysis = run_analysis(profile)
    except Exception as e:
        print(f"  Erreur lors de l'analyse : {e}")
        return

    session = AnalystSession(profile, analysis, call_llm)

    print("\n" + "="*60)
    print("  DIAGNOSTIC LEADIT")
    print("="*60)
    print()
    print(session.present())

    print("\n" + "-"*60)
    print("  Questions de suivi — tapez 'fin' pour terminer")
    print("-"*60)

    while True:
        question = input("\n> ").strip()
        if not question:
            continue
        if question.lower() in ("fin", "exit", "quit", "stop"):
            break
        print()
        print(session.ask(question))


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  LeadIt — Entretien & Diagnostic")
    print("="*60)
    project_name = input("\nNom du projet : ").strip() or "Projet sans nom"

    profile = run_intake(project_name)

    if not profile:
        print("Aucun profil collecté.")
        return

    print(f"\n  Profil collecté : {len(profile)} champs")
    run_analysis_session(profile)


if __name__ == "__main__":
    main()
