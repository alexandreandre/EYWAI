"""
Service applicatif payslips.

Orchestration des commands et queries, et contrôles d'accès (autorisation).
Les routers n'ont plus à porter la logique métier : ils appellent le service
et mappent les exceptions (PayslipNotFoundError -> 404, PayslipForbiddenError -> 403).
"""

from __future__ import annotations

from typing import Any

from app.modules.payslips.application.coherence import signal_a_regenerer
from app.modules.payslips.application.exports_du_mois import exports_du_mois
from app.modules.payslips.application.commands import (
    delete_payslip as cmd_delete_payslip,
    generate_payslip,
)
from app.modules.payslips.application.corrections import (
    corriger_bulletin,
    restaurer_version,
)
from app.modules.payslips.application.period_edit_lock import (
    assert_payslip_manual_edit_allowed,
    enrich_payslip_detail_with_edit_lock,
)
from app.modules.payslips.application.dto import (
    CorrigerBulletinInput,
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipForbiddenError,
    PayslipNotFoundError,
    RestorePayslipInput,
    UserContext,
)
from app.modules.payroll.domain.comparaison_mois_dernier import (
    comparer_au_mois_dernier,
    mois_precedent_civil,
)
from app.modules.payslips.application.queries import (
    get_payslip_data_du_mois,
    get_payslip_details,
    get_payslip_history,
)
from app.modules.payslips.domain.corrections import CorrectionsBulletin
from app.modules.payslips.domain.rules import (
    can_edit_or_restore_payslip,
    can_view_payslip,
)
from app.modules.payslips.infrastructure.readers import (
    debug_storage_info_provider,
    payslip_meta_reader,
)


# --- Use cases sans contrôle d'accès (router gère l'auth si besoin) ---


def generate_payslip_use_case(employee_id: str, year: int, month: int) -> Any:
    """Génération d'un bulletin (logique : forfait vs heures dans commands)."""
    return generate_payslip(
        GeneratePayslipInput(employee_id=employee_id, year=year, month=month)
    )


def delete_payslip_use_case(payslip_id: str) -> bool:
    """Suppression d'un bulletin (BDD + storage + recalc COR) ; faux s'il n'existait plus."""
    return cmd_delete_payslip(payslip_id)


def get_debug_storage_info(employee_id: str, year: int, month: int) -> dict[str, Any]:
    """
    Métadonnées Storage pour diagnostic (route debug).
    Lève PayslipNotFoundError si employé absent.
    """
    try:
        return debug_storage_info_provider.get_debug_storage_info(
            employee_id, year, month
        )
    except ValueError as e:
        if "Employé non trouvé" in str(e):
            raise PayslipNotFoundError("Employé non trouvé") from e
        raise


# --- Use cases avec autorisation : le service vérifie et lève si interdit ---


def get_payslip_details_for_user(
    payslip_id: str,
    ctx: UserContext,
) -> dict[str, Any]:
    """
    Détail complet d'un bulletin après vérification des droits.
    Lève PayslipNotFoundError si absent, PayslipForbiddenError si pas le droit.
    """
    detail = get_payslip_details(payslip_id)
    if not detail:
        raise PayslipNotFoundError("Bulletin non trouvé")
    if detail.get("employee_id") != ctx.user_id and not detail.get("company_id"):
        raise PayslipBadRequestError("Bulletin sans entreprise associée")
    if not can_view_payslip(
        detail,
        ctx.user_id,
        ctx.is_platform_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
        ctx.resolved_employee_id,
    ):
        raise PayslipForbiddenError(
            "Accès refusé: vous n'avez pas les permissions pour consulter ce bulletin"
        )
    detail = enrich_payslip_detail_with_edit_lock(
        detail, bypass_lock=ctx.is_platform_admin
    )
    if not _voit_comme_rh(detail, ctx):
        # Le salarié voit son bulletin, pas les versions de travail ni les notes
        # internes de la RH (audit du 28/09).
        return {
            **detail,
            "edit_history": [],
            "internal_notes": [],
            "a_regenerer": None,
            "a_recalculer": None,
            "exports_du_mois": [],
            "comparaison_mois_dernier": _comparaison_du_bulletin(detail),
        }
    return {
        **detail,
        "a_regenerer": signal_a_regenerer(detail),
        "a_recalculer": _a_recalculer_du_bulletin(detail),
        "exports_du_mois": exports_du_mois(
            detail["company_id"], detail["year"], detail["month"]
        ),
        "comparaison_mois_dernier": _comparaison_du_bulletin(detail),
    }


def _comparaison_du_bulletin(detail: dict[str, Any]) -> dict[str, Any]:
    """Brut, net, heures sup et absences vs le bulletin du mois précédent."""
    try:
        annee, mois = mois_precedent_civil(int(detail["year"]), int(detail["month"]))
        precedent = get_payslip_data_du_mois(
            str(detail["employee_id"]), annee, mois
        )
    except Exception:  # noqa: BLE001 — un mois illisible n'empêche pas d'ouvrir le bulletin
        precedent = None
    return comparer_au_mois_dernier(detail.get("payslip_data"), precedent)


