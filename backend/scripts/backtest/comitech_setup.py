#!/usr/bin/env python3
"""Setup data-driven Comitech (plasturgie idcc 0292) pour backtest 2026.

Config PERMANENTE (salaries "heures" non-cadres) :
  - specificites_paie.salaire_hors_hs_structurelles = True (contrat 39h).
  - mutuelle isolee GAN 2026 (EMU3 29.24/29.24), part patronale NON reintegree
    a l'impot (le reel Comitech ne reintegre pas).
  - prevoyance non cadre 0.465%/0.465% brut_plafonne, forfait social 8%.
  - salaire_de_base.valeur = SALAIRE DE BASE 151.67h reel par periode
    (jan-mars / avr-juin, augmentation en avril).

Variables MENSUELLES : auto-derivees des bulletins reels (scratchpad extract JSON)
pour famille (-98.12), transport, prime poste difficile (60), HS conjoncturelles,
conges payes. Cas complexes (absences non payees, paternite, maintien) : OVERRIDE.

Usage: .venv/bin/python -m scripts.backtest.comitech_setup --month 2 [--emp JEAN]
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from app.core.database import get_supabase_admin_client, supabase
from scripts.backtest.employee_matching import resolve_company_id

MARKER = "BACKTEST_AUTO_COMITECH"
MUT_ISOLE_ID = "d7131a63-7fef-417b-bb5d-f0e6081e457d"  # GAN Isolé 2026 (EMU3)
EXTRACT = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
               "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad/comitech_extract.json")

HEURES = [
    "BOUFRIDA", "CASANOVA", "ELIDRISSI", "GENAND", "GOYAT", "GROS", "JEAN",
    "LACAQUE", "OUASSIF", "POINSIGNON", "SOW", "TROUILLOUD", "VALLAT",
    "LEBRUN", "MARTINEZ", "BOUDJEMAA",
]
FAMILLE = {"BOUFRIDA", "ELIDRISSI", "GROS", "OUASSIF", "TROUILLOUD"}  # -98.12/mois
NO_MUTUELLE = {"VALLAT", "LACAQUE", "POINSIGNON", "LEBRUN", "MARTINEZ", "BOUDJEMAA"}
NO_PREVOYANCE = {"MARTINEZ", "BOUDJEMAA"}  # embauches mai, a confirmer

# Date "Ancienneté" reelle du bulletin (YYYY-MM-DD). Corrige la resolution de la
# date d'anciennete pour la prime (reprise CASANOVA 2006, boundary VALLAT 3 ans).
SENIORITY: Dict[str, str] = {
    "BOUFRIDA": "2019-10-01", "CASANOVA": "2006-11-02", "ELIDRISSI": "2004-05-03",
    "GENAND": "2000-01-03", "GOYAT": "2003-07-15", "GROS": "1996-06-04",
    "JEAN": "2025-05-28", "LACAQUE": "2026-01-19", "OUASSIF": "2018-02-01",
    "POINSIGNON": "2010-07-07", "SOW": "2025-04-22", "TROUILLOUD": "2014-05-05",
    "VALLAT": "2022-11-21",
}

PERIOD_BASE: Dict[str, tuple] = {
    "BOUFRIDA": (1887.69, 1924.54), "CASANOVA": (1933.22, 1971.86),
    "ELIDRISSI": (1933.22, 1981.57), "GENAND": (2063.66, 2123.53),
    "GOYAT": (1933.22, 1952.60), "GROS": (2062.71, 2114.28),
    "JEAN": (1880.70, 1918.32), "LACAQUE": (1926.21, 1964.73),
    "OUASSIF": (1933.79, 1972.47), "POINSIGNON": (2221.38, 2265.80),
    "SOW": (1850.37, 1887.38), "TROUILLOUD": (2002.05, 2052.09),
    "VALLAT": (1899.85, 1943.50), "LEBRUN": (1964.73, 1964.73),
    "MARTINEZ": (1820.04, 1820.04), "BOUDJEMAA": (2093.05, 2093.05),
}

# Overrides cas complexes : {(mois,mat): {"abs":{jour:heures}, "skip_auto_cp":bool,
# "extra_inputs":[(name,amt,taxed,taxable)], "maintien": ...}}. Best effort.
OVERRIDE: Dict[tuple, Dict[str, Any]] = {
    # ELIDRISSI : prime exceptionnelle 60 (parse fev = artefact Plafond Secu).
    (2, "ELIDRISSI"): {"extra_inputs": [("Prime exceptionnelle", 60.0, True, True)]},
    # SOW : absences non payees en heures PARTIELLES (1.7h/jour) non modelisables
    # via calendrier jour-plein -> KNOWN_GAP. Pas d'override (evite sur-deduction).
}


def _base_for_month(mat: str, month: int):
    pb = PERIOD_BASE.get(mat)
    return None if not pb else (pb[0] if month <= 3 else pb[1])


def _load_extract():
    return json.load(open(EXTRACT)) if EXTRACT.exists() else {}


def _days_from_label(lib: str) -> List[int]:
    """Extrait les jours (numero) d'un libelle CP/absence. Gere ranges DDMMYY-DDMMYY."""
    dates = re.findall(r"(\d{6})", lib)
    if not dates:
        return []
    if "-" in lib and len(dates) == 2:
        d1 = int(dates[0][:2]); d2 = int(dates[1][:2])
        if d1 <= d2:
            return list(range(d1, d2 + 1))
    return [int(x[:2]) for x in dates]


