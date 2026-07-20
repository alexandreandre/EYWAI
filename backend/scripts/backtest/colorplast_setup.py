#!/usr/bin/env python3
"""Setup data-driven d'un mois Colorplast pour backtest (jan-juin 2026).

Applique, pour chaque salarie d'un mois : le taux de base historique, les jours
CP / absences non remunerees au calendrier, et les monthly_inputs variables
(HS conjoncturelles 25/50, primes, transport, note de frais, acompte).
Idempotent : purge les monthly_inputs marques BACKTEST_AUTO avant reinsertion.

Les donnees par mois sont dans MONTH_DATA (rempli au fil du backtest, ancre
sur les bulletins reels + DSN).

Usage:
    .venv/bin/python -m scripts.backtest.colorplast_setup --month 1 [--emp BUGNY COTTE]
"""
from __future__ import annotations

import argparse
import copy
from typing import Any, Dict, List

from app.core.database import get_supabase_admin_client, supabase
from scripts.backtest.employee_matching import resolve_company_id

MARKER = "BACKTEST_AUTO_COLORPLAST"

# ---------------------------------------------------------------------------
# Donnees par mois. base = valeur mensuelle (151.67h) du taux historique.
# cp = liste des jours (numero) en conges payes. abs = {jour: heures} absence
# non remuneree. hs25/hs50 = quantite HS conjoncturelles. inputs = liste de
# (name, amount, is_socially_taxed, is_taxable).
# ---------------------------------------------------------------------------
MONTH_DATA: Dict[int, Dict[str, Dict[str, Any]]] = {
    1: {
        "BUGNY": {"base": 2123.38, "cp": [2], "hs25": 12.0, "hs50": 8.5, "mut_reint": False,
                  "inputs": [("Prime exceptionnelle", 150.0, True, True),
                             ("Remboursement de notes de frais", 84.59, False, False),
                             ("Acompte", -2369.63, False, False)]},
        "COTTE": {"base": 1964.00, "cp": [2], "abs": {21: 3.14},
                  "inputs": [("Prime exceptionnelle", 100.0, True, True),
                             ("Acompte", -1814.87, False, False)]},
        "ESPINOSA": {"base": 2328.00, "cp": [2], "hs25": 12.0, "hs50": 4.0, "mut_reint": False,
                     "inputs": [("Indemnite de transport", 100.0, False, False),
                                ("GAN MUTUELLE FAMILLE", -98.13, False, False),
                                ("Acompte", -2365.99, False, False)]},
        "GAUTHERON": {"base": 1964.00, "cp": [2, 23], "abs": {13: 2.24, 14: 7.63}, "mut_reint": False,
                      "inputs": [("Prime exceptionnelle", 100.0, True, True),
                                 ("GAN MUTUELLE FAMILLE", -98.13, False, False),
                                 ("Acompte", -1616.26, False, False)]},
        "GIRERD": {"base": 3101.00, "cp": [2], "mut_reint": False,
                   "inputs": [("Indemnite de transport", 250.0, False, False),
                              ("GAN MUTUELLE FAMILLE", -98.13, False, False),
                              ("Acompte", -2891.77, False, False)]},
    },
    2: {
        "BUGNY": {"base": 2123.38, "mut_reint": False,
                  "inputs": [("Prime exceptionnelle", 150.0, True, True),
                             ("Remboursement de notes de frais", 667.17, False, False)]},
        "COTTE": {"base": 1964.00, "cp": [19],
                  "inputs": [("Prime exceptionnelle", 100.0, True, True)]},
        "ESPINOSA": {"base": 2328.00, "hs25": 15.0, "hs50": 4.0, "mut_reint": False,
                     "inputs": [("Indemnite de transport", 100.0, False, False),
                                ("GAN MUTUELLE FAMILLE", -98.13, False, False)]},
        "GAUTHERON": {"base": 1964.00, "hs25": 3.5, "mut_reint": False,
                      "inputs": [("Prime exceptionnelle", 100.0, True, True),
                                 ("GAN MUTUELLE FAMILLE", -98.13, False, False)]},
        "GIRERD": {"base": 3101.00, "mut_reint": False, "prevoyance": (0.00365, 0.01825),
                   "inputs": [("Indemnite de transport", 250.0, False, False),
                              ("GAN MUTUELLE FAMILLE", -98.13, False, False)]},
    },
    3: {
        "BUGNY": {"base": 2123.38, "hs25": 16.0, "hs50": 10.0, "mut_reint": False,
                  "inputs": [("Prime exceptionnelle", 150.0, True, True),
                             ("Remboursement de notes de frais", 236.00, False, False)]},
        "COTTE": {"base": 1964.00,
                  "inputs": [("Prime exceptionnelle", 100.0, True, True)]},
        "ESPINOSA": {"base": 2328.00, "hs25": 14.75, "hs50": 5.75, "mut_reint": False,
                     "inputs": [("Indemnite de transport", 100.0, False, False),
                                ("GAN MUTUELLE FAMILLE", -98.13, False, False)]},
        "GIRERD": {"base": 3101.00, "mut_reint": False, "prevoyance": (0.00365, 0.01825),
                   "inputs": [("Indemnite de transport", 250.0, False, False),
                              ("GAN MUTUELLE FAMILLE", -98.13, False, False)]},
        # DEMORY : embauche 23/03, mois partiel. KNOWN_GAP : Cegid paie les
        # heures reelles (47.50h base, sans HS structurelle mensualisee), EYWAI
        # mensualise+prorate+ajoute 17.33h HS struct -> brut 772.62 vs 625.25.
        "DEMORY": {"base": 1850.37, "hs25": 3.0, "inputs": []},
    },
    4: {
        "BUGNY": {"base": 2123.38, "hs25": 18.0, "mut_reint": True,
                  "inputs": [("Prime exceptionnelle", 150.0, True, True),
                             ("Remboursement de notes de frais", 1057.49, False, False)]},
        "COTTE": {"base": 1964.00, "hs25": 2.0,
                  "inputs": [("Prime exceptionnelle", 100.0, True, True)]},
        "ESPINOSA": {"base": 2328.00, "hs25": 18.0, "hs50": 3.75, "mut_reint": True,
                     "inputs": [("Indemnite de transport", 100.0, False, False),
                                ("GAN MUTUELLE FAMILLE", -98.12, False, False)]},
        "GIRERD": {"base": 3101.00, "mut_reint": True, "prevoyance": (0.00465, 0.00465),
                   "inputs": [("Indemnite de transport", 250.0, False, False),
                              ("GAN MUTUELLE FAMILLE", -98.12, False, False)]},
        # DEMORY : 1er mois plein. Ferie 06/04 non paye (anciennete < 3 mois).
        "DEMORY": {"base": 1850.37, "abs": {6: 7.0}, "inputs": []},
        # FUCKAR : embauche 07/04 (partiel-embauche, KNOWN_GAP potentiel).
        "FUCKAR": {"base": 1850.37, "hs25": 5.0, "inputs": []},
    },
    6: {
        # Juin : taux releves (mai/juin). mut_reint defaut True, GIRERD
        # prevoyance non-cadre par defaut. Pas de DSN (cibles PDF).
        "BUGNY": {"base": 2165.85, "hs25": 14.0, "hs50": 7.0,
                  "inputs": [("Prime exceptionnelle", 150.0, True, True),
                             ("Remboursement de notes de frais", 415.27, False, False)]},
        "COTTE": {"base": 2003.26,
                  "inputs": [("Prime exceptionnelle", 100.0, True, True)]},
        "DEMORY": {"base": 1867.06, "abs": {8: 7.63}, "inputs": []},
        "ESPINOSA": {"base": 2374.55, "hs25": 16.0, "hs50": 7.0,
                     "inputs": [("Indemnite de transport", 100.0, False, False),
                                ("GAN MUTUELLE FAMILLE", -98.12, False, False)]},
        "FUCKAR": {"base": 1867.06, "hs25": 4.0, "hs50": 3.0,
                   "inputs": [("Prime exceptionnelle 06-2026", 100.0, True, True),
                              ("Prime exceptionnelle 05-2026", 100.0, True, True)]},
        "GAUTHERON": {"base": 1993.40, "abs": {10: 7.0},
                      "inputs": [("Prime exceptionnelle", 100.0, True, True),
                                 ("GAN MUTUELLE FAMILLE", -98.12, False, False),
                                 ("Saisie SGC OYONNAX", -33.38, False, False)]},
        "GIRERD": {"base": 3147.46,
                   "inputs": [("Indemnite de transport", 250.0, False, False),
                              ("GAN MUTUELLE FAMILLE", -98.12, False, False)]},
    },
}


