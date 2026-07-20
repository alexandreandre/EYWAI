"""Patch revert-safe d'un jour précis du planned_calendar (heures_prevues et/ou type).

Complète mbc_cal.py (qui ne patch que TOUS les jours travail en masse) pour le cas
d'un ajustement fin sur un seul jour, ancré sur une donnée réelle du bulletin
(ex. OZEN mai 2026 : fusionner deux absences fractionnaires réelles documentées
« Abs. Abs aut nonpayé 130526 1.40h » + « 220526 4.67h » = 6.07h, au lieu d'un
placeholder approximatif 6.5h posé par une session antérieure).

Usage (depuis backend/) :
  .venv/bin/python -m scripts.backtest.mbc_day_patch MAT JOUR HEURES [--type TYPE] [--force]
  (revert-safe : garde si tier-S baisse strictement, sinon revert automatique)
"""
from __future__ import annotations
import copy, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5


def tier_s(m):
    _generate_payslip(m, YEAR, MONTH)
    for r in compare_matches([m], YEAR, MONTH, thresholds=default_thresholds(),
                              systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")


def main():
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    new_type = None
    if "--type" in args:
        i = args.index("--type")
        new_type = args[i + 1]
        args = args[:i] + args[i + 2:]
    matricule, jour_s, heures_s = args[0], args[1], args[2]
    jour = int(jour_s)
    heures = float(heures_s)

    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = [m for m in match_employees(cid, refs).matched if m.matricule == matricule]
    if not matched:
        print("Matricule introuvable:", matricule); return
    m = matched[0]

    sched = (admin.table("employee_schedules").select("id,planned_calendar")
             .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    if not sched or not sched.data:
        print(f"{m.matricule}: pas de schedule"); return

    planned = sched.data.get("planned_calendar") or {}
    cal = planned.get("calendrier_prevu", [])
    snap = copy.deepcopy(planned)  # snapshot profond obligatoire avant toute mutation

    before = tier_s(m)
    found = False
    for j in cal:
        if j.get("jour") == jour:
            found = True
            j["heures_prevues"] = heures
            if new_type:
                j["type"] = new_type
            j["manuel"] = True
    if not found:
        print(f"Jour {jour} introuvable dans le calendrier de {matricule}"); return

    planned["calendrier_prevu"] = cal
    admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sched.data["id"]).execute()
    after = tier_s(m)

    if force or after < before - 0.01:
        print(f"[{m.matricule}] jour {jour} -> {heures}h{' type='+new_type if new_type else ''}  "
              f"tierS {before:.2f} -> {after:.2f}  GARDÉ")
    else:
        admin.table("employee_schedules").update({"planned_calendar": snap}).eq("id", sched.data["id"]).execute()
        rev = tier_s(m)
        print(f"[{m.matricule}] jour {jour} -> essai {after:.2f} -> REVERT {rev:.2f}")


if __name__ == "__main__":
    main()
