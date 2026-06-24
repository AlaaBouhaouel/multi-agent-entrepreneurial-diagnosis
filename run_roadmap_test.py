"""
run_roadmap_test.py

Full manual test harness for Feature 3 (RAG Roadmap) against YOUR real KB JSON.

Usage
-----
    # Default embedder (auto: bge-m3 if installed, else hashing fallback) + no Ollama:
    python run_roadmap_test.py --kb /path/to/your_kb.json

    # Force the offline-safe combo (no downloads, no Ollama) — fastest for a smoke test:
    python run_roadmap_test.py --kb your_kb.json --embedder hashing

    # Use the real local LLM (requires `ollama serve` + `ollama pull qwen2.5:7b-instruct`):
    python run_roadmap_test.py --kb your_kb.json --embedder bge --use-ollama

    # Test one enterprise only:
    python run_roadmap_test.py --kb your_kb.json --enterprise agri

What it checks
--------------
  0. KB loads + validates (counts problems: missing source_url, no stage tags...)
  1. Gap analysis produces ranked, domain-tagged weaknesses
  2. Retrieval returns eligible + ranked resources (and applies hard filters)
  3. Roadmap engine emits a 3-horizon, fully-traceable roadmap
  4. Grounding invariants hold (every action → real resource_id + source_url)
  5. Personalisation (different enterprises → different roadmaps)
  6. Assistant grounding context assembles and contains the right data
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from roadmap.kb.schema import load_kb, validate_entry
from roadmap.retrieval import KBRetriever
from roadmap.engine import RoadmapEngine
from roadmap.llm import RoadmapLLM
from roadmap.embeddings import get_embedding_backend
from roadmap.gap_analyzer import analyze_gaps
from roadmap.assistant import build_assistant_context

from dummy_data import DUMMY_ENTERPRISES


# ─────────────────────────────────────────────────────────────────────────────
# Pretty printing
# ─────────────────────────────────────────────────────────────────────────────

def hr(title):
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)

def ok(msg):    print(f"  \033[92m✓\033[0m {msg}")
def warn(msg):  print(f"  \033[93m!\033[0m {msg}")
def fail(msg):  print(f"  \033[91m✗\033[0m {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 0 — KB sanity
# ─────────────────────────────────────────────────────────────────────────────

def check_kb(kb_path):
    hr("STEP 0 — Knowledge base load + validation")
    entries = load_kb(kb_path)
    print(f"  loaded {len(entries)} entries from {kb_path}")

    problems = [p for e in entries for p in validate_entry(e)]
    by_domain = {}
    by_stage = {}
    no_url = 0
    for e in entries:
        if not e["source_url"]:
            no_url += 1
        for d in e["blocker_domains"]:
            by_domain[d] = by_domain.get(d, 0) + 1
        for s in e["stage_tags"]:
            by_stage[s] = by_stage.get(s, 0) + 1

    print(f"  resources per blocker domain : {by_domain}")
    print(f"  resources per stage tag      : {by_stage}")

    if len(entries) >= 30:
        ok(f"{len(entries)} resources (meets KB acceptance target of 30+)")
    else:
        warn(f"only {len(entries)} resources — KB spec target is 30+")

    if no_url == 0:
        ok("every resource has a source_url (traceability intact)")
    else:
        warn(f"{no_url} resource(s) missing source_url — will break traceability")

    if problems:
        warn(f"{len(problems)} validation problem(s):")
        for p in problems[:10]:
            print(f"       - {p}")
        if len(problems) > 10:
            print(f"       ... and {len(problems) - 10} more")
    else:
        ok("no validation problems")

    # Coverage warning: any domain with zero resources can never be matched.
    from roadmap.gap_analyzer import KB_DOMAINS
    missing_domains = [d for d in KB_DOMAINS if d not in by_domain]
    if missing_domains:
        warn(f"domains with NO resources (gaps here → unmatched): {missing_domains}")

    return entries


# ─────────────────────────────────────────────────────────────────────────────
# Step 1–4 — per enterprise
# ─────────────────────────────────────────────────────────────────────────────

def run_enterprise(name, profile, diagnosis, scoring, retriever, engine, verbose=True):
    hr(f"ENTERPRISE: {name.upper()} — « {profile['project_name']} »")

    # 1 — gap analysis
    gaps = analyze_gaps(diagnosis, scoring)
    gaps["credit_eligibility_path"] = scoring.get("metrics", {}).get("credit_eligibility_path")
    print(f"  diagnosed stage : {gaps['assigned_stage']}")
    print(f"  perception gap  : {(gaps.get('perception_gap') or {}).get('gap_direction')}")
    print(f"  ranked domains  :")
    for rd in gaps["ranked_domains"]:
        print(f"     - {rd['domain']:<16} gaps={rd['gap_count']} severity={rd['total_severity']}")
    if not gaps["ranked_domains"]:
        warn("no gaps detected — roadmap will be empty (is the dummy data right?)")

    # 2 — retrieval
    resources = retriever.retrieve(gaps, raw_profile=profile, top_k=8)
    print(f"\n  retrieved {len(resources)} eligible resources:")
    for r in resources:
        print(f"     [{r['final_score']:.3f}] {r['resource_id']:<24} "
              f"domains={r['matched_domains']} trust={r['trust_level']}")
    if not resources:
        warn("no resources retrieved — check stage tags / domains in your KB")

    # filter assertions
    rids = {r["resource_id"] for r in resources}
    credit_path = scoring.get("metrics", {}).get("credit_eligibility_path")
    bts_like = {rid for rid in rids if "bts" in rid.lower() or "fonapra" in rid.lower()}
    if credit_path == "none" and bts_like:
        fail(f"BTS/FONAPRA resource leaked despite blocked credit path: {bts_like}")
    elif credit_path == "none":
        ok("BTS/FONAPRA correctly filtered (credit path blocked)")
    elif credit_path == "bts_fonapra" and bts_like:
        ok("BTS/FONAPRA correctly retained (valid credit path)")

    # prior accompaniment exclusion
    prior = set(profile.get("prior_accompaniment", []))
    if prior & rids:
        fail(f"completed program(s) re-recommended: {prior & rids}")
    elif prior:
        ok(f"completed program(s) correctly excluded: {prior}")

    # 3 — roadmap engine
    result = engine.generate(profile, diagnosis, scoring)
    out = result["output"]
    print(f"\n  synthesis source : {out['synthesis_source']}")
    print(f"  verdict          : {out['verdict']['perception_gap_message_fr']}")
    print("  ROADMAP:")
    for horizon, block in out["roadmap_by_horizon"].items():
        if block["actions"]:
            print(f"     ── {block['label_fr']}")
            for a in block["actions"]:
                print(f"        #{a['order']} {a['title']}")
                print(f"           Explication: {a.get('rationale_fr')}")
                print(f"           → [{a['resource_id']}] {a.get('source_url')}")
    if out["unmatched_gaps"]:
        print("  UNMATCHED GAPS (reported, not invented):")
        for u in out["unmatched_gaps"]:
            print(f"     - {u['message_fr']}")

    # 4 — grounding invariants
    valid_ids = {r["resource_id"] for r in resources}
    grounded = True
    for a in out["roadmap_flat"]:
        if a["resource_id"] not in valid_ids:
            fail(f"ungrounded action (resource_id not retrieved): {a}"); grounded = False
        if not a.get("source_url"):
            fail(f"action missing source_url: {a}"); grounded = False
    if grounded and out["roadmap_flat"]:
        ok(f"all {len(out['roadmap_flat'])} actions trace to a KB resource_id + source_url")
    elif not out["roadmap_flat"]:
        warn("roadmap is empty (no eligible resources for this gap profile)")

    # 6 — assistant context
    ctx = build_assistant_context(profile["project_name"], diagnosis, scoring, out)
    has_all = all(r["resource_id"] in ctx for r in resources)
    if has_all and gaps["assigned_stage"] in ctx:
        ok(f"assistant grounding context assembled ({len(ctx)} chars, contains diag + all resources)")
    else:
        warn("assistant context missing some grounding data")

    return rids


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Test the LeadIt RAG roadmap against a real KB JSON.")
    ap.add_argument("--kb", required=True, help="Path to your KB JSON file")
    ap.add_argument("--embedder", default="auto", choices=["auto", "bge", "hashing"],
                    help="auto = bge-m3 if installed else hashing fallback")
    ap.add_argument("--use-live-llm", action="store_true",
                    help="Use Claude Sonnet via Anthropic API for synthesis (requires ANTHROPIC_API_KEY)")
    ap.add_argument("--enterprise", default="all",
                    choices=["all", "agri", "fintech", "growth"])
    args = ap.parse_args()

    if not os.path.exists(args.kb):
        fail(f"KB file not found: {args.kb}"); sys.exit(1)

    # Step 0
    entries = check_kb(args.kb)

    # Build retriever + engine once
    hr("BUILDING RETRIEVER + ENGINE")
    embedder = get_embedding_backend(args.embedder)
    print(f"  embedder : {getattr(embedder, 'model_name', type(embedder).__name__)} (dim={embedder.dim})")
    retriever = KBRetriever(entries, embedder=embedder)
    retriever.index()
    ok(f"indexed {len(entries)} resources into the vector store")

    llm = RoadmapLLM() if args.use_live_llm else None
    engine = RoadmapEngine(retriever, llm=llm)

    # Run enterprises
    selected = list(DUMMY_ENTERPRISES) if args.enterprise == "all" else [args.enterprise]
    roadmaps = {}
    for name in selected:
        profile, diagnosis, scoring = DUMMY_ENTERPRISES[name]
        roadmaps[name] = run_enterprise(name, profile, diagnosis, scoring, retriever, engine)

    # Step 5 — personalisation across enterprises
    if len(roadmaps) > 1:
        hr("STEP 5 — Personalisation (different enterprises → different roadmaps)")
        names = list(roadmaps)
        all_distinct = True
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                if roadmaps[a] == roadmaps[b]:
                    fail(f"{a} and {b} produced identical resource sets"); all_distinct = False
                else:
                    overlap = roadmaps[a] & roadmaps[b]
                    print(f"  {a} vs {b}: {len(overlap)} shared, "
                          f"{len(roadmaps[a] ^ roadmaps[b])} different")
        if all_distinct:
            ok("every enterprise produced a distinct roadmap")

    hr("DONE")
    print("  If you saw mostly ✓ and no ✗, the pipeline is wired correctly against your KB.")
    print("  ! warnings usually point to KB coverage gaps, not code bugs.\n")


if __name__ == "__main__":
    main()
