#!/usr/bin/env python3
"""Orchestrateur backtest paie autonome — entreprise x mois.

Compare les bulletins EYWAI aux bulletins Cegid (PDF Config), corrige
automatiquement les écarts (données VERT), boucle jusqu'à convergence,
et envoie un mail de bilan.

Usage:
    python -m scripts.backtest.backtest_company_payroll \\
        --company Colorplast --year 2026 --month 5

    python -m scripts.backtest.backtest_company_payroll \\
        --company Colorplast --year 2026 --month 5 --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import supabase
from app.modules.payroll.backtest.comparator import (
    compare_bulletins,
    detect_systemic_deltas,
)
from app.modules.payroll.backtest.diagnosis import diagnose_reports
from app.modules.payroll.backtest.models import (
    DiscrepancyReport,
    RemediationColor,
    Verdict,
)
from app.modules.payroll.backtest.thresholds import default_thresholds
from scripts.backtest.campaign_state import CampaignState
from scripts.backtest.employee_matching import (
    EmployeeMatch,
    match_employees,
    resolve_company_id,
)
from scripts.backtest.notifier import send_campaign_email
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.remediation import apply_remediation

# Références de non-régression
REGRESSION_MATRICULES = {"COTTE", "BUGNY"}


def _generate_payslip(match: EmployeeMatch, year: int, month: int) -> Dict[str, Any]:
    if match.is_forfait_jour:
        from app.modules.payroll.documents.payslip_generator_forfait import (
            process_payslip_generation_forfait,
        )

        return process_payslip_generation_forfait(match.employee_id, year, month)
    from app.modules.payroll.documents.payslip_generator import (
        process_payslip_generation,
    )

    return process_payslip_generation(match.employee_id, year, month)


def _load_payslip_data(employee_id: str, year: int, month: int) -> Optional[Dict[str, Any]]:
    res = (
        supabase.table("payslips")
        .select("payslip_data")
        .match({"employee_id": employee_id, "year": year, "month": month})
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        return None
    return res.data.get("payslip_data")


def compare_matches(
    matches: List[EmployeeMatch],
    year: int,
    month: int,
    *,
    thresholds,
    systemic_deltas: Dict[str, float],
    correction_attempts: Dict[str, int],
) -> List[DiscrepancyReport]:
    reports: List[DiscrepancyReport] = []
    for match in matches:
        if not match.reference:
            continue
        payslip_data = _load_payslip_data(match.employee_id, year, month) or {}
        reports.append(
            compare_bulletins(
                payslip_data,
                match.reference,
                employee_id=match.employee_id,
                employee_name=f"{match.first_name} {match.last_name}",
                thresholds=thresholds,
                systemic_deltas=systemic_deltas,
                correction_attempts=correction_attempts.get(match.matricule, 0),
            )
        )
    return reports


def _is_converged(reports: List[DiscrepancyReport]) -> bool:
    """Convergence = tier S OK pour tous (≤ 0,05 €)."""
    return all(r.tier_s_max_delta <= 0.05 for r in reports)


def _run_preflight_fixes(
    company_id: str,
    year: int,
    month: int,
    matches: List[EmployeeMatch],
    campaign: CampaignState,
) -> int:
    """Pré-vol : aligne pointage planning pour salariés avec écart."""
    from app.modules.payroll.application.preflight_anomalies import build_preflight_anomalies
    from app.core.database import get_supabase_admin_client

    try:
        preflight = build_preflight_anomalies(company_id, year, month)
    except Exception as exc:
        campaign.progress(f"  Pré-vol ignoré ({exc})")
        return 0

    pointage_ids = {
        a.employee_id
        for a in preflight.anomalies
        if a.type in ("pointage", "ecart_heures") and a.severity == "bloquant"
    }
    if not pointage_ids:
        campaign.progress("  Pré-vol : aucune anomalie pointage bloquante")
        return 0

    admin = get_supabase_admin_client()
    fixed = 0
    matricules = {m.employee_id: m.matricule for m in matches}
    for emp_id in pointage_ids:
        if emp_id not in matricules:
            continue
        from scripts.backtest.remediation import _align_pointage_planning

        try:
            _align_pointage_planning(admin, emp_id, year, month)
            fixed += 1
            campaign.log({"action": "preflight_pointage", "employee_id": emp_id})
        except Exception as exc:
            campaign.progress(f"  ⚠ Pré-vol {matricules.get(emp_id)}: {exc}")
    campaign.progress(f"  Pré-vol : {fixed} pointage(s) aligné(s) sur planning")
    return fixed


def _regression_ok(
    matches: List[EmployeeMatch],
    year: int,
    month: int,
    thresholds,
) -> bool:
    ref_matches = [m for m in matches if m.matricule in REGRESSION_MATRICULES]
    if not ref_matches:
        return True
    reports = compare_matches(
        ref_matches, year, month, thresholds=thresholds, systemic_deltas={}, correction_attempts={}
    )
    return all(r.tier_s_max_delta <= 0.05 for r in reports)


def run_campaign(
    company_name: str,
    year: int,
    month: int,
    *,
    dry_run: bool = False,
    max_iterations: int | None = None,
) -> Dict[str, Any]:
    start = time.time()
    thresholds = default_thresholds()
    max_iter = max_iterations or thresholds.max_iterations
    campaign = CampaignState(company_name, year, month)
    state = campaign.load_state()

    print(f"=== Backtest paie : {company_name} {month:02d}/{year} ===")
    campaign.progress(f"Démarrage campagne {company_name} {month:02d}/{year}")

    # 1. Charger références Cegid
    references = load_reference_bulletins(company_name, year, month)
    print(f"Références Cegid : {len(references)} bulletins parsés")

    # 2. Apparier employés
    company_id = resolve_company_id(company_name)
    matching = match_employees(company_id, references)
    print(
        f"Appariements : {len(matching.matched)} matchés, "
        f"{len(matching.unmatched_references)} refs orphelines, "
        f"{len(matching.unmatched_employees)} employés sans ref"
    )

    if not matching.matched:
        raise SystemExit("Aucun employé apparié — arrêt.")

    # 3. Snapshot initial
    if not dry_run:
        campaign.snapshot_payslips([m.employee_id for m in matching.matched])
        _run_preflight_fixes(company_id, year, month, matching.matched, campaign)

    correction_attempts: Dict[str, int] = {}
    patterns_applied: List[Dict[str, Any]] = []
    prev_converged = -1
    plateau_count = 0
    stop_reason = "budget"

    for iteration in range(1, max_iter + 1):
        state["iteration"] = iteration
        campaign.progress(f"--- Itération {iteration}/{max_iter} ---")

        # 4. Générer bulletins
        if not dry_run:
            for match in matching.matched:
                try:
                    _generate_payslip(match, year, month)
                except Exception as exc:
                    print(f"  ⚠ Génération {match.matricule}: {exc}")

        # 5. Comparer
        reports = compare_matches(
            matching.matched,
            year,
            month,
            thresholds=thresholds,
            systemic_deltas={},
            correction_attempts=correction_attempts,
        )
        systemic = detect_systemic_deltas(reports, thresholds)
        if systemic:
            print(f"  Écarts systémiques détectés : {systemic}")
            reports = compare_matches(
                matching.matched,
                year,
                month,
                thresholds=thresholds,
                systemic_deltas=systemic,
                correction_attempts=correction_attempts,
            )

        # 6. Mettre à jour état
        for report in reports:
            name = next(
                (f"{m.first_name} {m.last_name}" for m in matching.matched if m.matricule == report.matricule),
                "",
            )
            campaign.update_employee_status(state, report.matricule, report, name=name)

        converged, total = campaign.count_converged(state)
        tier_s_ok = sum(1 for r in reports if r.tier_s_max_delta <= 0.05)
        campaign.progress(
            f"  Convergence tier-S : {tier_s_ok}/{total} | statut OK : {converged}/{total}"
        )

        if _is_converged(reports):
            stop_reason = "converge"
            campaign.save_state(state)
            break

        if converged == prev_converged:
            plateau_count += 1
            if plateau_count >= thresholds.plateau_stop_after:
                stop_reason = "plateau"
                campaign.save_state(state)
                break
        else:
            plateau_count = 0
        prev_converged = converged

        if dry_run:
            break

        # 7. Diagnostiquer et appliquer remediations VERTES
        proposals = diagnose_reports(
            reports,
            references,
            catalog_path=campaign.catalog_path,
            systemic_fields=set(systemic.keys()),
        )
        vert_proposals = [p for p in proposals if p.color == RemediationColor.VERT]
        orange_proposals = [p for p in proposals if p.color == RemediationColor.ORANGE]
        for op in orange_proposals:
            campaign.progress(
                f"  ORANGE (code) reporté : {op.pattern_id} — {len(op.affected_matricules)} sal."
            )
            existing = state.setdefault("orange_quarantines", [])
            if not any(x.get("pattern_id") == op.pattern_id for x in existing):
                existing.append(
                    {"pattern_id": op.pattern_id, "matricules": op.affected_matricules}
                )
        if not vert_proposals:
            print("  Aucune remediation VERTE applicable — plateau imminent")
            plateau_count += 1
            if plateau_count >= thresholds.plateau_stop_after:
                stop_reason = "plateau_no_fix"
                campaign.save_state(state)
                break
            continue

        emp_ids = {m.matricule: m.employee_id for m in matching.matched}
        folders = {m.matricule: m.employee_folder_name for m in matching.matched}
        applied_patterns = set(state.get("patterns_applied") or [])

        for proposal in vert_proposals[:4]:
            # Ne pas ré-appliquer un pattern déjà tenté sans progrès tier-S
            if proposal.pattern_id in applied_patterns:
                still_bad = [
                    m
                    for m in proposal.affected_matricules
                    if (state.get("employees") or {}).get(m, {}).get("tier_s_max_delta", 999)
                    > 0.05
                ]
                if not still_bad:
                    continue
            campaign.progress(
                f"  Applique {proposal.pattern_id} ({len(proposal.affected_matricules)} sal.)"
            )
            results = apply_remediation(
                proposal,
                employee_ids_by_matricule=emp_ids,
                company_id=company_id,
                year=year,
                month=month,
                employee_folders=folders,
                journal_callback=campaign.log,
            )
            applied = [r for r in results if r.get("status") == "applied"]
            if applied:
                patterns_applied.append(
                    {
                        "pattern_id": proposal.pattern_id,
                        "matricules": [r["matricule"] for r in applied],
                    }
                )
                state.setdefault("patterns_applied", []).append(proposal.pattern_id)
                for r in applied:
                    correction_attempts[r["matricule"]] = (
                        correction_attempts.get(r["matricule"], 0) + 1
                    )
                # Régénérer immédiatement les salariés corrigés
                touched_ids = {r["employee_id"] for r in applied if r.get("employee_id")}
                for match in matching.matched:
                    if match.employee_id in touched_ids:
                        try:
                            _generate_payslip(match, year, month)
                        except Exception as exc:
                            print(f"  ⚠ Regénération {match.matricule}: {exc}")

        # 8. Non-régression COTTE/BUGNY (tier S uniquement)
        if not _regression_ok(matching.matched, year, month, thresholds):
            campaign.progress("  ⚠ Régression ancre COTTE/BUGNY (tier S > 0,05 €) — arrêt sécurisé")
            stop_reason = "regression"
            campaign.save_state(state)
            break

        campaign.save_state(state)

    duration = (time.time() - start) / 60.0
    state["patterns_applied"] = state.get("patterns_applied") or []
    campaign.save_state(state)

    # 9. Rapport + mail
    tolerated = [
        {"field_key": k, "delta": v, "count": thresholds.systemic_min_employees}
        for k, v in (detect_systemic_deltas(
            compare_matches(
                matching.matched, year, month,
                thresholds=thresholds, systemic_deltas={}, correction_attempts={},
            ),
            thresholds,
        ).items())
    ]

    if not dry_run:
        ok, err = send_campaign_email(
            company_name=company_name,
            year=year,
            month=month,
            state=state,
            stop_reason=stop_reason,
            duration_minutes=duration,
            report_path=campaign.report_path,
            patterns_applied=patterns_applied,
            quarantines=state.get("quarantines") or [],
            tolerated=tolerated,
        )
        if ok:
            print(f"\n✅ Mail envoyé à alexandreandre2004@gmail.com")
        else:
            print(f"\n⚠ Mail non envoyé : {err}")
    else:
        print("\n(dry-run — pas de mail envoyé)")

    print(f"\nRapport : {campaign.report_path}")
    print(f"Arrêt : {stop_reason} — {duration:.1f} min")
    return {"stop_reason": stop_reason, "state": state, "duration_minutes": duration}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True, help="Nom entreprise (ex: Colorplast)")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + compare sans écrire en base ni envoyer de mail",
    )
    parser.add_argument("--max-iterations", type=int, default=None)
    args = parser.parse_args()
    run_campaign(
        args.company,
        args.year,
        args.month,
        dry_run=args.dry_run,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    main()