def _emp_map(company_id: str) -> Dict[str, dict]:
    rows = (supabase.table("employees")
            .select("id, matricule, salaire_de_base, company_id, specificites_paie")
            .eq("company_id", company_id).execute().data)
    return {r["matricule"]: r for r in rows}


def _set_base(admin, emp: dict, base: float) -> None:
    sdb = copy.deepcopy(emp.get("salaire_de_base") or {"type": "mensuel"})
    sdb["type"] = sdb.get("type", "mensuel")
    sdb["valeur"] = base
    admin.table("employees").update({"salaire_de_base": sdb}).eq("id", emp["id"]).execute()


def _set_prevoyance(admin, emp: dict, salarial: float, patronal: float) -> None:
    """Override du taux de prevoyance (lignes_specifiques). GIRERD etait cadre
    (EPR1 0.365% sal / 1.825% pat) jan-mars, non-cadre (EPR3 0.465%/0.465%)
    des avril 2026."""
    sp = copy.deepcopy(emp.get("specificites_paie") or {})
    prev = sp.get("prevoyance") or {}
    lignes = prev.get("lignes_specifiques") or []
    if lignes:
        for lg in lignes:
            lg["salarial"] = salarial
            lg["patronal"] = patronal
    else:
        lignes = [{"id": "prevoyance_dsn", "base": "brut_plafonne",
                   "libelle": "Prevoyance (import DSN)",
                   "salarial": salarial, "patronal": patronal}]
    prev["lignes_specifiques"] = lignes
    prev["adhesion"] = True
    sp["prevoyance"] = prev
    admin.table("employees").update({"specificites_paie": sp}).eq("id", emp["id"]).execute()


