"""Ajoute une (ou plusieurs) journée(s) d'absence_non_remuneree au planned_calendar
d'un salarié MBC, revert-safe (garde si tier-S baisse, revert sinon). Sert aux
absences déduites sur le bulletin du mois mais non captées par le réconciliateur
(ex. absences du mois précédent régularisées, « Abs injustifiée DDMM[M-1] »).

Usage : .venv/bin/python -m scripts.backtest.add_absence MAT HEURES [MAT HEURES ...]
Ex :     .venv/bin/python -m scripts.backtest.add_absence KIRMIZI 7
Pose l'absence sur des jours libres (repos/férié) pour ne pas retirer de jour
travaillé (l'absence est une déduction sèche, cf. régul M-1).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.mbc_reconcile import (
    COMPANY, YEAR, MONTH, CONVERGENCE, tier_s, _clear_actual_hours,
)


def _add_absence_hours(admin, employee_id, hours: float):
    sched = (admin.table("employee_schedules").select("id,planned_calendar")
             .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    if not sched or not sched.data:
        return None
    planned = sched.data.get("planned_calendar") or {}
    cal = planned.get("calendrier_prevu", [])
    used = {j.get("jour") for j in cal
            if j.get("type") in ("travail", "conges_payes", "absence_non_remuneree",
                                  "arret_maladie")}
    # journée(s) de 7 h chacune ; répartir le reliquat sur une journée fractionnaire
    remaining = round(hours, 2)
    day = 1
    while remaining > 0.001:
        while day in used and day <= 31:
            day += 1
        if day > 31:
            break
        h = 7.0 if remaining >= 7.0 else remaining
        by_day = {j.get("jour"): j for j in cal}
        j = by_day.get(day)
        if j is None:
            cal.append({"jour": day, "type": "absence_non_remuneree",
                        "manuel": True, "heures_prevues": round(h, 2)})
        else:
            j["type"] = "absence_non_remuneree"; j["manuel"] = True
            j["heures_prevues"] = round(h, 2)
        used.add(day)
        remaining = round(remaining - h, 2)
        day += 1
    planned["calendrier_prevu"] = sorted(cal, key=lambda j: j["jour"])
    admin.table("employee_schedules").update(
        {"planned_calendar": planned}).eq("id", sched.data["id"]).execute()
    return sched.data["id"]


def main():
    args = sys.argv[1:]
    pairs = [(args[i], float(args[i + 1])) for i in range(0, len(args) - 1, 2)]
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = {m.matricule: m for m in match_employees(cid, refs).matched}
    for mat, hours in pairs:
        m = matched.get(mat)
        if not m:
            print(f"[{mat}] introuvable"); continue
        before = tier_s(m)
        sched = (admin.table("employee_schedules").select("id,planned_calendar")
                 .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
                 .maybe_single().execute())
        snap = copy.deepcopy(sched.data.get("planned_calendar")) if sched and sched.data else None
        sched_id = sched.data["id"] if sched and sched.data else None
        try:
            _add_absence_hours(admin, m.employee_id, hours)
            _clear_actual_hours(admin, m.employee_id)
            after = tier_s(m)
        except Exception as exc:
            if sched_id and snap is not None:
                admin.table("employee_schedules").update({"planned_calendar": snap}).eq("id", sched_id).execute()
            print(f"[{mat}] ERREUR (revert) {exc}"); continue
        if after < before - 0.01:
            print(f"[{mat}] {before:.2f} -> {after:.2f}  GARDÉ (+{hours}h abs)")
        else:
            if sched_id and snap is not None:
                admin.table("employee_schedules").update({"planned_calendar": snap}).eq("id", sched_id).execute()
            print(f"[{mat}] {before:.2f} -> essai {after:.2f}  REVERT")


if __name__ == "__main__":
    main()
