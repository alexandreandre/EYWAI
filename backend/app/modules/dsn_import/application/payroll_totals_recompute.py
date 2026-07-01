"""Recalcule company_dsn_payroll_totals depuis batches committed (sans ré-import)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.modules.dsn_import.application.cumuls import (
    plan_cumul_items,
    _normalize_employee_charges,
)
from app.modules.dsn_import.application.payroll_totals_persist import (
    build_resolve_company_id_from_batch,
    persist_batch_dsn_payroll_totals,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files
from app.modules.dsn_import.infrastructure import repository as repo


def sanitize_stored_month_totals(month_totals: Dict[str, Any]) -> Dict[str, float]:
    """
    Normalise les month_totals persistés en base (imports antérieurs sans cotisations).
    Conserve brut/net ; reconstitue les charges quand absentes ou aberrantes.
    """
    brut = round(float(month_totals.get("brut") or 0), 2)
    net = round(float(month_totals.get("net_imposable") or 0), 2)
    pas = round(float(month_totals.get("pas") or 0), 2)
    employee_charges = _normalize_employee_charges(
        float(month_totals.get("employee_charges") or 0),
        brut=brut,
        net_imposable=net,
    )
    employer_charges = round(float(month_totals.get("employer_charges") or 0), 2)
    if employer_charges < 0 and brut > 0:
        employer_charges = 0.0
    if brut > 0 and net > brut:
        if employee_charges > 0:
            net = round(max(brut - employee_charges, 0.0), 2)
        else:
            net = round(brut * 0.78, 2)
    return {
        "brut": brut,
        "net_imposable": net,
        "pas": pas,
        "employee_charges": employee_charges,
        "employer_charges": employer_charges,
    }


def _cumul_items_from_stored_batch(batch_id: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in repo.list_items(batch_id):
        if row.get("item_type") != "cumul":
            continue
        payload = dict(row.get("mapped_payload") or {})
        month_totals = sanitize_stored_month_totals(payload.get("month_totals") or {})
        items.append(
            {
                "item_type": "cumul",
                "mapped_payload": {
                    **payload,
                    "month_totals": month_totals,
                },
            }
        )
    return items


def _cumul_items_from_dsn_content(
    file_name: str, content: bytes
) -> List[Dict[str, Any]]:
    parsed = parse_dsn_files([(file_name, content)])
    return plan_cumul_items(parsed)


def _filename_search_keys(file_names: Sequence[str]) -> List[str]:
    """Génère des clés de recherche souples (Cegid ajoute souvent « (1) » au nom)."""
    import re

    keys: List[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        clean = str(raw or "").strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        keys.append(clean)

    for name in file_names:
        _add(name)
        stem = Path(name).stem
        _add(stem)
        if " (1)" in name:
            _add(name.replace(" (1)", ""))
        m = re.match(r"^(.+?) \(\d+\)$", stem)
        if m:
            _add(m.group(1) + Path(name).suffix)
        parts = stem.split("_")
        if len(parts) >= 2:
            _add("_".join(parts[:2]))
    return keys


def locate_dsn_file(
    file_names: Sequence[str],
    search_dirs: Iterable[Path],
) -> Optional[Path]:
    """Cherche un fichier DSN par nom (exact, variante « (1) », ou wildcard local)."""
    keys = _filename_search_keys(file_names)

    for base in search_dirs:
        if not base.is_dir():
            continue
        for key in keys:
            direct = base / key
            if direct.is_file():
                return direct
            for hit in base.glob(key):
                if hit.is_file():
                    return hit
            stem = Path(key).stem
            for pattern in (f"{stem}*.dsn", f"{stem} (*).dsn"):
                for hit in base.glob(pattern):
                    if hit.is_file():
                        return hit
    return None


def recompute_batch_payroll_totals(
    batch_id: str,
    *,
    dsn_path: Optional[Path] = None,
    prefer_dsn_file: bool = True,
) -> Dict[str, int]:
    """
    Recalcule et upsert les totaux paie d'un batch committed.
    Si dsn_path est fourni (ou trouvé), re-parse le fichier avec le parser corrigé.
    Sinon, normalise les month_totals stockés dans dsn_import_items.
    """
    batch = repo.get_batch(batch_id)
    if not batch:
        raise LookupError(f"Batch {batch_id} introuvable")
    if batch.get("status") != "committed":
        raise ValueError(f"Batch {batch_id} non committed ({batch.get('status')})")

    cumul_items: List[Dict[str, Any]]
    if prefer_dsn_file and dsn_path and dsn_path.is_file():
        cumul_items = _cumul_items_from_dsn_content(dsn_path.name, dsn_path.read_bytes())
    else:
        cumul_items = _cumul_items_from_stored_batch(batch_id)

    if not cumul_items:
        return {}

    resolve_company_id = build_resolve_company_id_from_batch(batch_id)
    return persist_batch_dsn_payroll_totals(
        cumul_items,
        resolve_company_id=resolve_company_id,
        batch_id=batch_id,
    )


def recompute_committed_batches(
    *,
    search_dirs: Optional[Sequence[Path]] = None,
    limit: int = 500,
    prefer_dsn_file: bool = True,
) -> Dict[str, Any]:
    """Recalcule tous les batches committed (avec recherche optionnelle de fichiers DSN)."""
    dirs = list(search_dirs or [])
    batches = repo.list_committed_batches(limit=limit)
    report: Dict[str, Any] = {
        "batches_processed": 0,
        "periods_upserted": 0,
        "from_dsn_file": 0,
        "from_stored_items": 0,
        "details": [],
    }

    for batch in batches:
        batch_id = str(batch["id"])
        file_names = batch.get("file_names") or []
        dsn_path = locate_dsn_file(file_names, dirs) if prefer_dsn_file and dirs else None
        try:
            counts = recompute_batch_payroll_totals(
                batch_id,
                dsn_path=dsn_path,
                prefer_dsn_file=prefer_dsn_file,
            )
        except (LookupError, ValueError):
            continue
        if not counts:
            continue
        periods = sum(counts.values())
        report["batches_processed"] += 1
        report["periods_upserted"] += periods
        if dsn_path:
            report["from_dsn_file"] += 1
            source = str(dsn_path)
        else:
            report["from_stored_items"] += 1
            source = "stored_items"
        report["details"].append(
            {
                "batch_id": batch_id,
                "period_min": batch.get("period_min"),
                "file_names": file_names,
                "source": source,
                "counts": counts,
            }
        )

    return report


def preview_stored_vs_reparsed_totals(
    dsn_path: Path,
) -> Dict[str, Any]:
    """Compare agrégats stockés vs re-parse (outil de diagnostic)."""
    parsed = parse_dsn_files([(dsn_path.name, dsn_path.read_bytes())])
    fresh_items = plan_cumul_items(parsed)

    def _sum(items: List[Dict[str, Any]]) -> Dict[str, float]:
        totals = {
            "brut": 0.0,
            "net_imposable": 0.0,
            "employee_charges": 0.0,
            "employer_charges": 0.0,
        }
        for it in items:
            mt = it.get("mapped_payload", {}).get("month_totals") or {}
            totals["brut"] += float(mt.get("brut") or 0)
            totals["net_imposable"] += float(mt.get("net_imposable") or 0)
            totals["employee_charges"] += float(mt.get("employee_charges") or 0)
            totals["employer_charges"] += float(mt.get("employer_charges") or 0)
        return {k: round(v, 2) for k, v in totals.items()}

    return {
        "file": str(dsn_path),
        "employee_count": len(fresh_items),
        "reparsed": _sum(fresh_items),
    }
