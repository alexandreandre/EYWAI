#!/usr/bin/env python3
"""Correction ciblée des 5 salariés Colorplast mai 2026 restants."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client, supabase
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.remediation import (
    FROZEN_EMPLOYEE_FOLDERS,
    _align_pointage_planning,
    _apply_monthly_input,
    _patch_specificites,
)

YEAR, MONTH = 2026, 5
COMPANY = "Colorplast"

# Montants participation Cegid (par matricule)
PARTICIPATION = {
    "ESPINOSA": 3849.67,
    "GAUTHERON": 2632.65,
    "GIRERD": 5331.56,
}

# Autres lignes mensuelles depuis Cegid
EXTRA_INPUTS = {
    "ESPINOSA": [
        {
            "name": "Indemnité de transport",
            "amount": 100.0,
            "is_socially_taxed": False,
            "is_taxable": False,
        },
    ],
    "GAUTHERON": [
        {
            "name": "Prime exceptionnelle",
            "amount": 100.0,
            "is_socially_taxed": True,
            "is_taxable": True,
        },
        {
            "name": "Report NAP négatif (acompte)",
            "amount": -115.11,
            "is_socially_taxed": False,
            "is_taxable": False,
        },
    ],
    "GIRERD": [
        {
            "name": "Indemnité de transport",
            "amount": 250.0,
            "is_socially_taxed": False,
            "is_taxable": False,
        },
    ],
}

WRONG_PARTICIPATION_LABEL = "Participation 2025 — numéraire"


def _generate(employee_id: str, is_forfait: bool) -> None:
    if is_forfait:
        from app.modules.payroll.documents.payslip_generator_forfait import (
            process_payslip_generation_forfait,
        )

        process_payslip_generation_forfait(employee_id, YEAR, MONTH)
    else:
        from app.modules.payroll.documents.payslip_generator import (
            process_payslip_generation,
        )

        process_payslip_generation(employee_id, YEAR, MONTH)


def main() -> None:
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    company_id = resolve_company_id(COMPANY)
    matching = match_employees(company_id, refs)
    targets = {"FUCKAR", "DEMORY", "ESPINOSA", "GAUTHERON", "GIRERD"}

    for match in matching.matched:
        if match.matricule not in targets:
            continue
        if match.employee_folder_name in FROZEN_EMPLOYEE_FOLDERS:
            continue

        print(f"\n=== {match.matricule} ({match.first_name} {match.last_name}) ===")
        eid = match.employee_id

        # 1. Supprimer participation erronée (3936.59 BUGNY)
        admin.table("monthly_inputs").delete().eq("employee_id", eid).eq(
            "year", YEAR
        ).eq("month", MONTH).eq("name", WRONG_PARTICIPATION_LABEL).execute()

        # 2. Participation correcte si applicable
        if match.matricule in PARTICIPATION:
            _apply_monthly_input(
                admin,
                eid,
                company_id,
                YEAR,
                MONTH,
                name=WRONG_PARTICIPATION_LABEL,
                amount=PARTICIPATION[match.matricule],
                is_socially_taxed=False,
                is_taxable=True,
            )
            print(f"  ✓ Participation {PARTICIPATION[match.matricule]:,.2f} €")
        else:
            # FUCKAR / DEMORY : pas de participation
            admin.table("monthly_inputs").delete().eq("employee_id", eid).eq(
                "year", YEAR
            ).eq("month", MONTH).ilike("name", "%participation%").execute()
            print("  ✓ Participation supprimée")

        # 3. Lignes extra (transport, prime excep, acompte)
        for extra in EXTRA_INPUTS.get(match.matricule, []):
            _apply_monthly_input(admin, eid, company_id, YEAR, MONTH, **extra)
            print(f"  ✓ {extra['name']}: {extra['amount']} €")

        # 4. Prévoyance GAN si inactive
        emp = (
            supabase.table("employees")
            .select("specificites_paie")
            .eq("id", eid)
            .maybe_single()
            .execute()
        )
        sp = (emp.data or {}).get("specificites_paie") or {}
        if isinstance(sp, str):
            sp = json.loads(sp)
        if not (sp.get("prevoyance") or {}).get("adhesion"):
            _patch_specificites(admin, eid, {"prevoyance": {"adhesion": True}})
            print("  ✓ Prévoyance activée")

        # 5. hors_hs pour salariés heures si absent
        if not match.is_forfait_jour and not sp.get("salaire_hors_hs_structurelles"):
            _patch_specificites(admin, eid, {"salaire_hors_hs_structurelles": True})
            print("  ✓ hors_hs_structurelles activé")

        # 6. Aligner pointage sur planning
        _align_pointage_planning(admin, eid, YEAR, MONTH)
        print("  ✓ Pointage aligné planning")

        # 7. Régénérer bulletin
        try:
            _generate(eid, match.is_forfait_jour)
            print("  ✓ Bulletin régénéré")
        except Exception as exc:
            print(f"  ⚠ Erreur génération: {exc}")

    # Bilan comparatif
    print("\n=== BILAN POST-CORRECTION ===")
    from scripts.backtest.backtest_company_payroll import compare_matches, _load_payslip_data
    from app.modules.payroll.backtest.thresholds import default_thresholds
    from app.modules.payroll.backtest.models import Verdict

    thresholds = default_thresholds()
    pending = [m for m in matching.matched if m.matricule in targets]
    reports = compare_matches(
        pending, YEAR, MONTH, thresholds=thresholds, systemic_deltas={}, correction_attempts={}
    )
    for r in reports:
        status = "OK" if r.tier_s_max_delta <= 0.05 else "KO"
        print(
            f"  {r.matricule}: tier-S Δ={r.tier_s_max_delta:.2f} € [{status}] "
            f"anomalies S={sum(1 for l in r.lines if l.tier=='S' and l.verdict==Verdict.ANOMALIE)}"
        )


if __name__ == "__main__":
    main()
