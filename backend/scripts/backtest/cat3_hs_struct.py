"""Catégorie 3 — HS structurelles surévaluées (brut +13-18, NI≈0).

Cause : le calendrier prévu applique 7,5 h/jour à des contrats 36,67 h/semaine.
Une semaine pleine (5×7,5=37,5 h) dépasse la durée contractuelle (36,67 h) de
0,83 h → l'analyzer facture cette 0,83 h en HS conjoncturelle 25 %, que Cegid ne
paie pas (mensualisation lissée, HS structurelles déjà incluses).

Correction DATA (revert-safe) : ramener les heures_prevues des jours « travail »
à duree_hebdo/5 (planché à 2 décimales pour ne jamais dépasser le seuil), de
sorte qu'une semaine pleine = durée contractuelle exacte → zéro HS conjoncturelle.

Snapshot → applique → régénère → compare le tier-S. Garde si mieux, revert sinon.

Usage (depuis backend/) :
    .venv/bin/python -m scripts.backtest.cat3_hs_struct [MATRICULE ...]
"""
from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

COMPANY, YEAR, MONTH = "Mont Blanc Composite", 2026, 5
CONVERGENCE = 0.05
DEFAULT = ["SOUCHEYRE", "SULPICE", "GOISSAUD", "CVITKOVIC", "BOUSSANOR", "FANOVO"]


def tier_s(match) -> float:
    _generate_payslip(match, YEAR, MONTH)
    for r in compare_matches([match], YEAR, MONTH, thresholds=default_thresholds(),
                             systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")


def process(match, admin) -> dict:
    before = tier_s(match)
    if before <= CONVERGENCE:
        return {"m": match.matricule, "before": before, "after": before, "st": "déjà OK"}

    emp = (admin.table("employees").select("duree_hebdomadaire")
           .eq("id", match.employee_id).single().execute().data)
    duree = float(emp.get("duree_hebdomadaire") or 35)
    # Planché 2 décimales pour ne jamais dépasser le seuil hebdo contractuel.
    target = math.floor((duree / 5.0) * 100) / 100.0

    srow = (admin.table("employee_schedules").select("id,planned_calendar")
            .match({"employee_id": match.employee_id, "year": YEAR, "month": MONTH})
            .maybe_single().execute().data)
    if not srow:
        return {"m": match.matricule, "before": before, "after": before, "st": "pas de schedule"}
    sid = srow["id"]
    orig = copy.deepcopy(srow["planned_calendar"])
    pc = copy.deepcopy(srow["planned_calendar"])
    changed = 0
    for j in pc.get("calendrier_prevu", []):
        if j.get("type") == "travail" and (j.get("heures_prevues") or 0) > target + 0.005:
            j["heures_prevues"] = target
            changed += 1
    if not changed:
        return {"m": match.matricule, "before": before, "after": before, "st": "rien à changer"}

    admin.table("employee_schedules").update({"planned_calendar": pc}).eq("id", sid).execute()
    after = tier_s(match)
    if after < before - 0.01:
        return {"m": match.matricule, "before": before, "after": after,
                "st": f"amélioré (jours={changed}, {target}h/j)"}
    admin.table("employee_schedules").update({"planned_calendar": orig}).eq("id", sid).execute()
    reverted = tier_s(match)
    return {"m": match.matricule, "before": before, "after": reverted,
            "st": f"revert (essai={after:.2f})"}


def main():
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    wanted = set(sys.argv[1:]) or set(DEFAULT)
    matched = [m for m in matched if m.matricule in wanted]
    for m in matched:
        res = process(m, admin)
        print(f"[{res['m']:12s}] {res['before']:7.2f} -> {res['after']:7.2f}  {res['st']}", flush=True)


if __name__ == "__main__":
    main()
