"""Fix ciblé OZEN (MBC mai 2026) — remplace le placeholder approximatif
« absence_non_remuneree 6.5h le jour 4 » (posé par une session antérieure,
jour arbitraire ne correspondant à aucune ligne réelle du bulletin) par les
DEUX absences fractionnaires RÉELLES documentées sur le bulletin Cegid :
  - « Abs. Abs aut nonpayé 130526 1.40h » -> jour 13, 1.40h
  - « Abs. Abs aut nonpayé 220526 4.67h » -> jour 22, 4.67h
Le jour 4 est remis à « travail » (7.5h, template standard OZEN).
Revert-safe : garde seulement si le tier-S baisse strictement.
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
    force = "--force" in sys.argv
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    m = next(x for x in match_employees(cid, refs).matched if x.matricule == "OZEN")

    sched = (admin.table("employee_schedules").select("id,planned_calendar")
             .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
             .maybe_single().execute())
    planned = sched.data["planned_calendar"]
    snap = copy.deepcopy(planned)

    before = tier_s(m)

    cal = planned["calendrier_prevu"]
    by_day = {j.get("jour"): j for j in cal}
    if 4 in by_day:
        by_day[4]["type"] = "travail"
        by_day[4]["heures_prevues"] = 7.5
        by_day[4].pop("heures", None)
        by_day[4]["manuel"] = True
    if 13 in by_day:
        by_day[13]["type"] = "absence_non_remuneree"
        by_day[13]["heures_prevues"] = 1.40
        by_day[13]["manuel"] = True
    else:
        cal.append({"jour": 13, "type": "absence_non_remuneree", "heures_prevues": 1.40, "manuel": True})
    if 22 in by_day:
        by_day[22]["type"] = "absence_non_remuneree"
        by_day[22]["heures_prevues"] = 4.67
        by_day[22]["manuel"] = True
    else:
        cal.append({"jour": 22, "type": "absence_non_remuneree", "heures_prevues": 4.67, "manuel": True})

    planned["calendrier_prevu"] = sorted(cal, key=lambda j: j["jour"])
    admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sched.data["id"]).execute()

    after = tier_s(m)
    keep = force or after < before - 0.01
    if keep:
        print(f"[OZEN] {before:.2f} -> {after:.2f}  GARDÉ")
    else:
        admin.table("employee_schedules").update({"planned_calendar": snap}).eq("id", sched.data["id"]).execute()
        _generate_payslip(m, YEAR, MONTH)
        print(f"[OZEN] {before:.2f} -> {after:.2f}  REVERT (pas d'amélioration)")


if __name__ == "__main__":
    main()