def _a_recalculer_du_bulletin(detail: dict[str, Any]) -> bool | None:
    """true / false / null, même règle que la liste de la paie du mois."""
    if str(detail.get("origine") or "calcule") == "importe":
        return None
    try:
        from app.modules.payroll.application.empreinte_entrees_service import (
            empreinte_actuelle,
        )
        from app.modules.payroll.domain.empreinte_entrees import (
            empreinte_stockee,
            etat_a_recalculer,
        )

        actuelle = empreinte_actuelle(
            str(detail["employee_id"]), int(detail["year"]), int(detail["month"])
        )
        return etat_a_recalculer(empreinte_stockee(detail.get("payslip_data")), actuelle)
    except Exception:  # noqa: BLE001 — un détail illisible n'empêche pas d'ouvrir le bulletin
        return None


def _voit_comme_rh(detail: dict[str, Any], ctx: UserContext) -> bool:
    """La RH (ou l'admin) qui peut corriger ce bulletin, pas le salarié."""
    return can_edit_or_restore_payslip(
        detail,
        ctx.is_platform_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    )


def get_payslip_history_for_user(
    payslip_id: str,
    ctx: UserContext,
) -> list[dict[str, Any]]:
    """
    Historique d'édition d'un bulletin après vérification des droits.
    Lève PayslipNotFoundError si bulletin absent, PayslipForbiddenError si pas le droit.
    """
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    if not meta:
        raise PayslipNotFoundError("Bulletin non trouvé")
    if meta.get("employee_id") != ctx.user_id and not meta.get("company_id"):
        raise PayslipBadRequestError("Bulletin sans entreprise associée")
    if not can_view_payslip(
        meta,
        ctx.user_id,
        ctx.is_platform_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
        ctx.resolved_employee_id,
    ):
        raise PayslipForbiddenError("Accès refusé")
    if not _voit_comme_rh(meta, ctx):
        raise PayslipForbiddenError(
            "L'historique d'un bulletin est réservé aux RH de l'entreprise."
        )
    return get_payslip_history(payslip_id)


def edit_payslip_for_user(
    payslip_id: str,
    corrections: CorrectionsBulletin,
    ctx: UserContext,
    *,
    changes_summary: str | None = None,
    pdf_notes: str | None = None,
    internal_note: str | None = None,
    base_updated_at: str | None = None,
) -> dict[str, Any]:
    """
    Correction d'un bulletin par ses variables du mois, après vérification des
    droits (RH/Admin/Super Admin).
    Lève PayslipNotFoundError, PayslipForbiddenError si pas le droit.
    """
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    if not meta:
        raise PayslipNotFoundError("Bulletin non trouvé")
    company_id = meta.get("company_id")
    if not company_id:
        raise PayslipBadRequestError("Bulletin sans entreprise associée")
    if not can_edit_or_restore_payslip(
        meta,
        ctx.is_platform_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    ):
        raise PayslipForbiddenError(
            "Vous n'avez pas les permissions pour modifier les bulletins"
        )
    try:
        assert_payslip_manual_edit_allowed(meta, bypass_lock=ctx.is_platform_admin)
    except ValueError as exc:
        raise PayslipBadRequestError(str(exc)) from exc
    return corriger_bulletin(
        CorrigerBulletinInput(
            payslip_id=payslip_id,
            corrections=corrections,
            current_user_id=ctx.user_id,
            current_user_name=ctx.display_name(),
            changes_summary=changes_summary,
            pdf_notes=pdf_notes,
            internal_note=internal_note,
            base_updated_at=base_updated_at,
        )
    )


def restore_payslip_for_user(
    payslip_id: str,
    version: int,
    ctx: UserContext,
) -> dict[str, Any]:
    """
    Restauration d'une version après vérification des droits.
    Lève PayslipNotFoundError, PayslipForbiddenError si pas le droit.
    """
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    if not meta:
        raise PayslipNotFoundError("Bulletin non trouvé")
    company_id = meta.get("company_id")
    if not company_id:
        raise PayslipBadRequestError("Bulletin sans entreprise associée")
    if not can_edit_or_restore_payslip(
        meta,
        ctx.is_platform_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    ):
        raise PayslipForbiddenError(
            "Vous n'avez pas les permissions pour restaurer les bulletins"
        )
    try:
        assert_payslip_manual_edit_allowed(meta, bypass_lock=ctx.is_platform_admin)
    except ValueError as exc:
        raise PayslipBadRequestError(str(exc)) from exc
    return restaurer_version(
        RestorePayslipInput(
            payslip_id=payslip_id,
            version=version,
            current_user_id=ctx.user_id,
            current_user_name=ctx.display_name(),
        )
    )
