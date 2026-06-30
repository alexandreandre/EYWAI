#!/usr/bin/env python3
"""Réimporte les DSN Config/*/DSN en flux mensuel contrôlé.

Mode par défaut : simulation sans écriture. L'exécution réelle exige à la fois
``--execute`` et ``--confirm-prod-write``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_supabase_admin_client  # noqa: E402
from app.modules.dsn_import.application import service  # noqa: E402
from app.modules.dsn_import.application.coverage import compute_coverage  # noqa: E402
from app.modules.dsn_import.application.cumuls import (  # noqa: E402
    build_cumuls_summary,
    plan_cumul_items,
)
from app.modules.dsn_import.application.import_checks import (  # noqa: E402
    attach_import_context_warnings,
)
from app.modules.dsn_import.application.mapping import (  # noqa: E402
    build_preview_items,
    build_review_summary,
    enrich_summary_from_items,
)
from app.modules.dsn_import.application.orphan_employees import (  # noqa: E402
    attach_reimport_orphans,
)
from app.modules.dsn_import.application.system_user import (  # noqa: E402
    resolve_dsn_workflow_user_id,
)
from app.modules.dsn_import.application.workforce_reconciliation import (  # noqa: E402
    attach_workforce_reconciliation,
    workforce_blocks_commit,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files  # noqa: E402
from app.modules.dsn_import.domain.user_messages import parse_warning_anomaly  # noqa: E402
from app.modules.dsn_import.domain.validation import validate_parsed_dsn  # noqa: E402
from app.modules.dsn_import.infrastructure import (  # noqa: E402
    payroll_totals_repository as totals_repo,
)
from app.modules.dsn_import.infrastructure import repository as dsn_repo  # noqa: E402
from app.modules.payroll.domain.payroll_kpi_resolver import (  # noqa: E402
    align_net_with_gross,
)


EXPECTED_FOLDERS = {
    "Cartol": ("cartol",),
    "Lewis": ("lewis",),
    "Colorplast": ("colorplast",),
    "Comitech Composite": ("comitech composite", "comitech"),
    "Maji": ("maji",),
    "MBC": ("mont blanc", "mbc"),
    "Zone": ("zone 404", "zone"),
}
EXPECTED_PERIODS = [f"2026-{month:02d}" for month in range(1, 6)]
CONFIRMATION = "EYWAI_PROD_DSN_REIMPORT_2026_JAN_MAY"


@dataclass(frozen=True)
class DsnJob:
    folder: str
    path: Path
    period: str
    company_id: str
    company_name: str


def _norm(value: str) -> str:
    value = value.lower().replace("&", " et ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _period_from_name(path: Path) -> str | None:
    match = re.search(r"(?<!\d)(0[1-5])26(?!\d)", path.name)
    if not match:
        return None
    return f"2026-{match.group(1)}"


def _load_companies() -> list[dict[str, Any]]:
    rows = dsn_repo.list_companies_for_attribution()
    return [r for r in rows if r.get("is_active", True)]


def _fetch_all(table: str, select: str, *, page_size: int = 1000) -> list[dict[str, Any]]:
    client = get_supabase_admin_client()
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        resp = (
            client.table(table)
            .select(select)
            .range(start, start + page_size - 1)
            .execute()
        )
        chunk = [dict(row) for row in (resp.data or [])]
        rows.extend(chunk)
        if len(chunk) < page_size:
            return rows
        start += page_size


def install_dry_run_read_cache() -> None:
    """Accélère les simulations en remplaçant les lectures point à point par des dicts."""
    companies = _fetch_all(
        "companies",
        "id, company_name, raison_sociale, siret, siren, group_id, is_active, "
        "dsn_sync_mode, paie_occurrence, paie_jour_de_fin, taux_at_mp, effectif, "
        "settings, idcc",
    )
    groups = _fetch_all("company_groups", "id, group_name, siren")
    employees = _fetch_all(
        "employees",
        "id, company_id, first_name, last_name, email, user_id, nir, employment_status, "
        "contract_end_date, hire_date, employee_folder_name",
    )

    companies_by_id = {str(row["id"]): row for row in companies if row.get("id")}
    companies_by_siret = {
        str(row["siret"]).strip(): row
        for row in companies
        if str(row.get("siret") or "").strip()
    }
    groups_by_siren = {
        str(row["siren"]).strip(): row
        for row in groups
        if str(row.get("siren") or "").strip()
    }
    employees_by_company_nir: dict[tuple[str, str], dict[str, Any]] = {}
    employees_by_nir: dict[str, dict[str, Any]] = {}
    employees_by_company: dict[str, list[dict[str, Any]]] = {}
    for row in employees:
        cid = str(row.get("company_id") or "")
        nir = str(row.get("nir") or "").strip()
        if cid:
            employees_by_company.setdefault(cid, []).append(row)
        if cid and nir:
            employees_by_company_nir[(cid, nir)] = row
        if nir and nir not in employees_by_nir:
            employees_by_nir[nir] = row

    group_names = {str(row["id"]): row.get("group_name") for row in groups if row.get("id")}

    def list_companies_for_attribution_cached() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in companies:
            gid = str(row["group_id"]) if row.get("group_id") else None
            out.append(
                {
                    "id": str(row["id"]),
                    "company_name": row.get("company_name") or "Entreprise",
                    "siret": row.get("siret"),
                    "siren": row.get("siren"),
                    "group_id": gid,
                    "group_name": group_names.get(gid) if gid else None,
                    "is_active": row.get("is_active", True),
                }
            )
        return out

    def find_company_by_id_cached(company_id: str) -> dict[str, Any] | None:
        return companies_by_id.get(str(company_id))

    def find_company_by_siret_cached(siret: str) -> dict[str, Any] | None:
        return companies_by_siret.get(str(siret or "").strip())

    def find_group_by_siren_cached(siren: str) -> dict[str, Any] | None:
        return groups_by_siren.get(str(siren or "").strip())

    def find_employee_by_nir_cached(company_id: str, nir: str) -> dict[str, Any] | None:
        return employees_by_company_nir.get((str(company_id), str(nir or "").strip()))

    def find_employee_by_nir_global_cached(nir: str) -> dict[str, Any] | None:
        return employees_by_nir.get(str(nir or "").strip())

    def list_active_employees_with_nir_cached(company_id: str) -> list[dict[str, Any]]:
        active_statuses = {"actif", "active"}
        out = []
        for row in employees_by_company.get(str(company_id), []):
            if (row.get("employment_status") or "actif").lower() not in active_statuses:
                continue
            if str(row.get("nir") or "").strip():
                out.append(dict(row))
        return sorted(out, key=lambda row: str(row.get("last_name") or ""))

    def list_active_employees_without_nir_cached(company_id: str) -> list[dict[str, Any]]:
        active_statuses = {"actif", "active"}
        out = []
        for row in employees_by_company.get(str(company_id), []):
            if (row.get("employment_status") or "actif").lower() not in active_statuses:
                continue
            if not str(row.get("nir") or "").strip():
                out.append(dict(row))
        return sorted(out, key=lambda row: str(row.get("last_name") or ""))

    def list_dsn_placeholder_employees_cached(company_id: str) -> list[dict[str, Any]]:
        out = []
        for row in employees_by_company.get(str(company_id), []):
            email = str(row.get("email") or "")
            if row.get("user_id") or not email.endswith(".dsn-import.local"):
                continue
            out.append(dict(row))
        return sorted(out, key=lambda row: str(row.get("last_name") or ""))

    dsn_repo.list_companies_for_attribution = list_companies_for_attribution_cached
    dsn_repo.find_company_by_id = find_company_by_id_cached
    dsn_repo.find_company_by_siret = find_company_by_siret_cached
    dsn_repo.find_group_by_siren = find_group_by_siren_cached
    dsn_repo.find_employee_by_nir = find_employee_by_nir_cached
    dsn_repo.find_employee_by_nir_global = find_employee_by_nir_global_cached
    dsn_repo.list_active_employees_with_nir = list_active_employees_with_nir_cached
    dsn_repo.list_active_employees_without_nir = list_active_employees_without_nir_cached
    dsn_repo.list_dsn_placeholder_employees = list_dsn_placeholder_employees_cached


def _resolve_company(folder: str, companies: list[dict[str, Any]]) -> tuple[str, str]:
    aliases = EXPECTED_FOLDERS[folder]
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in companies:
        name = _norm(str(row.get("company_name") or ""))
        for alias in aliases:
            alias_norm = _norm(alias)
            if name == alias_norm:
                scored.append((100, row))
            elif alias_norm in name:
                scored.append((80, row))
    dedup: dict[str, tuple[int, dict[str, Any]]] = {}
    for score, row in scored:
        cid = str(row["id"])
        if cid not in dedup or score > dedup[cid][0]:
            dedup[cid] = (score, row)
    matches = sorted(dedup.values(), key=lambda item: item[0], reverse=True)
    if len(matches) != 1:
        names = ", ".join(str(r.get("company_name")) for _, r in matches) or "aucune"
        raise RuntimeError(
            f"Entreprise cible ambiguë pour {folder}: {names}. "
            "Ajoutez un alias exact dans EXPECTED_FOLDERS ou filtrez le lot."
        )
    row = matches[0][1]
    return str(row["id"]), str(row.get("company_name") or folder)


def discover_jobs(config_dir: Path) -> list[DsnJob]:
    companies = _load_companies()
    jobs: list[DsnJob] = []
    missing: list[str] = []
    for folder in EXPECTED_FOLDERS:
        dsn_dir = config_dir / folder / "DSN"
        files = sorted(dsn_dir.glob("*.dsn"))
        by_period = {_period_from_name(path): path for path in files if _period_from_name(path)}
        for period in EXPECTED_PERIODS:
            path = by_period.get(period)
            if not path:
                missing.append(f"{folder} {period}")
                continue
            company_id, company_name = _resolve_company(folder, companies)
            jobs.append(
                DsnJob(
                    folder=folder,
                    path=path,
                    period=period,
                    company_id=company_id,
                    company_name=company_name,
                )
            )
    if missing:
        raise RuntimeError("DSN manquantes: " + ", ".join(missing))
    return sorted(jobs, key=lambda job: (job.period, job.folder))


def filter_jobs(jobs: list[DsnJob], *, only_company: str | None, only_period: str | None) -> list[DsnJob]:
    out = jobs
    if only_company:
        target = _norm(only_company)
        out = [job for job in out if _norm(job.folder) == target or target in _norm(job.company_name)]
    if only_period:
        out = [job for job in out if job.period == only_period]
    return out


def _preview_without_writes(job: DsnJob) -> dict[str, Any]:
    content = job.path.read_bytes()
    parsed = parse_dsn_files([(job.path.name, content)])
    anomalies = validate_parsed_dsn(parsed)
    for warning in parsed.warnings or []:
        anomalies.append(parse_warning_anomaly(str(warning)))

    preview_items, summary = build_preview_items(parsed)
    cumul_items = plan_cumul_items(parsed)
    all_items = preview_items + cumul_items

    service._enrich_actions(all_items, target_company_id=job.company_id, anomalies=anomalies)
    service._attach_psc_warnings(all_items, anomalies)
    summary = enrich_summary_from_items(summary, parsed, all_items)
    summary.update(service._employee_state_counts(all_items))
    summary["review_summary"] = build_review_summary(all_items)
    summary["target_company_id"] = job.company_id
    summary["import_mode"] = "monthly"
    summary["intended_period"] = job.period
    periods = sorted(
        {
            str(item.get("mapped_payload", {}).get("period"))
            for item in cumul_items
            if item.get("mapped_payload", {}).get("period")
        }
    )
    summary["cumul_month_count"] = len(periods)
    summary["cumul_periods"] = periods
    summary["cumuls_summary"] = build_cumuls_summary(cumul_items)

    attach_workforce_reconciliation(
        all_items,
        summary,
        anomalies,
        target_company_id=job.company_id,
        import_mode="monthly",
    )
    attach_reimport_orphans(
        all_items,
        summary,
        target_company_id=job.company_id,
        import_mode="monthly",
    )
    service._attach_import_warnings(
        anomalies,
        summary,
        mode="monthly",
        target_company_id=job.company_id,
        periods=periods,
    )
    attach_import_context_warnings(
        anomalies,
        summary,
        mode="monthly",
        target_company_id=job.company_id,
        periods=periods,
        dsn_company_name=summary.get("dsn_company_name"),
        intended_period=job.period,
    )
    can_commit = not any(a.get("severity") == "blocking" for a in anomalies)
    if workforce_blocks_commit(summary):
        can_commit = False
    return {
        "summary": summary,
        "anomalies": anomalies,
        "items": all_items,
        "can_commit": can_commit,
    }


def _existing_employee_skip_overrides(items: Iterable[dict[str, Any]]) -> dict[str, str]:
    return {
        str(item["source_ref"]): "skip"
        for item in items
        if item.get("item_type") == "employee" and item.get("is_existing")
    }


def _blocking_anomalies(anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in anomalies if a.get("severity") == "blocking"]


def _workforce_unresolved(summary: dict[str, Any]) -> int:
    wf = summary.get("workforce_reconciliation") or {}
    return int(wf.get("unresolved_count") or 0) if wf.get("enabled") else 0


def run_job(job: DsnJob, *, execute: bool, uploaded_by: str) -> dict[str, Any]:
    base = {
        "folder": job.folder,
        "company": job.company_name,
        "company_id": job.company_id,
        "period": job.period,
        "file": str(job.path.relative_to(REPO_ROOT)),
        "status": "dry_run" if not execute else "pending",
    }
    try:
        preview = _preview_without_writes(job)
        summary = preview["summary"]
        anomalies = preview["anomalies"]
        unresolved = _workforce_unresolved(summary)
        blocking = _blocking_anomalies(anomalies)
        overrides = _existing_employee_skip_overrides(preview["items"])
        base.update(
            {
                "employee_existing_skip_count": len(overrides),
                "employee_new_count": summary.get("employee_new_count", 0),
                "cumul_periods": summary.get("cumul_periods") or [],
                "reimport_orphans_count": (summary.get("reimport_orphans") or {}).get("count", 0),
                "workforce_unresolved_count": unresolved,
                "blocking_count": len(blocking),
                "can_commit": bool(preview["can_commit"]),
                "messages": [str(a.get("message") or a.get("type")) for a in anomalies[:8]],
            }
        )
        if unresolved:
            base["status"] = "manual_workforce_reconciliation"
            return base
        if blocking:
            base["status"] = "failed_blocking_preview"
            return base
        if not execute:
            return base

        staged = service.parse_and_stage(
            [(job.path.name, job.path.read_bytes())],
            uploaded_by=uploaded_by,
            import_mode="monthly",
            target_company_id=job.company_id,
            intended_period=job.period,
        )
        staged_unresolved = _workforce_unresolved(staged.get("summary") or {})
        staged_blocking = _blocking_anomalies(staged.get("anomalies") or [])
        if staged_unresolved:
            base.update(
                {
                    "status": "manual_workforce_reconciliation",
                    "batch_id": staged["batch_id"],
                    "workforce_unresolved_count": staged_unresolved,
                }
            )
            return base
        if staged_blocking:
            base.update(
                {
                    "status": "failed_blocking_preview",
                    "batch_id": staged["batch_id"],
                    "blocking_count": len(staged_blocking),
                    "messages": [
                        str(a.get("message") or a.get("type")) for a in staged_blocking[:8]
                    ],
                }
            )
            return base

        commit_overrides = _existing_employee_skip_overrides(staged.get("items") or [])
        report = service.execute_commit(
            staged["batch_id"],
            overrides=commit_overrides,
            payload_edits={},
            target_company_id=job.company_id,
            workforce_resolutions=[],
            current_user_id=uploaded_by,
            remove_orphan_imported_employees=False,
        )
        errors = report.get("errors") or []
        base.update(
            {
                "status": "ok" if not errors else "failed_commit",
                "batch_id": staged["batch_id"],
                "commit_stats": report.get("stats") or {},
                "errors": errors,
                "warnings": report.get("warnings") or [],
            }
        )
        return base
    except Exception as exc:  # noqa: BLE001 - rapport de prod, on continue le lot
        base.update({"status": "failed_exception", "error": str(exc)})
        return base


def may_dashboard_control(jobs: list[DsnJob]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for job in jobs:
        if job.company_id in seen:
            continue
        seen.add(job.company_id)
        row = totals_repo.get_period(job.company_id, "2026-05") or {}
        gross = round(float(row.get("gross_salary") or 0), 2)
        net_raw = round(float(row.get("net_imposable") or 0), 2)
        employee_charges = round(float(row.get("employee_charges") or 0), 2)
        net_dashboard = align_net_with_gross(
            gross,
            net_raw,
            employee_charges=employee_charges,
            employee_count=int(row.get("employee_count") or 0),
            employees_with_gross=int(row.get("employees_with_gross") or 0),
        )
        rows.append(
            {
                "company": job.company_name,
                "company_id": job.company_id,
                "period": "2026-05",
                "gross_salary": gross,
                "net_imposable_raw": net_raw,
                "net_dashboard": net_dashboard,
                "net_lte_gross": net_dashboard <= gross if gross > 0 else None,
                "employee_count": int(row.get("employee_count") or 0),
                "last_batch_id": row.get("last_batch_id"),
            }
        )
    return sorted(rows, key=lambda r: str(r["company"]))


def coverage_control(jobs: list[DsnJob]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for job in jobs:
        if job.company_id in seen:
            continue
        seen.add(job.company_id)
        company = dsn_repo.find_company_by_id(job.company_id)
        if not company:
            continue
        coverage = compute_coverage(company)
        rows.append(
            {
                "company": job.company_name,
                "months_covered_2026_01_05": [
                    period
                    for period in EXPECTED_PERIODS
                    if period in set(coverage.get("months_covered") or [])
                ],
                "missing_2026_01_05": [
                    period
                    for period in EXPECTED_PERIODS
                    if period not in set(coverage.get("months_covered") or [])
                ],
            }
        )
    return sorted(rows, key=lambda r: str(r["company"]))


def write_reports(report: dict[str, Any], report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = report_dir / f"dsn_config_reimport_{stamp}.json"
    md_path = report_dir / f"dsn_config_reimport_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Rapport réimport DSN Config",
        "",
        f"- Mode: {'EXECUTION PROD' if report['execute'] else 'SIMULATION'}",
        f"- Généré: {report['generated_at']}",
        f"- Fichiers traités: {len(report['results'])}",
        "",
        "## Résultats",
        "",
        "| Statut | Entreprise | Période | Fichier | Détails |",
        "|---|---|---:|---|---|",
    ]
    for row in report["results"]:
        details = []
        if row.get("batch_id"):
            details.append(f"batch `{row['batch_id']}`")
        if row.get("workforce_unresolved_count"):
            details.append(f"{row['workforce_unresolved_count']} écart(s) effectifs")
        if row.get("blocking_count"):
            details.append(f"{row['blocking_count']} blocage(s)")
        if row.get("commit_stats"):
            details.append(f"stats {row['commit_stats']}")
        if row.get("error"):
            details.append(str(row["error"]))
        lines.append(
            "| {status} | {company} | {period} | `{file}` | {details} |".format(
                status=row.get("status"),
                company=row.get("company"),
                period=row.get("period"),
                file=row.get("file"),
                details="; ".join(details) or "-",
            )
        )
    lines.extend(["", "## Contrôle mai 2026", ""])
    lines.append("| Entreprise | Brut | Net dashboard | Net <= brut | Salariés |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in report["may_2026_control"]:
        lines.append(
            "| {company} | {gross:.2f} | {net:.2f} | {ok} | {count} |".format(
                company=row["company"],
                gross=row["gross_salary"],
                net=row["net_dashboard"],
                ok=row["net_lte_gross"],
                count=row["employee_count"],
            )
        )
    lines.extend(["", "## Couverture janvier-mai 2026", ""])
    for row in report["coverage_control"]:
        lines.append(
            f"- {row['company']}: OK {row['months_covered_2026_01_05']} ; "
            f"manquant {row['missing_2026_01_05']}"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulation/exécution du réimport mensuel DSN Config janvier-mai 2026."
    )
    parser.add_argument("--config-dir", default=str(REPO_ROOT / "Config"))
    parser.add_argument("--report-dir", default=str(REPO_ROOT / "backend" / "reports"))
    parser.add_argument("--company", help="Limiter à une filiale (ex: Maji).")
    parser.add_argument("--period", help="Limiter à une période YYYY-MM (ex: 2026-05).")
    parser.add_argument("--test-maji-may", action="store_true", help="Limiter à Maji mai 2026.")
    parser.add_argument("--execute", action="store_true", help="Écrit en base Supabase prod.")
    parser.add_argument(
        "--confirm-prod-write",
        default="",
        help=f"Confirmation obligatoire: {CONFIRMATION}",
    )
    parser.add_argument(
        "--yes-i-know-no-recompute",
        action="store_true",
        help="Confirme qu'aucun recompute_committed_batches ne sera lancé par ce script.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.test_maji_may:
        args.company = "Maji"
        args.period = "2026-05"
    if args.execute:
        if args.confirm_prod_write != CONFIRMATION:
            print(f"Refus: ajoute --confirm-prod-write {CONFIRMATION}", file=sys.stderr)
            return 2
        if not args.yes_i_know_no_recompute:
            print("Refus: ajoute --yes-i-know-no-recompute.", file=sys.stderr)
            return 2

    config_dir = Path(args.config_dir).expanduser().resolve()
    if not args.execute:
        install_dry_run_read_cache()
    jobs = filter_jobs(
        discover_jobs(config_dir),
        only_company=args.company,
        only_period=args.period,
    )
    if not jobs:
        print("Aucun fichier DSN dans le périmètre demandé.", file=sys.stderr)
        return 1

    uploaded_by = resolve_dsn_workflow_user_id() if args.execute else "00000000-0000-0000-0000-000000000000"
    results = []
    for index, job in enumerate(jobs, start=1):
        print(f"[{index}/{len(jobs)}] {job.folder} {job.period} — {job.path.name}", flush=True)
        results.append(run_job(job, execute=args.execute, uploaded_by=uploaded_by))

    report = {
        "execute": bool(args.execute),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_dir": str(config_dir),
        "results": results,
        "may_2026_control": may_dashboard_control(jobs),
        "coverage_control": coverage_control(jobs),
    }
    json_path, md_path = write_reports(report, Path(args.report_dir).expanduser().resolve())
    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print("Résumé:", counts, flush=True)
    print(f"Rapport JSON: {json_path}", flush=True)
    print(f"Rapport Markdown: {md_path}", flush=True)
    return 0 if not any(str(k).startswith("failed") for k in counts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
