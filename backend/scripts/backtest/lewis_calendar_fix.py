"""Corrige les heures journalières du planned_calendar pour qu'elles reflètent la
durée contractuelle (heures_prevues des jours travail/congé = durée_hebdo/5), ce
qui élimine les heures supplémentaires FANTÔMES générées par un calendrier importé
à 7,8 h/j (barème équipe) sur un contrat 35 h. Généraliste, revert-safe.

Usage : .venv/bin/python -m scripts.backtest.lewis_calendar_fix [MAT ...]
Sans argument : tous les salariés non convergés.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.lewis_reconcile import COMPANY, YEAR, MONTH, CONVERGENCE, tier_s

_TYPES_JOUR = {"travail", "conge", "conges_payes"}


def _daily_hours(admin, employee_id) -> float:
    e = (admin.table("employees").select("duree_hebdomadaire")
         .eq("id", employee_id).single().execute().data)
    duree = float(e.get("duree_hebdomadaire") or 35.0)
    return round(duree / 5.0, 2)


def _set_hours(admin, employee_id, hpj: float):
    sched = (admin.table("employee_schedules").select("id,planned_calendar")
             .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    if not sched or not sched.data:
        return None, None
    planned = sched.data.get("planned_calendar") or {}
    snap = copy.deepcopy(planned)
    for j in planned.get("calendrier_prevu", []):
        if j.get("type") in _TYPES_JOUR and float(j.get("heures_prevues") or 0) > 0:
            j["heures_prevues"] = hpj
    admin.table("employee_schedules").update(
        {"planned_calendar": planned}).eq("id", sched.data["id"]).execute()
    return sched.data["id"], snap


def main():
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    wanted = set(sys.argv[1:])
    if wanted:
        matched = [m for m in matched if m.matricule in wanted]
    for m in matched:
        before = tier_s(m)
        if before <= CONVERGENCE:
            print(f"[{m.matricule:12s}] déjà convergé {before:.2f}"); continue
        hpj = _daily_hours(admin, m.employee_id)
        sched_id, snap = _set_hours(admin, m.employee_id, hpj)
        if sched_id is None:
            print(f"[{m.matricule:12s}] pas de calendrier"); continue
        try:
            after = tier_s(m)
        except Exception as exc:
            admin.table("employee_schedules").update({"planned_calendar": snap}).eq("id", sched_id).execute()
            print(f"[{m.matricule:12s}] ERREUR (revert) {exc}"); continue
        if after < before - 0.01:
            print(f"[{m.matricule:12s}] {before:8.2f} -> {after:8.2f}  GARDÉ ({hpj}h/j)")
        else:
            admin.table("employee_schedules").update({"planned_calendar": snap}).eq("id", sched_id).execute()
            print(f"[{m.matricule:12s}] {before:8.2f} -> essai {after:8.2f}  REVERT")


if __name__ == "__main__":
    main()
