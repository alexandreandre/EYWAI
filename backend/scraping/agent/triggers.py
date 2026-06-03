"""Normalisation des déclencheurs agent (tripwire, échec orchestrateur, CI)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class FailureKind(str, Enum):
    DOM_CHANGE = "dom_change"
    URL_DEAD = "url_dead"
    ANTI_BOT = "anti_bot"
    VALIDATION_REJECT = "validation_reject"
    UNKNOWN = "unknown"


@dataclass
class RepairContext:
    scraper_name: str
    trigger: str
    error_message: str
    failure_kind: FailureKind
    source_id: Optional[str] = None
    tripwire_url: Optional[str] = None
    tripwire_excerpt: Optional[str] = None
    orchestrator_stderr: str = ""
    official_primary_url: str = ""


def classify_failure(error_message: str, stderr: str = "") -> FailureKind:
    blob = f"{error_message}\n{stderr}".lower()
    if any(x in blob for x in ("404", "410", "not found", "introuvable", "url morte")):
        return FailureKind.URL_DEAD
    if any(x in blob for x in ("403", "forbidden", "anti-bot", "selenium", "captcha")):
        return FailureKind.ANTI_BOT
    if any(x in blob for x in ("validation", "hors plage", "hors [", "signature métier")):
        return FailureKind.VALIDATION_REJECT
    if any(x in blob for x in ("tripwire", "hash", "dom", "parser", "extrait")):
        return FailureKind.DOM_CHANGE
    return FailureKind.UNKNOWN


def build_context_from_job(job: dict[str, Any]) -> RepairContext:
    ctx = job.get("context") or {}
    err = job.get("error_message") or ""
    stderr = ctx.get("stderr") or ""
    return RepairContext(
        scraper_name=job.get("scraper_name", ""),
        trigger=job.get("trigger", "manual"),
        error_message=err,
        failure_kind=FailureKind(ctx.get("failure_kind") or classify_failure(err, stderr).value),
        source_id=job.get("source_id"),
        tripwire_url=ctx.get("tripwire_url"),
        tripwire_excerpt=ctx.get("tripwire_excerpt"),
        orchestrator_stderr=stderr,
        official_primary_url=ctx.get("official_primary_url") or "",
    )


def context_for_orchestrator_failure(
    scraper_name: str,
    *,
    source_id: Optional[str],
    error: str,
    stderr: str = "",
    official_url: str = "",
) -> dict[str, Any]:
    kind = classify_failure(error, stderr)
    return {
        "failure_kind": kind.value,
        "stderr": stderr[:8000],
        "official_primary_url": official_url,
    }


def context_for_tripwire(
    *,
    url: str,
    excerpt: str = "",
    official_url: str = "",
) -> dict[str, Any]:
    return {
        "failure_kind": FailureKind.DOM_CHANGE.value,
        "tripwire_url": url,
        "tripwire_excerpt": excerpt[:2000],
        "official_primary_url": official_url,
    }