def _auto_inputs(mat: str, month: int, extract) -> Dict[str, Any]:
    """Derive cp/hs25/inputs depuis le bulletin reel parse."""
    e = extract.get(str(month), {}).get(mat)
    cfg: Dict[str, Any] = {"cp": [], "hs25": 0.0, "hs50": 0.0, "abs": {}, "inputs": []}
    if not e:
        return cfg
    for r in e["rub"]:
        lib = (r["lib"] or ""); low = lib.lower()
        if "heures supplémentaires 50" in low and r.get("base"):
            try:
                cfg["hs50"] += float(r["base"])
            except (TypeError, ValueError):
                pass
        elif "congés payés :" in low:
            for dnum in _days_from_label(lib):
                if 1 <= dnum <= 31 and dnum not in cfg["cp"]:
                    cfg["cp"].append(dnum)
        elif "heures supplémentaires 25" in low and r.get("base"):
            try:
                cfg["hs25"] += float(r["base"])  # HS conjoncturelle explicite
            except (TypeError, ValueError):
                pass
        elif low.startswith("participation") and r.get("base") not in (None,):
            # Participation numéraire (mai) : non soumise cotisations, IMPOSABLE.
            # Format + traitement identiques à MBC (mbc_reconcile).
            amt = float(r["base"])
            if amt > 0:
                cfg["inputs"].append(("Participation 2025 — numéraire", amt, False, True))
        elif "poste difficile" in low:
            cfg["inputs"].append(("Prime poste difficile", 60.0, True, True))
        elif "poste injection" in low:
            amt = float(r["ms"]) if r.get("ms") not in (None,) and 0 < float(r["ms"]) < 500 else 90.0
            cfg["inputs"].append(("Prime poste injection", amt, True, True))
        elif "exceptionnelle" in low and r.get("ms") not in (None,):
            amt = float(r["ms"])
            if 0 < amt < 1000:  # sinon artefact Plafond Sécu (ex 4005) -> OVERRIDE
                cfg["inputs"].append(("Prime exceptionnelle", amt, True, True))
        elif low.startswith("acompte") and r.get("base") not in (None,):
            amt = abs(float(r["base"]))
            if 0 < amt < 5000:
                cfg["inputs"].append(("Acompte", -amt, False, False))
        elif "remboursement" in low and "pret" in low.replace("ê", "e"):
            # Remboursement pret (net-only) : base=-1, taux=montant.
            amt = abs(float(r["ts"])) if r.get("ts") else abs(float(r.get("ms") or 0))
            if 0 < amt < 5000:
                cfg["inputs"].append(("Acompte", -amt, False, False))
        elif "transport" in low and r.get("ms") not in (None,):
            amt = float(r["ms"])
            if 0 < amt < 500:
                cfg["inputs"].append(("Indemnité de transport", amt, False, False))
    if e.get("acompte_part"):
        # Avance sur participation déjà versée (net-only), même canal que MBC.
        cfg["inputs"].append(("Avance participation 2025 (déjà versée)", -float(e["acompte_part"]), False, False))
    if mat in FAMILLE:
        cfg["inputs"].append(("GAN MUTUELLE FAMILLE", -98.12, False, False))
    return cfg