def _set_mut_reint(admin, emp: dict, reintegree: bool) -> None:
    """Positionne specificites_paie.mutuelle.part_patronale_reintegree_impot.
    Colorplast : la mutuelle patronale n'est reintegree au net imposable qu'a
    partir de mars 2026 (DSN code S21.G00.54 type 92 absent jan-fev)."""
    sp = copy.deepcopy(emp.get("specificites_paie") or {})
    mut = sp.get("mutuelle")
    if not mut:
        return
    mut["part_patronale_reintegree_impot"] = reintegree
    sp["mutuelle"] = mut
    admin.table("employees").update({"specificites_paie": sp}).eq("id", emp["id"]).execute()


def _set_calendar(admin, emp_id: str, year: int, month: int,
                  cp_days: List[int], abs_days: Dict[int, float]) -> str:
    sch = (admin.table("employee_schedules").select("id,planned_calendar")
           .match({"employee_id": emp_id, "year": year, "month": month})
           .maybe_single().execute())
    if not sch or not sch.data:
        return "NO_SCHEDULE"
    planned = copy.deepcopy(sch.data.get("planned_calendar") or {})
    cal = planned.get("calendrier_prevu", [])
    by_day = {j.get("jour"): j for j in cal}
    actions = []
    for d in cp_days:
        j = by_day.get(d)
        if j is None:
            cal.append({"jour": d, "type": "conges_payes", "manuel": True, "heures_prevues": 7.0})
            actions.append(f"cp+{d}")
        else:
            j["type"] = "conges_payes"; j["manuel"] = True
            actions.append(f"cp:{d}")
    for d, h in abs_days.items():
        j = by_day.get(d)
        if j is None:
            cal.append({"jour": d, "type": "absence_non_remuneree", "manuel": True, "heures_prevues": round(h, 2)})
        else:
            j["type"] = "absence_non_remuneree"; j["manuel"] = True; j["heures_prevues"] = round(h, 2)
        actions.append(f"abs:{d}={h}")
    planned["calendrier_prevu"] = sorted(cal, key=lambda x: x["jour"])
    admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sch.data["id"]).execute()
    return ",".join(actions) or "no-cal-change"


