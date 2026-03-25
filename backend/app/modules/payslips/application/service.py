"""
Service applicatif payslips.

Orchestration des commands et queries, et contrôles d'accès (autorisation).
Les routers n'ont plus à porter la logique métier : ils appellent le service
et mappent les exceptions (PayslipNotFoundError -> 404, PayslipForbiddenError -> 403).
"""

from __future__ import annotations

from typing import Any

from app.modules.payslips.application.commands import (
    delete_payslip as cmd_delete_payslip,
    edit_payslip,
    generate_payslip,
    restore_payslip_version,
)
from app.modules.payslips.application.dto import (
    EditPayslipInput,
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipForbiddenError,
    PayslipNotFoundError,
    RestorePayslipInput,
    UserContext,
)
from app.modules.payslips.application.queries import (
    get_payslip_details,
    get_payslip_history,
)
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


def delete_payslip_use_case(payslip_id: str) -> None:
    """Suppression d'un bulletin (BDD + storage + recalc COR)."""
    cmd_delete_payslip(payslip_id)


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
        ctx.is_super_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    ):
        raise PayslipForbiddenError(
            "Accès refusé: vous n'avez pas les permissions pour consulter ce bulletin"
        )
    return detail


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
        ctx.is_super_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    ):
        raise PayslipForbiddenError("Accès refusé")
    return get_payslip_history(payslip_id)


def edit_payslip_for_user(
    payslip_id: str,
    payslip_data: dict[str, Any],
    changes_summary: str,
    ctx: UserContext,
    pdf_notes: str | None = None,
    internal_note: str | None = None,
) -> dict[str, Any]:
    """
    Édition d'un bulletin après vérification des droits (RH/Admin/Super Admin).
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
        ctx.is_super_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    ):
        raise PayslipForbiddenError(
            "Vous n'avez pas les permissions pour modifier les bulletins"
        )
    return edit_payslip(
        EditPayslipInput(
            payslip_id=payslip_id,
            payslip_data=payslip_data,
            changes_summary=changes_summary,
            current_user_id=ctx.user_id,
            current_user_name=ctx.display_name(),
            pdf_notes=pdf_notes,
            internal_note=internal_note,
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
        ctx.is_super_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    ):
        raise PayslipForbiddenError(
            "Vous n'avez pas les permissions pour restaurer les bulletins"
        )
    return restore_payslip_version(
        RestorePayslipInput(
            payslip_id=payslip_id,
            version=version,
            current_user_id=ctx.user_id,
            current_user_name=ctx.display_name(),
        )
    )


# --- Ré-exports pour compatibilité : signature (user_id, user_name) au lieu de UserContext ---


def edit_payslip_use_case(
    payslip_id: str,
    payslip_data: dict[str, Any],
    changes_summary: str,
    current_user_id: str,
    current_user_name: str,
    pdf_notes: str | None = None,
    internal_note: str | None = None,
) -> dict[str, Any]:
    """Édition d'un bulletin (signature legacy : user_id, user_name)."""
    return edit_payslip(
        EditPayslipInput(
            payslip_id=payslip_id,
            payslip_data=payslip_data,
            changes_summary=changes_summary,
            current_user_id=current_user_id,
            current_user_name=current_user_name,
            pdf_notes=pdf_notes,
            internal_note=internal_note,
        )
    )


def restore_payslip_use_case(
    payslip_id: str,
    version: int,
    current_user_id: str,
    current_user_name: str,
) -> dict[str, Any]:
    """Restauration d'une version (signature legacy : user_id, user_name)."""
    return restore_payslip_version(
        RestorePayslipInput(
            payslip_id=payslip_id,
            version=version,
            current_user_id=current_user_id,
            current_user_name=current_user_name,
        )
    )
