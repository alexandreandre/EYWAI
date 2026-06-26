#!/usr/bin/env python3
"""
Rattrapage : salariés marqués « départ à traiter plus tard » lors d'imports DSN mensuels
dont la décision n'a pas été persistée sur la fiche (open_exit avant correctif commit).

Exécution (depuis backend/) :
  python scripts/backfill_dsn_open_exit_deferred.py
  python scripts/backfill_dsn_open_exit_deferred.py --dry-run
  python scripts/backfill_dsn_open_exit_deferred.py --company-id <uuid>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import get_supabase_admin_client  # noqa: E402
from app.modules.dsn_import.application.system_user import (  # noqa: E402
    resolve_dsn_workflow_user_id,
)
from app.modules.employee_exits.application.commands import (  # noqa: E402
    create_reconciliation_exit,
)


def _collect_deferred_entries(
    company_id: Optional[str],
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Retourne (batch_id, company_id, entry) pour chaque open_exit_deferred."""
    db = get_supabase_admin_client()
    query = (
        db.table("dsn_import_batches")
        .select("id, summary, status")
        .eq("status", "committed")
        .order("created_at")
    )
    resp = query.execute()
    rows = resp.data or []
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for batch in rows:
        summary = batch.get("summary") or {}
        report = summary.get("commit_report") or {}
        wf = report.get("workforce_reconciliation") or {}
        target_company = str(
            report.get("target_company_id")
            or (summary.get("workforce_reconciliation") or {}).get("company_id")
            or ""
        )
        if company_id and target_company != company_id:
            continue
        for entry in wf.get("open_exit_deferred") or []:
            if not entry.get("employee_id") or not target_company:
                continue
            out.append((str(batch["id"]), target_company, dict(entry)))
    return out


def _latest_by_employee(
    entries: List[Tuple[str, str, Dict[str, Any]]],
) -> Dict[str, Tuple[str, str, Dict[str, Any]]]:
    """Garde la dernière décision par employee_id (batches triés chronologiquement)."""
    by_emp: Dict[str, Tuple[str, str, Dict[str, Any]]] = {}
    for batch_id, company_id, entry in entries:
        by_emp[str(entry["employee_id"])] = (batch_id, company_id, entry)
    return by_emp


def _employee_row(employee_id: str) -> Optional[Dict[str, Any]]:
    db = get_supabase_admin_client()
    resp = (
        db.table("employees")
        .select("id, company_id, employment_status, current_exit_id, first_name, last_name")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans écrire")
    parser.add_argument("--company-id", help="Limiter à une entreprise")
    args = parser.parse_args()

    entries = _collect_deferred_entries(args.company_id)
    latest = _latest_by_employee(entries)
    if not latest:
        print("Aucun salarié open_exit_deferred trouvé dans les batches commités.")
        return 0

    created = skipped = failed = 0
    seen_exit_ids: Set[str] = set()
    workflow_user_id = resolve_dsn_workflow_user_id()

    for employee_id, (batch_id, company_id, entry) in sorted(
        latest.items(), key=lambda x: x[1][2].get("last_working_day") or ""
    ):
        emp = _employee_row(employee_id)
        if not emp:
            print(f"  SKIP {employee_id} — fiche introuvable (batch {batch_id[:8]}…)")
            skipped += 1
            continue

        status = str(emp.get("employment_status") or "actif").lower()
        name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()

        if status in ("en_sortie", "parti") or emp.get("current_exit_id"):
            exit_id = str(entry.get("exit_id") or emp.get("current_exit_id") or "")
            if exit_id:
                seen_exit_ids.add(exit_id)
            print(f"  SKIP {name} ({employee_id[:8]}…) — déjà {status}")
            skipped += 1
            continue

        if status not in ("actif", "active"):
            print(f"  SKIP {name} — statut {status}")
            skipped += 1
            continue

        lwd = entry.get("last_working_day")
        if not lwd:
            print(f"  FAIL {name} — date dernier jour manquante dans batch {batch_id[:8]}…")
            failed += 1
            continue

        exit_type = str(entry.get("exit_type") or "demission")
        gap_id = str(entry.get("gap_id") or "backfill")

        if args.dry_run:
            print(
                f"  DRY-RUN {name} → en_sortie "
                f"(type={exit_type}, lwd={lwd}, batch={batch_id[:8]}…)"
            )
            created += 1
            continue

        try:
            created_exit = create_reconciliation_exit(
                employee_id,
                company_id,
                workflow_user_id,
                exit_type=exit_type,
                last_working_day=lwd,
                exit_reason=f"Départ à finaliser — réconciliation DSN ({gap_id})",
                fast_archive=False,
                source="dsn_reconciliation",
            )
            exit_id = str(created_exit.get("id") or "")
            if exit_id:
                seen_exit_ids.add(exit_id)
            print(f"  OK {name} → en_sortie (exit {exit_id[:8] if exit_id else '—'}…)")
            created += 1
        except Exception as exc:
            print(f"  FAIL {name} — {exc}")
            failed += 1

    print(
        f"\nTerminé : {created} traité(s), {skipped} ignoré(s), {failed} échec(s) "
        f"({len(latest)} salarié(s) distinct(s))."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
