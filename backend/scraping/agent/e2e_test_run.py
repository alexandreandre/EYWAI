#!/usr/bin/env python3
"""Test E2E agent repair avec suivi coût OpenRouter (sans git/PR)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from agent.jobs import claim_next_job, update_job
from agent.models import MODEL_CODE_REPAIR, MODEL_URL_SEARCH
from agent.orchestrator import run_repair_job
from core.env import ensure_scraping_path, load_env
from core.supabase_io import init_supabase_client

# Tarifs OpenRouter Kimi K2.6 / Sonar (USD par 1M tokens, ordre de grandeur)
PRICING = {
    "moonshotai/kimi-k2.6": (0.684, 3.42),
    "moonshotai/kimi-k2.5": (0.40, 1.90),
    "perplexity/sonar": (1.0, 1.0),  # approx
}


def _install_usage_tracker() -> list[dict]:
    records: list[dict] = []
    import openrouter_client as oc

    original = oc.chat_completions_create

    def tracked(*, model: str, **kwargs):
        t0 = time.perf_counter()
        resp = original(model=model, **kwargs)
        elapsed = time.perf_counter() - t0
        usage = getattr(resp, "usage", None)
        rec = {
            "model": model,
            "elapsed_s": round(elapsed, 2),
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
        }
        records.append(rec)
        print(
            f"[LLM] {model} — {rec['prompt_tokens']}+{rec['completion_tokens']} tokens "
            f"({rec['elapsed_s']}s)",
            flush=True,
        )
        return resp

    oc.chat_completions_create = tracked
    return records


def _estimate_cost(records: list[dict]) -> float:
    total = 0.0
    for r in records:
        model = r["model"]
        inp, out = PRICING.get(model, (1.0, 3.0))
        total += (r["prompt_tokens"] / 1_000_000) * inp
        total += (r["completion_tokens"] / 1_000_000) * out
    return total


def main() -> int:
    ensure_scraping_path()
    load_env()
    sb = init_supabase_client()

    job = claim_next_job(sb)
    if not job:
        print("Aucun job queued.")
        return 1

    print(f"Job {job['id']} — scraper={job['scraper_name']} trigger={job['trigger']}")
    print(f"Modèle code par défaut: {MODEL_CODE_REPAIR}")
    print(f"Modèle URL: {MODEL_URL_SEARCH}")

    usage_records = _install_usage_tracker()
    t0 = time.perf_counter()
    result = run_repair_job(job, sb, skip_git=True)
    wall_s = round(time.perf_counter() - t0, 1)

    cost = _estimate_cost(usage_records)
    summary = {
        "result": result,
        "wall_time_s": wall_s,
        "llm_calls": usage_records,
        "estimated_cost_usd": round(cost, 4),
        "total_tokens": sum(r["total_tokens"] for r in usage_records),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # Marquer job test si encore actif
    if result.get("job_id"):
        update_job(
            sb,
            result["job_id"],
            context={**(job.get("context") or {}), "e2e_test_summary": summary},
        )
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