def _clear_actual(admin, emp_id: str, year: int, month: int) -> bool:
    """Vide actual_hours.calendrier_reel (pointage corrompu -> absences fantomes).
    EYWAI retombe alors sur le planned_calendar (jours travailles reels)."""
    sch = (admin.table("employee_schedules").select("id,actual_hours")
           .match({"employee_id": emp_id, "year": year, "month": month})
           .maybe_single().execute())
    if not sch or not sch.data:
        return False
    ah = sch.data.get("actual_hours") or {}
    if not ah.get("calendrier_reel"):
        return False
    ah = copy.deepcopy(ah)
    ah["calendrier_reel"] = []
    admin.table("employee_schedules").update({"actual_hours": ah}).eq("id", sch.data["id"]).execute()
    return True


def _clear_inputs(admin, emp_id: str, company_id: str, year: int, month: int) -> None:
    admin.table("monthly_inputs").delete().match(
        {"employee_id": emp_id, "year": year, "month": month}
    ).like("description", f"%{MARKER}%").execute()


def _insert_input(admin, emp_id: str, company_id: str, year: int, month: int,
                  name: str, amount: float, taxed: bool, taxable: bool,
                  qty: float | None = None) -> None:
    admin.table("monthly_inputs").insert({
        "employee_id": emp_id, "company_id": company_id, "year": year, "month": month,
        "name": name, "description": f"Backtest Colorplast {month:02d}/{year} {MARKER}",
        "amount": amount, "is_socially_taxed": taxed, "is_taxable": taxable,
        "payroll_quantity": qty,
    }).execute()


def apply_month(company: str, year: int, month: int, only: List[str] | None = None) -> None:
    admin = get_supabase_admin_client()
    company_id = resolve_company_id(company)
    emps = _emp_map(company_id)
    data = MONTH_DATA.get(month, {})
    for mat, cfg in data.items():
        if only and mat not in only:
            continue
        emp = emps.get(mat)
        if not emp:
            print(f"[{mat}] introuvable"); continue
        if "base" in cfg:
            _set_base(admin, emp, cfg["base"])
        if "mut_reint" in cfg or "prevoyance" in cfg:
            sp = copy.deepcopy(emp.get("specificites_paie") or {})
            if "mut_reint" in cfg and sp.get("mutuelle"):
                sp["mutuelle"]["part_patronale_reintegree_impot"] = cfg["mut_reint"]
            if "prevoyance" in cfg:
                sal, pat = cfg["prevoyance"]
                prev = sp.get("prevoyance") or {}
                lignes = prev.get("lignes_specifiques") or []
                if lignes:
                    for lg in lignes:
                        lg["salarial"] = sal; lg["patronal"] = pat
                else:
                    lignes = [{"id": "prevoyance_dsn", "base": "brut_plafonne",
                               "libelle": "Prevoyance (import DSN)", "salarial": sal, "patronal": pat}]
                prev["lignes_specifiques"] = lignes; prev["adhesion"] = True
                sp["prevoyance"] = prev
            admin.table("employees").update({"specificites_paie": sp}).eq("id", emp["id"]).execute()
        cleared = _clear_actual(admin, emp["id"], year, month)
        cal_res = _set_calendar(admin, emp["id"], year, month,
                                cfg.get("cp", []), cfg.get("abs", {}))
        _clear_inputs(admin, emp["id"], company_id, year, month)
        for name, amount, taxed, taxable in cfg.get("inputs", []):
            _insert_input(admin, emp["id"], company_id, year, month, name, amount, taxed, taxable)
        if cfg.get("hs25"):
            _insert_input(admin, emp["id"], company_id, year, month,
                          "Heures supplementaires conjoncturelles", 0.0, True, True, cfg["hs25"])
        if cfg.get("hs50"):
            _insert_input(admin, emp["id"], company_id, year, month,
                          "Heures supplementaires conjoncturelles 50%", 0.0, True, True, cfg["hs50"])
        print(f"[{mat}] base={cfg.get('base')} cal=[{cal_res}] "
              f"inputs={len(cfg.get('inputs', []))} hs25={cfg.get('hs25')} hs50={cfg.get('hs50')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default="Colorplast")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--emp", nargs="*", default=None)
    args = ap.parse_args()
    apply_month(args.company, args.year, args.month, only=args.emp)


if __name__ == "__main__":
    main()
