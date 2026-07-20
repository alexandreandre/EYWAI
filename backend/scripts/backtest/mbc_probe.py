"""Sonde ciblée : pour chaque matricule, imprime duree_hebdo, flag
salaire_hors_hs_structurelles, jours CP/JTC/absence du calendrier, et si le
bulletin réel contient une ligne HS 25 % structurelle.
"""
from __future__ import annotations
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins

COMPANY, YEAR, MONTH = "Mont Blanc Composite", 2026, 5
_HS25 = re.compile(r"H\. supp majorées à 25 %\s+([\d]+\.\d{2})\s")
_BASE = re.compile(r"SALAIRE DE BASE\s+([\d]+\.\d{2})\s")

def main():
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    wanted = set(sys.argv[1:])
    for m in matched:
        if wanted and m.matricule not in wanted:
            continue
        emp = (admin.table("employees").select("specificites_paie,duree_hebdomadaire")
               .eq("id", m.employee_id).single().execute().data)
        sp = emp.get("specificites_paie") or {}
        flag = bool(sp.get("salaire_hors_hs_structurelles"))
        duree = float(emp.get("duree_hebdomadaire") or 35)
        struct_qty = round((duree - 35) * 52 / 12, 2) if duree > 35 else 0.0
        txt = m.reference.raw_text or ""
        hs = [float(q) for q in _HS25.findall(txt)]
        base = _BASE.findall(txt)
        sched = (admin.table("employee_schedules").select("planned_calendar,actual_hours")
                 .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
                 .maybe_single().execute())
        cal_days = {"CP": [], "JTC/abs": [], "maladie": []}
        ah_empty = True
        if sched and sched.data:
            pc = (sched.data.get("planned_calendar") or {}).get("calendrier_prevu", [])
            for j in pc:
                t = j.get("type")
                if t == "conges_payes": cal_days["CP"].append(j.get("jour"))
                elif t == "absence_justifiee": cal_days["JTC/abs"].append(j.get("jour"))
                elif t == "arret_maladie": cal_days["maladie"].append(j.get("jour"))
            ah = sched.data.get("actual_hours") or {}
            ah_empty = not (ah.get("calendrier_reel"))
        match_struct = any(abs(q - struct_qty) < 0.05 for q in hs) if struct_qty else False
        print(f"{m.matricule:12s} duree={duree:5.2f} flag={int(flag)} baseBull={base[:1]} "
              f"structQty={struct_qty} HS={hs} matchStruct={int(match_struct)} "
              f"CP={cal_days['CP']} JTCabs={cal_days['JTC/abs']} mal={cal_days['maladie']} AHempty={int(ah_empty)}",
              flush=True)

if __name__ == "__main__":
    main()
