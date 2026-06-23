#!/usr/bin/env python3
"""
Import ponctuel de l'historique des visites médicales depuis un fichier Excel ou CSV.

Usage (depuis backend/) :
  python scripts/import_medical_history.py --company-id UUID --file historique.xlsx --dry-run
  python scripts/import_medical_history.py --company-id UUID --file historique.csv

Colonnes attendues (noms flexibles, insensibles à la casse) :
  - last_name / nom + first_name / prenom
  - visit_type / type_visite / type  (VIP, SIR, Reprise, etc.)
  - visit_date / date_visite / date  (YYYY-MM-DD ou format Excel)

Prérequis : SUPABASE_URL + SUPABASE_SERVICE_KEY (ou SUPABASE_KEY service role) dans backend/.env

Après import, le script recalcule les prochaines obligations (compute_obligations_for_employee)
pour chaque salarié touché.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import get_supabase_admin_client  # noqa: E402
from app.modules.medical_follow_up.application.service import (  # noqa: E402
    compute_obligations_for_employee,
)

VISIT_TYPE_ALIASES: Dict[str, str] = {
    "vip": "vip",
    "visite vip": "vip",
    "visite d information et de prevention": "vip",
    "visite d'information et de prévention": "vip",
    "sir": "sir",
    "visite sir": "sir",
    "suivi individuel renforce": "sir",
    "reprise": "reprise",
    "visite de reprise": "reprise",
    "mi carriere": "mi_carriere_45",
    "mi-carriere": "mi_carriere_45",
    "mi_carriere_45": "mi_carriere_45",
    "45 ans": "mi_carriere_45",
    "demande": "demande",
    "a la demande": "demande",
    "aptitude sir": "aptitude_sir_avant_affectation",
    "aptitude_sir_avant_affectation": "aptitude_sir_avant_affectation",
}

TRIGGER_BY_VISIT: Dict[str, str] = {
    "vip": "periodicite_vip",
    "sir": "periodicite_sir",
    "reprise": "arret_long",
    "mi_carriere_45": "age_45",
    "demande": "demande",
    "aptitude_sir_avant_affectation": "poste_sir",
}


def _normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _normalize_visit_type(raw: str) -> Optional[str]:
    key = _normalize_key(raw)
    key = key.replace("visite_", "").replace("type_", "")
    if key in VISIT_TYPE_ALIASES:
        return VISIT_TYPE_ALIASES[key]
    compact = key.replace("_", " ")
    return VISIT_TYPE_ALIASES.get(compact)


def _parse_date(raw: Any) -> Optional[date]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _load_rows(file_path: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xltx"}:
        import pandas as pd

        df = pd.read_excel(file_path, dtype=str)
        df = df.fillna("")
        headers = [str(c) for c in df.columns]
        rows = [dict(zip(headers, row)) for row in df.values.tolist()]
        return headers, rows

    with file_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return headers, rows


def _row_get(row: Dict[str, Any], *candidates: str) -> str:
    normalized = {_normalize_key(str(k)): v for k, v in row.items()}
    for candidate in candidates:
        key = _normalize_key(candidate)
        if key in normalized and str(normalized[key]).strip():
            return str(normalized[key]).strip()
    return ""


def _build_employee_index(company_id: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    supabase = get_supabase_admin_client()
    res = (
        supabase.table("employees")
        .select("id, first_name, last_name")
        .eq("company_id", company_id)
        .execute()
    )
    by_name: Dict[str, str] = {}
    by_matricule: Dict[str, str] = {}
    for emp in res.data or []:
        emp_id = emp["id"]
        last = (emp.get("last_name") or "").strip().lower()
        first = (emp.get("first_name") or "").strip().lower()
        if last and first:
            by_name[f"{last}|{first}"] = emp_id
            by_name[f"{first}|{last}"] = emp_id
    return by_name, by_matricule


def _resolve_employee_id(
    row: Dict[str, Any],
    by_name: Dict[str, str],
    by_matricule: Dict[str, str],
) -> Optional[str]:
    matricule = _row_get(row, "matricule", "employee_number", "numero")
    if matricule:
        return by_matricule.get(matricule.lower())

    last_name = _row_get(row, "last_name", "nom", "nom_salarie")
    first_name = _row_get(row, "first_name", "prenom", "prenom_salarie")
    if last_name and first_name:
        return by_name.get(f"{last_name.lower()}|{first_name.lower()}")
    return None


def _insert_historical_obligation(
    company_id: str,
    employee_id: str,
    visit_type: str,
    visit_date: date,
    dry_run: bool,
) -> str:
    trigger_type = TRIGGER_BY_VISIT.get(visit_type, "periodicite_vip")
    payload = {
        "company_id": company_id,
        "employee_id": employee_id,
        "visit_type": visit_type,
        "trigger_type": trigger_type,
        "due_date": visit_date.isoformat(),
        "priority": 2,
        "status": "realisee",
        "completed_date": visit_date.isoformat(),
        "rule_source": "legal",
        "justification": "Import historique Excel",
    }
    if dry_run:
        return "dry_run"
    supabase = get_supabase_admin_client()
    res = supabase.table("medical_follow_up_obligations").insert(payload).execute()
    if not res.data:
        return "error"
    return res.data[0]["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Import historique visites médicales")
    parser.add_argument("--company-id", required=True, help="UUID entreprise")
    parser.add_argument("--file", required=True, type=Path, help="Fichier Excel ou CSV")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simuler sans écrire en base",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Fichier introuvable : {args.file}", file=sys.stderr)
        return 1

    headers, rows = _load_rows(args.file)
    print(f"Fichier : {args.file} ({len(rows)} lignes, colonnes : {', '.join(headers)})")

    by_name, by_matricule = _build_employee_index(args.company_id)
    ok = 0
    skipped = 0
    errors: List[str] = []
    touched_employees: set[str] = set()

    for index, row in enumerate(rows, start=2):
        employee_id = _resolve_employee_id(row, by_name, by_matricule)
        if not employee_id:
            skipped += 1
            errors.append(f"Ligne {index} : salarié introuvable ({row})")
            continue

        visit_raw = _row_get(row, "visit_type", "type_visite", "type", "visite")
        visit_type = _normalize_visit_type(visit_raw) if visit_raw else None
        if not visit_type:
            skipped += 1
            errors.append(f"Ligne {index} : type de visite invalide ({visit_raw!r})")
            continue

        visit_date = _parse_date(_row_get(row, "visit_date", "date_visite", "date"))
        if not visit_date:
            skipped += 1
            errors.append(f"Ligne {index} : date invalide")
            continue

        try:
            result = _insert_historical_obligation(
                args.company_id,
                employee_id,
                visit_type,
                visit_date,
                args.dry_run,
            )
            if result == "error":
                skipped += 1
                errors.append(f"Ligne {index} : échec insertion")
            else:
                ok += 1
                touched_employees.add(employee_id)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            errors.append(f"Ligne {index} : {exc}")

    if not args.dry_run and touched_employees:
        print(f"Recalcul des obligations pour {len(touched_employees)} salarié(s)...")
        for employee_id in sorted(touched_employees):
            compute_obligations_for_employee(args.company_id, employee_id)

    print(f"\nRésumé : {ok} importée(s), {skipped} ignorée(s)")
    if args.dry_run:
        print("(mode dry-run — aucune écriture)")
    if errors:
        print("\nDétail des lignes ignorées :")
        for err in errors[:50]:
            print(f"  - {err}")
        if len(errors) > 50:
            print(f"  ... et {len(errors) - 50} autre(s)")

    return 0 if ok > 0 or (args.dry_run and skipped == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
