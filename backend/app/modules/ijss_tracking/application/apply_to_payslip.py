"""Application du montant IJSS validé sur le bulletin : une saisie du mois, puis
la génération normale."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.database import supabase
from app.core.logging import get_logger
from app.modules.ijss_tracking.domain.saisie_ijss import LIBELLE_IJSS_VALIDEES
from app.modules.ijss_tracking.infrastructure import repository as repo
from app.modules.payroll.documents.verrou_generation import verrou_de_generation
from app.modules.payslips.application.commands import (
    _fetch_existing_payslip,
    _refuser_si_importe,
    generate_payslip,
    salarie_generable,
)
from app.modules.payslips.application.corrections import _message_d_erreur
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipNotFoundError,
)

logger = get_logger("modules.ijss_tracking.apply")


def _resolve_brut_amount(
    expected: Dict[str, Any],
    period_id: str,
    manual_amount: Optional[float],
    manual_source: Optional[str],
) -> tuple[float, str]:
    """CPAM matched > banque matched > montant manuel > déjà validé."""
    if manual_amount is not None and manual_amount >= 0:
        return round(float(manual_amount), 2), manual_source or "manual"

    existing = expected.get("ijss_brut_validated")
    if existing is not None and float(existing) >= 0:
        return round(float(existing), 2), str(
            expected.get("validation_source") or "manual"
        )

    received = repo.list_received_lines(period_id)
    emp_id = str(expected.get("employee_id") or "")
    cpam = sum(
        float(line.get("amount") or 0)
        for line in received
        if str(line.get("employee_id") or "") == emp_id
        and line.get("source") == "cpam_decompte"
        and line.get("match_status") == "matched"
    )
    if cpam > 0:
        return round(cpam, 2), "cpam_decompte"

    bank = sum(
        float(line.get("amount") or 0)
        for line in received
        if str(line.get("employee_id") or "") == emp_id
        and line.get("source") == "bank_transfer"
        and line.get("match_status") == "matched"
    )
    if bank > 0:
        return round(bank, 2), "bank_transfer"

    raise ValueError(
        "Aucun montant CPAM/banque rapproché — saisissez un montant brut manuellement."
    )


def validate_expected_line_brut(
    company_id: str,
    expected_line_id: str,
    user_id: str,
    amount: Optional[float] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    expected = repo.get_expected_line(company_id, expected_line_id)
    if not expected:
        raise LookupError("Ligne attendue introuvable.")
    period = repo.get_period(company_id, str(expected["period_id"]))
    if not period:
        raise LookupError("Période introuvable.")
    if period.get("status") == "closed":
        raise ValueError("Période clôturée.")

    brut, validation_source = _resolve_brut_amount(
        expected, str(period["id"]), amount, source
    )
    now = datetime.now(timezone.utc).isoformat()
    updated = repo.update_expected_line(
        expected_line_id,
        {
            "ijss_brut_validated": brut,
            "validation_source": validation_source,
            "validated_at": now,
            "validated_by": user_id,
        },
    )
    from app.modules.ijss_tracking.application.service import _recompute_period

    _recompute_period(period)
    return updated or expected


def _ecrire_saisie_ijss(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    brut: float,
    expected_line_id: str,
) -> None:
    """Le montant validé devient la saisie du mois que le générateur relit.

    Une seule par salarié et par mois : la précédente est remplacée.
    `manual_override` la protège de la génération automatique des variables.
    """
    periode = {"employee_id": employee_id, "year": year, "month": month}
    (
        supabase.table("monthly_inputs")
        .delete()
        .match(periode)
        .eq("name", LIBELLE_IJSS_VALIDEES)
        .execute()
    )
    supabase.table("monthly_inputs").insert(
        {
            **periode,
            "company_id": company_id,
            "name": LIBELLE_IJSS_VALIDEES,
            "description": f"Suivi IJSS, ligne {expected_line_id}",
            "amount": brut,
            "is_socially_taxed": False,
            "is_taxable": False,
            "manual_override": True,
        }
    ).execute()


def apply_validated_ijss_to_payslip(
    company_id: str,
    expected_line_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Écrit le montant validé comme saisie du mois, puis recalcule le bulletin
    par la génération normale.

    Le montant passait au générateur en paramètre, sans être écrit : le recalcul
    suivant le perdait, et ce chemin pouvait recalculer un mois repris. Désormais
    la saisie persiste (empreinte, badge « À recalculer ») et la génération
    oppose ses gardes : mois repris, bulletin validé archivé, documents de sortie.
    """
    expected = repo.get_expected_line(company_id, expected_line_id)
    if not expected:
        raise LookupError("Ligne attendue introuvable.")
    period = repo.get_period(company_id, str(expected["period_id"]))
    if not period:
        raise LookupError("Période introuvable.")
    if period.get("status") == "closed":
        raise ValueError("Période clôturée.")

    brut = expected.get("ijss_brut_validated")
    if brut is None:
        raise ValueError("Validez d'abord le montant brut CPAM pour cette ligne.")

    brut_f = round(float(brut), 2)
    employee_id = str(expected.get("employee_id") or "")
    year = int(period["period_year"])
    month = int(period["period_month"])

    # Avant toute écriture : un mois payé par le logiciel précédent, un bulletin
    # repris, un salarié qu'on ne peut pas recalculer ne reçoivent pas la saisie.
    try:
        salarie_generable(employee_id, year, month)
        existant = _fetch_existing_payslip(employee_id, year, month)
        if existant:
            _refuser_si_importe(str(existant["id"]))
    except (PayslipBadRequestError, PayslipNotFoundError) as exc:
        raise ValueError(str(exc)) from exc

    with verrou_de_generation(employee_id, year, month):
        _ecrire_saisie_ijss(employee_id, company_id, year, month, brut_f, expected_line_id)
        try:
            result = generate_payslip(
                GeneratePayslipInput(
                    employee_id=employee_id,
                    year=year,
                    month=month,
                    # Comme une correction au bulletin : le mois a déjà passé ces
                    # gardes à sa génération ; un bulletin validé est archivé puis
                    # repasse en brouillon.
                    force_calendrier_incomplet=True,
                    regenerer_bulletin_valide=True,
                    requested_by=user_id,
                    requested_by_name="rapprochement IJSS",
                    motif=f"IJSS validées appliquées : {brut_f:.2f} €",
                )
            )
            if str(getattr(result, "status", "success")) != "success":
                raise RuntimeError(getattr(result, "message", None) or "Recalcul impossible.")
        except Exception as exc:  # noqa: BLE001 — rendu à l'écran, la saisie reste
            logger.exception("[ijss] Recalcul après application de %s impossible", expected_line_id)
            raise ValueError(
                f"Montant de {brut_f:.2f} € enregistré dans les saisies du mois, mais "
                f"le bulletin n'a pas été recalculé : {_message_d_erreur(exc)}"
            ) from exc

    payslip_id = getattr(result, "payslip_id", None)
    now = datetime.now(timezone.utc).isoformat()
    repo.update_expected_line(
        expected_line_id,
        {
            "applied_to_payslip_at": now,
            "applied_ijss_brut": brut_f,
            "payslip_id": payslip_id or expected.get("payslip_id"),
        },
    )
    from app.modules.ijss_tracking.application.service import _recompute_period

    _recompute_period(period)
    return {
        "expected_line_id": expected_line_id,
        "applied_ijss_brut": brut_f,
        "payslip_id": payslip_id,
        "employee_id": employee_id,
    }


def apply_all_validated_for_period(
    company_id: str, period_id: str, user_id: str
) -> Dict[str, Any]:
    period = repo.get_period(company_id, period_id)
    if not period:
        raise LookupError("Période introuvable.")
    if period.get("status") == "closed":
        raise ValueError("Période clôturée.")

    applied: list[Dict[str, Any]] = []
    errors: list[str] = []
    for exp in repo.list_expected_lines(period_id):
        if exp.get("ijss_brut_validated") is None:
            continue
        if exp.get("applied_to_payslip_at"):
            continue
        st = exp.get("line_status") or "pending"
        if st not in ("ok", "justified", "partial"):
            continue
        try:
            applied.append(
                apply_validated_ijss_to_payslip(
                    company_id, str(exp["id"]), user_id
                )
            )
        except Exception as exc:
            errors.append(f"{exp.get('employee_id')}: {exc}")

    return {"applied_count": len(applied), "applied": applied, "errors": errors}