def _emp_map(company_id: str) -> Dict[str, dict]:
    rows = (supabase.table("employees")
            .select("id, matricule, salaire_de_base, specificites_paie, is_forfait_jour")
            .eq("company_id", company_id).execute().data)
    return {r["matricule"]: r for r in rows}


def _apply_permanent(admin, emp: dict, month: int = 1) -> None:
    sp = copy.deepcopy(emp.get("specificites_paie") or {})
    sen = SENIORITY.get(emp["matricule"])
    if sen:
        admin.table("employees").update({"seniority_reference_date": sen}).eq("id", emp["id"]).execute()
    mat = emp["matricule"]
    sp["salaire_hors_hs_structurelles"] = True
    # Reintegration mutuelle patronale au net imposable : demarre avril 2026.
    reintegree = month >= 4
    if mat in NO_MUTUELLE:
        sp["mutuelle"] = {"adhesion": False}
    else:
        sp["mutuelle"] = {"adhesion": True, "pack_couverture": "isole",
                          "mutuelle_type_ids": [MUT_ISOLE_ID], "lignes_specifiques": [],
                          "part_patronale_reintegree_impot": reintegree}
    if mat in NO_PREVOYANCE:
        sp["prevoyance"] = {"adhesion": False}
    else:
        sp["prevoyance"] = {"adhesion": True, "lignes_specifiques": [
            {"id": "prevoyance_dsn", "base": "brut_plafonne",
             "libelle": "Prévoyance (import DSN)",
             "salarial": 0.00465, "patronal": 0.00465, "forfait_social": 0.08}]}
    admin.table("employees").update({"specificites_paie": sp}).eq("id", emp["id"]).execute()


def _set_base(admin, emp: dict, base: float) -> None:
    sdb = copy.deepcopy(emp.get("salaire_de_base") or {"type": "mensuel"})
    sdb["type"] = sdb.get("type", "mensuel"); sdb["valeur"] = base
    admin.table("employees").update({"salaire_de_base": sdb}).eq("id", emp["id"]).execute()


def _set_calendar(admin, emp_id, year, month, cp_days, abs_days):
    sch = (admin.table("employee_schedules").select("id,planned_calendar")
           .match({"employee_id": emp_id, "year": year, "month": month})
           .maybe_single().execute())
    if not sch or not sch.data:
        return "NO_SCHEDULE"
    import calendar as _cal
    dim = _cal.monthrange(year, month)[1]
    planned = copy.deepcopy(sch.data.get("planned_calendar") or {})
    cal = [j for j in planned.get("calendrier_prevu", []) if 1 <= j.get("jour", 0) <= dim]
    by_day = {j.get("jour"): j for j in cal}
    actions = []
    for d in [x for x in cp_days if 1 <= x <= dim]:
        j = by_day.get(d)
        if j is None:
            cal.append({"jour": d, "type": "conges_payes", "manuel": True, "heures_prevues": 7.0})
        elif j.get("type") == "travail":
            j["type"] = "conges_payes"; j["manuel"] = True
        actions.append(f"cp:{d}")
    for d, h in abs_days.items():
        if not 1 <= d <= dim:
            continue
        j = by_day.get(d)
        if j is None:
            cal.append({"jour": d, "type": "absence_non_remuneree", "manuel": True, "heures_prevues": round(h, 2)})
        elif j.get("type") == "travail":
            j["type"] = "absence_non_remuneree"; j["manuel"] = True; j["heures_prevues"] = round(h, 2)
        actions.append(f"abs:{d}={h}")
    planned["calendrier_prevu"] = sorted(cal, key=lambda x: x["jour"])
    admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sch.data["id"]).execute()
    return ",".join(actions) or "no-cal-change"


