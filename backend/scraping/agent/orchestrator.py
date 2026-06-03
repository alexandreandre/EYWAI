"""Boucle principale de l'agent de réparation scraping."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from agent.jobs import (
    claim_next_job,
    emit_repair_alert,
    enqueue_repair_job,
    update_job,
)
from agent.models import MAX_ITERATIONS, agent_disabled, code_model_for_iteration
from agent.prompts import CODE_REPAIR_SYSTEM, URL_DISCOVERY_SYSTEM
from agent.source_registry import fetch_official_source
from agent.tools import (
    FileEdit,
    apply_edits,
    create_pr_and_merge,
    fetch_page,
    git_commit_and_push,
    parse_edits_from_llm,
    read_file,
    scraper_script_paths,
)
from agent.triggers import FailureKind, RepairContext, build_context_from_job
from agent.verify_repair import verify_repair
from core.env import ensure_scraping_path, load_env
from core.supabase_io import init_supabase_client
from scraper_manifest import get_manifest

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manifest_entry(scraper_name: str):
    for e in get_manifest():
        if e.name == scraper_name:
            return e
    return None


def _build_repair_prompt(ctx: RepairContext, *, feedback: str = "") -> str:
    entry = _manifest_entry(ctx.scraper_name)
    scripts = scraper_script_paths(ctx.scraper_name)
    script_contents = []
    for rel in scripts[:4]:
        content = read_file(rel)
        if content:
            script_contents.append(f"### {rel}\n```python\n{content[:12000]}\n```")

    official_url = ctx.official_primary_url
    html_excerpt = ""
    if official_url:
        _, html = fetch_page(official_url)
        html_excerpt = html[:15000]

    checks_desc = ""
    if entry:
        checks_desc = str(
            [{"path": c.path, "min": c.min, "max": c.max} for c in entry.checks]
        )

    parts = [
        f"Scraper : {ctx.scraper_name}",
        f"Type d'échec : {ctx.failure_kind.value}",
        f"Trigger : {ctx.trigger}",
        f"URL officielle (registre Suivi des taux) : {official_url}",
        f"Erreur : {ctx.error_message[:2000]}",
        f"Invariants manifeste : {checks_desc}",
        "",
        "Scripts actuels :",
        "\n".join(script_contents),
    ]
    if html_excerpt:
        parts.extend(["", "HTML officiel (extrait) :", f"```html\n{html_excerpt}\n```"])
    if ctx.tripwire_excerpt:
        parts.extend(["", "Extrait tripwire :", ctx.tripwire_excerpt[:1500]])
    if feedback:
        parts.extend(["", f"Feedback itération précédente : {feedback}"])
    parts.extend([
        "",
        "Produis les edits de fichiers (path relatif au repo, new_content complet).",
        "Ne hardcode aucune valeur de taux.",
    ])
    return "\n".join(parts)


def _propose_code_patch(
    ctx: RepairContext,
    *,
    attempt: int,
    feedback: str = "",
    propose_fn: Optional[Callable[..., dict[str, Any] | None]] = None,
) -> Optional[list[FileEdit]]:
    if propose_fn is not None:
        data = propose_fn(ctx, attempt, feedback)
        return parse_edits_from_llm(data) if data else None

    try:
        from openrouter_client import chat_completions_create, require_api_key

        require_api_key()
    except Exception as exc:
        logger.error("OpenRouter indisponible : %s", exc)
        return None

    schema = {
        "type": "object",
        "properties": {
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_content": {"type": "string"},
                        "new_content": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["path", "new_content"],
                    "additionalProperties": False,
                },
            },
            "rationale": {"type": "string"},
        },
        "required": ["edits", "rationale"],
        "additionalProperties": False,
    }

    model = code_model_for_iteration(attempt)
    user = _build_repair_prompt(ctx, feedback=feedback)

    try:
        resp = chat_completions_create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": CODE_REPAIR_SYSTEM},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "code_repair", "strict": True, "schema": schema},
            },
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        return parse_edits_from_llm(data)
    except Exception as exc:
        logger.error("Proposition patch échouée (attempt %s): %s", attempt, exc)
        return None


def _discover_official_url(ctx: RepairContext) -> Optional[str]:
    if not ctx.official_primary_url:
        return None
    try:
        from agent.models import MODEL_URL_SEARCH, OFFICIAL_DOMAINS
        from openrouter_client import chat_completions_create, require_api_key

        require_api_key()
        schema = {
            "type": "object",
            "properties": {
                "new_url": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["new_url", "rationale"],
            "additionalProperties": False,
        }
        plugins = [{"id": "web", "max_results": 5, "include_domains": OFFICIAL_DOMAINS}]
        resp = chat_completions_create(
            model=MODEL_URL_SEARCH,
            temperature=0,
            messages=[
                {"role": "system", "content": URL_DISCOVERY_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"L'URL {ctx.official_primary_url} pour le scraper "
                        f"{ctx.scraper_name} ne fonctionne plus. Trouve la nouvelle URL officielle."
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "url_discovery", "strict": True, "schema": schema},
            },
            extra_body={"plugins": plugins},
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
        return data.get("new_url")
    except Exception as exc:
        logger.warning("URL discovery échouée : %s", exc)
        return None


def run_repair_job(
    job: dict[str, Any],
    supabase=None,
    *,
    propose_fn: Optional[Callable[..., dict[str, Any] | None]] = None,
    skip_git: bool = False,
) -> dict[str, Any]:
    """Exécute un job de réparation. Retourne résumé JSON."""
    ensure_scraping_path()
    load_env()
    supabase = supabase or init_supabase_client()

    ctx = build_context_from_job(job)
    job_id = job["id"]
    attempts = int(job.get("attempts") or 0)

    # Source officielle depuis scraping_sources (Suivi des taux)
    official = fetch_official_source(supabase, ctx.scraper_name)
    if official and official.primary_url:
        ctx.official_primary_url = official.primary_url
        if not ctx.source_id:
            ctx.source_id = official.source_id

    history: list[str] = []
    feedback = ""

    for iteration in range(1, MAX_ITERATIONS + 1):
        attempts += 1
        update_job(supabase, job_id, attempts=attempts, model_used=code_model_for_iteration(iteration))

        if ctx.failure_kind == FailureKind.URL_DEAD and iteration == 1:
            new_url = _discover_official_url(ctx)
            if new_url and new_url != ctx.official_primary_url and official and official.source_id:
                from agent.source_registry import update_primary_url
                from agent.tools import find_url_constants_in_scripts, replace_url_in_file

                update_primary_url(supabase, official.source_id, new_url, validated_at=_iso_now())
                for rel, url in find_url_constants_in_scripts(ctx.scraper_name):
                    if ctx.official_primary_url in url:
                        replace_url_in_file(rel, url, new_url)
                ctx.official_primary_url = new_url
                history.append(f"URL officielle migrée → {new_url}")

        edits = _propose_code_patch(ctx, attempt=iteration, feedback=feedback, propose_fn=propose_fn)
        if not edits:
            feedback = "Aucun patch proposé"
            history.append(f"T{iteration}: pas de patch")
            continue

        ok, err = apply_edits(edits)
        if not ok:
            feedback = f"Patch rejeté par safety : {err}"
            history.append(f"T{iteration}: safety KO — {err}")
            continue

        verify = verify_repair(ctx.scraper_name, full_gate=(iteration == MAX_ITERATIONS))
        if not verify.ok:
            feedback = verify.message + "\n" + (
                verify.stages[-1].output if verify.stages else ""
            )
            history.append(f"T{iteration}: oracle KO — {verify.message}")
            update_job(supabase, job_id, status="tests_failed", history=history)
            continue

        # Succès
        edited_paths = [e.path for e in edits]
        diff_summary = f"{len(edits)} fichier(s): " + ", ".join(edited_paths)
        update_job(
            supabase,
            job_id,
            status="tests_passed",
            diff_summary=diff_summary,
            history=history,
            completed_at=_iso_now(),
        )

        pr_url = ""
        if not skip_git:
            branch = f"scraping-agent/repair-{ctx.scraper_name}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
            msg = f"fix(scraping): repair {ctx.scraper_name} — {ctx.failure_kind.value}"
            git_ok, git_msg = git_commit_and_push(branch=branch, message=msg, files=edited_paths)
            if git_ok:
                pr_ok, pr_msg = create_pr_and_merge(
                    branch,
                    title=msg,
                    body=f"Agent autonome — trigger {ctx.trigger}\n\n{diff_summary}",
                )
                pr_url = pr_msg if pr_ok else ""
                final_status = "merged" if pr_ok else "tests_passed"
            else:
                final_status = "tests_passed"
                history.append(f"Git skip: {git_msg}")
        else:
            final_status = "tests_passed"

        update_job(
            supabase,
            job_id,
            status=final_status,
            pr_url=pr_url or None,
            ci_run_url=pr_url or None,
        )
        emit_repair_alert(
            supabase,
            alert_type="repair_agent_merged" if final_status == "merged" else "repair_agent_success",
            scraper_name=ctx.scraper_name,
            source_id=ctx.source_id,
            title=f"Réparation agent : {ctx.scraper_name}",
            message=f"Statut {final_status} après {iteration} tentative(s)",
            details={"diff_summary": diff_summary, "history": history},
            severity="info",
        )
        return {
            "success": True,
            "job_id": job_id,
            "scraper_name": ctx.scraper_name,
            "status": final_status,
            "attempts": attempts,
            "diff_summary": diff_summary,
        }

    update_job(
        supabase,
        job_id,
        status="aborted",
        attempts=attempts,
        history=history,
        completed_at=_iso_now(),
    )
    emit_repair_alert(
        supabase,
        alert_type="repair_agent_aborted",
        scraper_name=ctx.scraper_name,
        source_id=ctx.source_id,
        title=f"Réparation agent échouée : {ctx.scraper_name}",
        message=f"Abandon après {MAX_ITERATIONS} tentatives",
        details={"history": history},
        severity="warning",
    )
    return {
        "success": False,
        "job_id": job_id,
        "scraper_name": ctx.scraper_name,
        "status": "aborted",
        "attempts": attempts,
    }


def run_repair_queue(
    *,
    max_jobs: int = 5,
    skip_git: bool = False,
) -> list[dict[str, Any]]:
    """Traite jusqu'à max_jobs jobs queued."""
    if agent_disabled():
        logger.info("Agent désactivé (EYWAI_REPAIR_AGENT_DISABLED)")
        return []

    ensure_scraping_path()
    load_env()
    supabase = init_supabase_client()
    results: list[dict[str, Any]] = []

    for _ in range(max_jobs):
        job = claim_next_job(supabase)
        if not job:
            break
        try:
            results.append(run_repair_job(job, supabase, skip_git=skip_git))
        except Exception as exc:
            logger.exception("Job %s échoué : %s", job.get("id"), exc)
            update_job(
                supabase,
                job["id"],
                status="aborted",
                error_message=str(exc),
                completed_at=_iso_now(),
            )
            results.append({"success": False, "job_id": job["id"], "error": str(exc)})
    return results


def enqueue_from_orchestrator_failure(
    supabase,
    *,
    scraper_name: str,
    source_id: Optional[str],
    error: str,
    stderr: str = "",
) -> None:
    from agent.triggers import context_for_orchestrator_failure

    official = fetch_official_source(supabase, scraper_name)
    official_url = official.primary_url if official else ""
    enqueue_repair_job(
        supabase,
        scraper_name=scraper_name,
        trigger="orchestrator_failure",
        source_id=source_id or (official.source_id if official else None),
        error_message=error,
        context=context_for_orchestrator_failure(
            scraper_name,
            source_id=source_id,
            error=error,
            stderr=stderr,
            official_url=official_url,
        ),
    )
