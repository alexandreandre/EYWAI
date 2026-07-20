"""Corrige le planned_calendar d'un salarié pour les jours de congés payés
mal classés (type 'travail' générique alors que le bulletin réel montre
'Congés payés : DDMMAA' ce jour-là) — cf. skill backtest-paie-auto, catégorie
"calendrier congés payés incomplet".

Usage (depuis backend/):
    .venv/bin/python -m scripts.backtest.fix_conges_payes_calendar MATRICULE1 MATRICULE2 ...
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5

_CP_RANGE_RE = re.compile(
    r"Cong[ée]s pay[ée]s\s*:\s*(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", re.IGNORECASE
)
_CP_DAY_RE = re.compile(r"Cong[ée]s pay[ée]s\s*:\s*(\d{2})(\d{2})(\d{2})(?!-)", re.IGNORECASE)


def find_cp_days(raw_text: str, month: int) -> list[int]:
    days = set()
    # Plages "DDMMYY-DDMMYY" en premier (retire ces occurrences pour éviter
    # que le regex jour-simple ne matche le "DDMMYY" de début de plage).
    ranges_text = raw_text
    for d1, m1, _y1, d2, m2, _y2 in _CP_RANGE_RE.findall(raw_text):
        if int(m1) == month:
            days.update(range(int(d1), int(d2) + 1))
        elif int(m2) == month:
            days.update(range(1, int(d2) + 1))
    ranges_text = _CP_RANGE_RE.sub("", ranges_text)
    for d, m, _y in _CP_DAY_RE.findall(ranges_text):
        if int(m) == month:
            days.add(int(d))
    return sorted(days)


def fix_employee(matricule: str, m, admin) -> list[str]:
    actions = []
    cp_days = find_cp_days(m.reference.raw_text or "", MONTH)
    if not cp_days:
        return actions
    row = (
        admin.table("employee_schedules")
        .select("id,planned_calendar")
        .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
        .single()
        .execute()
        .data
    )
    if not row:
        actions.append("aucune ligne employee_schedules trouvée")
        return actions
    planned = row["planned_calendar"] or {}
    cal = planned.get("calendrier_prevu", [])
    changed = False
    for day in cp_days:
        found = False
        for j in cal:
            if j.get("jour") == day:
                found = True
                if j.get("type") != "conges_payes":
                    old_type = j.get("type")
                    j["type"] = "conges_payes"
                    j["manuel"] = True
                    if not j.get("heures_prevues"):
                        j["heures_prevues"] = 7.5
                    changed = True
                    actions.append(f"jour {day}: {old_type} -> conges_payes")
        if not found:
            cal.append(
                {"jour": day, "type": "conges_payes", "manuel": True, "heures_prevues": 7.5}
            )
            changed = True
            actions.append(f"jour {day}: ajouté (absent) -> conges_payes")
    if changed:
        planned["calendrier_prevu"] = sorted(cal, key=lambda j: j["jour"])
        admin.table("employee_schedules").update({"planned_calendar": planned}).eq(
            "id", row["id"]
        ).execute()
    return actions


def main():
    matricules = sys.argv[1:]
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matches = {m.matricule: m for m in match_employees(cid, refs).matched}

    for matricule in matricules:
        m = matches.get(matricule)
        if not m:
            print(f"[{matricule}] introuvable dans l'appariement")
            continue
        actions = fix_employee(matricule, m, admin)
        print(f"[{matricule}] {len(actions)} action(s):")
        for a in actions:
            print(f"    {a}")


if __name__ == "__main__":
    main()