def _clear_actual(admin, emp_id, year, month) -> bool:
    sch = (admin.table("employee_schedules").select("id,actual_hours")
           .match({"employee_id": emp_id, "year": year, "month": month})
           .maybe_single().execute())
    if not sch or not sch.data:
        return False
    ah = sch.data.get("actual_hours") or {}
    if not ah.get("calendrier_reel"):
        return False
    ah = copy.deepcopy(ah); ah["calendrier_reel"] = []
    admin.table("employee_schedules").update({"actual_hours": ah}).eq("id", sch.data["id"]).execute()
    return True


def _clear_inputs(admin, emp_id, year, month):
    admin.table("monthly_inputs").delete().match(
        {"employee_id": emp_id, "year": year, "month": month}
    ).like("description", f"%{MARKER}%").execute()


def _insert_input(admin, emp_id, company_id, year, month, name, amount, taxed, taxable, qty=None):
    admin.table("monthly_inputs").insert({
        "employee_id": emp_id, "company_id": company_id, "year": year, "month": month,
        "name": name, "description": f"Backtest Comitech {month:02d}/{year} {MARKER}",
        "amount": amount, "is_socially_taxed": taxed, "is_taxable": taxable,
        "payroll_quantity": qty,
    }).execute()


def apply_month(company: str, year: int, month: int, only=None, permanent_only=False):
    admin = get_supabase_admin_client()
    company_id = resolve_company_id(company)
    emps = _emp_map(company_id)
    extract = _load_extract()
    targets = only or HEURES
    for mat in targets:
        emp = emps.get(mat)
        if not emp:
            print(f"[{mat}] introuvable"); continue
        if mat in HEURES:
            _apply_permanent(admin, emp, month)
            base = _base_for_month(mat, month)
            if base is not None:
                _set_base(admin, emp, base)
        if permanent_only:
            print(f"[{mat}] permanent base={_base_for_month(mat, month)}"); continue
        cfg = _auto_inputs(mat, month, extract)
        ov = OVERRIDE.get((month, mat), {})
        abs_days = dict(cfg["abs"]); abs_days.update(ov.get("abs", {}))
        cp = [] if ov.get("skip_auto_cp") else cfg["cp"]
        _clear_actual(admin, emp["id"], year, month)
        cal_res = _set_calendar(admin, emp["id"], year, month, cp, abs_days)
        _clear_inputs(admin, emp["id"], year, month)
        inputs = list(cfg["inputs"]) + list(ov.get("extra_inputs", []))
        for name, amount, taxed, taxable in inputs:
            _insert_input(admin, emp["id"], company_id, year, month, name, amount, taxed, taxable)
        if cfg["hs25"]:
            _insert_input(admin, emp["id"], company_id, year, month,
                          "Heures supplementaires conjoncturelles", 0.0, True, True, round(cfg["hs25"], 2))
        if cfg.get("hs50"):
            _insert_input(admin, emp["id"], company_id, year, month,
                          "Heures supplementaires conjoncturelles 50%", 0.0, True, True, round(cfg["hs50"], 2))
        print(f"[{mat}] base={_base_for_month(mat, month)} cp={cp} abs={abs_days} "
              f"hs25={round(cfg['hs25'],2)} hs50={round(cfg.get('hs50',0),2)} inputs={[i[0] for i in inputs]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default="Comitech Composite")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--emp", nargs="*", default=None)
    ap.add_argument("--permanent-only", action="store_true")
    a = ap.parse_args()
    apply_month(a.company, a.year, a.month, only=a.emp, permanent_only=a.permanent_only)


if __name__ == "__main__":
    main()
