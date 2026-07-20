"""Cat 7 — arrêt maladie SANS maintien : pose les jours ouvrés de la plage
« Absence maladie DDMMYY-DDMMYY » en absence_non_remuneree (7 h légal), vide le
pointage, régénère, compare, garde/revert automatiquement.

Réservé aux salariés dont le bulletin n'a PAS de ligne « Maintien de salaire »
(sinon → chantier moteur maintien). Usage :
    .venv/bin/python -m scripts.backtest.cat7_arret MATRICULE [MATRICULE ...]
"""
from __future__ import annotations

import copy
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.mbc_reconcile import (
    COMPANY, YEAR, MONTH, CONVERGENCE,
    take_snapshot, restore_snapshot, tier_s, _clear_actual_hours,
)

_MAL_RANGE_RE = re.compile(
    r"Absence maladie\s+(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", re.IGNORECASE
)
_MAINTIEN_RE = re.compile(r"Maintien de salaire", re.IGNORECASE)


def _arret_weekdays(text: str) -> list[int]:
    days: set[int] = set()
    for d1, m1, _y, d2, m2, _y2 in _MAL_RANGE_RE.findall(text):
        d1i, d2i = int(d1), int(d2)
        start = d1i if int(m1) == MONTH else 1
        end = d2i if int(m2) == MONTH else 31
        for d in range(start, end + 1):
            if datetime.date(YEAR, MONTH, d).weekday() < 5:
                days.add(d)
    return sorted(days)


def _pose_absence(admin, employee_id, days: list[int]) -> list[str]:
    sched = (admin.table("employee_schedules").select("id,planned_calendar")
             .match({"employee_id": employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    if not sched or not sched.data:
        return []
    planned = sched.data.get("planned_calendar") or {}
    cal = planned.get("calendrier_prevu", [])
    by_day = {j.get("jour"): j for j in cal}
    for d in days:
        j = by_day.get(d)
        if j is None:
            cal.append({"jour": d, "type": "absence_non_remuneree",
                        "manuel": True, "heures_prevues": 7.0})
        else:
            j["type"] = "absence_non_remuneree"
            j["manuel"] = True
            j["heures_prevues"] = 7.0
    planned["calendrier_prevu"] = sorted(cal, key=lambda j: j["jour"])
    admin.table("employee_schedules").update({"planned_calendar": planned}).eq(
        "id", sched.data["id"]).execute()
    return [f"absence maladie jours {days}"]


def main():
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    wanted = set(sys.argv[1:])
    if wanted:
        matched = [m for m in matched if m.matricule in wanted]

    for m in matched:
        text = m.reference.raw_text or ""
        if _MAINTIEN_RE.search(text):
            print(f"[{m.matricule:14s}] SKIP (maintien présent → chantier moteur)")
            continue
        days = _arret_weekdays(text)
        if not days:
            print(f"[{m.matricule:14s}] SKIP (pas d'arrêt maladie)")
            continue
        before = tier_s(m)
        if before <= CONVERGENCE:
            print(f"[{m.matricule:14s}] déjà convergé {before:.2f}")
            continue
        snap = take_snapshot(admin, m.employee_id, m.company_id)
        try:
            actions = _pose_absence(admin, m.employee_id, days)
            actions += _clear_actual_hours(admin, m.employee_id)
            after = tier_s(m)
        except Exception as exc:
            restore_snapshot(admin, m.employee_id, m.company_id, snap)
            print(f"[{m.matricule:14s}] ERREUR (revert) {exc}")
            continue
        if after < before - 0.01:
            print(f"[{m.matricule:14s}] {before:8.2f} -> {after:8.2f}  amélioré  {actions}")
        else:
            restore_snapshot(admin, m.employee_id, m.company_id, snap)
            rev = tier_s(m)
            print(f"[{m.matricule:14s}] {before:8.2f} -> {rev:8.2f}  revert (essai={after:.2f})")


if __name__ == "__main__":
    main()
