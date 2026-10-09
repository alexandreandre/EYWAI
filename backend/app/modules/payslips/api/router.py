"""
Router API payslips.

Appelle uniquement l'application du module. Aucune logique métier :
validation des entrées (schémas), construction du contexte utilisateur,
appel du use case, mapping des exceptions applicatives vers HTTP.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.core.constants import HEADER_DEJA_SUPPRIME, MESSAGE_ERREUR_GENERATION
from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.audit.application.commands import log_audit_event
from app.modules.webhooks.application.service import trigger_webhook_event
from app.modules.payslips.application.anomalies_report import (
    build_payslips_anomalies_report,
)
from app.shared.employee_resolution import resolve_employee_id_for_user_account
from app.modules.payslips.application import (
    PayslipBadRequestError,
    PayslipCriticalActiveError,
    PayslipForbiddenError,
    PayslipNotFoundError,
    PayslipRefusStructure,
    PayslipValidatedError,
    UserContext,
    acquit_payslip_alert_for_user,
    delete_payslip,
    generate_payslip,
    get_debug_storage_info,
    get_employee_payslips,
    get_my_payslips_for_user_account,
    get_payslip_comparison_for_user,
    get_payslip_details_for_user,
    get_payslip_history_for_user,
    get_payslip_trend_for_user,
    edit_payslip_for_user,
    ignore_payslip_alert_for_user,
    restore_payslip_for_user,
    validate_payslip_for_user,
    GeneratePayslipInput,
)
from app.modules.payslips.application.comparison_service import (
    valider_plusieurs_bulletins,
)
from app.modules.payslips.application.dto import PayslipConflictError
from app.modules.payslips.domain.comparison_engine import REGLES_CONNUES
from app.modules.payslips.application.report_nap_negatif import (
    ReportNapRefuse,
    executer_report,
    lire_etat_du_report,
    lire_etats_du_mois,
)
from app.modules.payslips.application.router_queries import get_payslip_meta_for_access
from app.modules.payslips.schemas.anomalies import PayslipsAnomaliesReport
from app.modules.payslips.schemas import (
    AcquitAlertRequest,
    ComparisonResultResponse,
    ReportNetNegatifActionRequest,
    HistoryEntry,
    PayslipDetail,
    PayslipEditRequest,
    PayslipEditResponse,
    PayslipInfo,
    PayslipPreviewRequest,
    PayslipPreviewResponse,
    PayslipRequest,
    PayslipRestoreRequest,
    PayslipRestoreResponse,
    TrendResponse,
    ValidationGroupeeRequest,
    ValidationGroupeeResponse,
)
from app.modules.payroll.documents.verrou_generation import GenerationDejaEnCours
from app.modules.users.schemas.responses import User

from app.core.logging import get_logger
from app.modules.payroll.engine.lectures import LectureIndispensable

logger = get_logger(__name__)

router = APIRouter(tags=["Payslips"])

# Exceptions applicatives à mapper vers HTTP (404, 403, 400, 409, 422)
_PAYSLIP_APP_ERRORS = (
    PayslipNotFoundError,
    PayslipForbiddenError,
    PayslipBadRequestError,
    PayslipCriticalActiveError,
    PayslipRefusStructure,
    PayslipValidatedError,
    PayslipConflictError,
    GenerationDejaEnCours,
)


def _to_user_context(user: User) -> UserContext:
    """Adapte User (couche API) vers UserContext (application)."""
    company_id = user.active_company_id
    resolved_employee_id = None
    if company_id:
        resolved_employee_id = resolve_employee_id_for_user_account(
            str(user.id), str(company_id)
        )
    return UserContext(
        user_id=user.id,
        is_platform_admin=user.is_platform_admin,
        has_rh_access_in_company=user.has_rh_access_in_company,
        active_company_id=company_id,
        resolved_employee_id=resolved_employee_id,
        first_name=user.first_name,
        last_name=user.last_name,
    )


def _map_app_errors(exc: Exception) -> None:
    """Relève HTTPException selon le type d'exception applicative."""
    if isinstance(exc, PayslipNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PayslipForbiddenError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, PayslipCriticalActiveError):
        raise HTTPException(
            status_code=400, detail={"critical_alerts": exc.critical_alerts}
        ) from exc
    if isinstance(exc, PayslipRefusStructure):
        # Calendrier incomplet, heures sur un jour d'arrêt, arrêts illisibles :
        # `{code, message, **details}`, que l'écran lit pour proposer la sortie.
        raise HTTPException(status_code=exc.http_status, detail=exc.detail_http()) from exc
    if isinstance(exc, PayslipValidatedError):
        raise HTTPException(
            status_code=409,
            detail={"code": PayslipValidatedError.code, "message": str(exc)},
        ) from exc
    if isinstance(exc, PayslipConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, GenerationDejaEnCours):
        # Une phrase, pas un objet : l'écran de paie l'affiche telle quelle
        # (un 409 structuré y est réservé au bulletin déjà validé).
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, PayslipBadRequestError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _handle_application_errors(exc: Exception) -> None:
    """Alias explicite pour le mapping des erreurs applicatives payslips."""
    _map_app_errors(exc)


def _require_rh_company_context(current_user: User) -> str:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return str(company_id)


def _require_payslip_scope(
    current_user: User,
    payslip_id: str,
    permission_code: str,
    *,
    meta: dict | None = None,
) -> dict:
    """Résout le bulletin (sauf `meta` déjà lu) puis masque un salarié hors périmètre par une 404."""
    if meta is None:
        meta = get_payslip_meta_for_access(payslip_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Bulletin introuvable")
    company_id = str(meta.get("company_id") or "")
    employee_id = str(meta.get("employee_id") or "")
    if not company_id or not employee_id:
        raise HTTPException(status_code=404, detail="Bulletin introuvable")
    if company_id != str(current_user.active_company_id or ""):
        raise HTTPException(status_code=404, detail="Bulletin introuvable")
    access_control_service.require_employee_access(
        current_user, company_id, permission_code, employee_id
    )
    return meta


# --- Rapport anomalies (RH) ---
@router.get("/api/payslips/anomalies", response_model=PayslipsAnomaliesReport)
def get_payslips_anomalies_route(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    """Contrôles métier sur tous les bulletins du mois (entreprise active)."""
    company_id = _require_rh_company_context(current_user)
    today = date.today()
    y = year if year is not None else today.year
    m = month if month is not None else today.month
    try:
        return build_payslips_anomalies_report(company_id, y, m)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de get_payslips_anomalies_route")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/payslips/reports-net-negatif")
def get_reports_net_negatif_du_mois_route(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    """Reports de net négatif de tous les bulletins du mois (une lecture groupée)."""
    company_id = _require_rh_company_context(current_user)
    try:
        return lire_etats_du_mois(company_id, year, month)
    except Exception as e:
        logger.exception("Échec de get_reports_net_negatif_du_mois_route")
        raise HTTPException(
            status_code=500,
            detail=f"Lecture des reports du net négatif impossible : {e}",
        )


# --- Génération ---
@router.post("/api/actions/generate-payslip")
def generate_payslip_route(
    request: PayslipRequest,
    current_user: User = Depends(get_current_user),
):
    """Génération d'un bulletin (forfait jour ou heures selon statut employé).

    Périmètre société vérifié comme sur /validate, /preview et /delete : la
    garde RH seule répond « êtes-vous RH dans VOTRE société ? », jamais
    « ce salarié est-il chez vous ? » — une RH pouvait donc écrire dans la
    paie d'un autre client (audit du 23/08/2026).
    """
    try:
        company_id = _require_rh_company_context(current_user)
        access_control_service.require_employee_access(
            current_user, company_id, "payslips.generate", request.employee_id
        )
        result = generate_payslip(
            GeneratePayslipInput(
                employee_id=request.employee_id,
                year=request.year,
                month=request.month,
                force_calendrier_incomplet=request.force_calendrier_incomplet,
                regenerer_bulletin_valide=request.regenerer_bulletin_valide,
                requested_by=str(current_user.id),
                requested_by_name=(
                    f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
                    or None
                ),
            )
        )
        return {
            "status": result.status,
            "message": result.message,
            "download_url": result.download_url,
            "payslip_id": result.payslip_id,
            "warnings": result.warnings or [],
            "salaire_brut": result.salaire_brut,
            "net_a_payer": result.net_a_payer,
            "heures_sup": result.heures_sup,
        }
    except HTTPException:
        raise
    except _PAYSLIP_APP_ERRORS as exc:
        _handle_application_errors(exc)
    except LectureIndispensable as exc:
        # Le bulletin n'est pas calculé plutôt que calculé sans une donnée
        # (mutuelle, convention, évolution de salaire) : la phrase dit quoi faire
        # (réessayer, ou corriger la fiche).
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as e:
        logger.exception("Échec de generate_payslip_route")
        raise HTTPException(status_code=500, detail=MESSAGE_ERREUR_GENERATION)


# --- Mes bulletins ---
@router.get("/api/me/payslips", response_model=List[PayslipInfo])
def get_my_payslips_route(current_user: User = Depends(get_current_user)):
    """Liste des bulletins de l'employé connecté."""
    try:
        return get_my_payslips_for_user_account(
            str(current_user.id), current_user.active_company_id
        )
    except Exception as e:
        logger.exception("Échec de get_my_payslips_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Bulletins d'un employé ---
@router.get("/api/employees/{employee_id}/payslips", response_model=List[PayslipInfo])
def get_employee_payslips_route(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Liste des bulletins d'un salarié."""
    try:
        company_id = _require_rh_company_context(current_user)
        access_control_service.require_employee_access(
            current_user, company_id, "payslips.view_all", employee_id
        )
        return get_employee_payslips(employee_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de get_employee_payslips_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Suppression ---
_PERMISSION_SUPPRESSION = "payslips.delete"


def _deja_supprime() -> Response:
    return Response(status_code=204, headers={HEADER_DEJA_SUPPRIME: "true"})


@router.delete("/api/payslips/{payslip_id}", status_code=204)
def delete_payslip_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime un bulletin (BDD, storage, recalc COR) ; idempotent.

    Périmètre résolu depuis le BULLETIN, comme /validate et /preview : la
    garde précédente vérifiait seulement que l'appelant était RH quelque
    part, sans jamais regarder à quelle société appartenait le bulletin
    (audit sécurité 23/08/2026).

    Un bulletin déjà supprimé répond 204 avec l'en-tête `X-Deja-Supprime` (le
    29/09, il répondait 500). Le droit de supprimer est vérifié d'abord, et un
    bulletin d'une autre société répond comme un bulletin absent : la réponse
    ne dit jamais qu'il existe. Dans la société, le périmètre du salarié et les
    refus (validé, repris de l'ancien logiciel) sont ceux d'avant.
    """
    try:
        company_id = str(current_user.active_company_id or "")
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        access_control_service.require_company_permission(
            current_user, company_id, _PERMISSION_SUPPRESSION
        )
        meta = get_payslip_meta_for_access(payslip_id)
        if not meta or str(meta.get("company_id") or "") != company_id:
            return _deja_supprime()
        _require_payslip_scope(current_user, payslip_id, _PERMISSION_SUPPRESSION, meta=meta)
        if not delete_payslip(payslip_id):
            return _deja_supprime()
        return Response(status_code=204)
    except HTTPException:
        raise
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except Exception as e:
        logger.exception("Échec de delete_payslip_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Comparaison N vs N-1 ---
@router.get(
    "/api/payslips/{payslip_id}/comparison",
    response_model=ComparisonResultResponse,
)
def get_payslip_comparison_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Comparaison du bulletin N avec le dernier bulletin N-1 validé."""
    try:
        return get_payslip_comparison_for_user(
            payslip_id, _to_user_context(current_user)
        )
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de get_payslip_comparison_route")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/payslips/{payslip_id}/trend", response_model=TrendResponse)
def get_payslip_trend_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Tendance sur les 12 derniers bulletins validés avant la période du bulletin."""
    try:
        return get_payslip_trend_for_user(payslip_id, _to_user_context(current_user))
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de get_payslip_trend_route")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/payslips/{payslip_id}/report-net-negatif")
def get_report_net_negatif_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Report d'un net négatif sur le mois suivant : montant, saisie existante, verrou."""
    meta = _require_payslip_scope(current_user, payslip_id, "payslips.view_all")
    try:
        return lire_etat_du_report(payslip_id, meta)
    except Exception as e:
        logger.exception("Échec de get_report_net_negatif_route")
        raise HTTPException(
            status_code=500,
            detail=f"Lecture du report du net négatif impossible : {e}",
        )


@router.post("/api/payslips/{payslip_id}/report-net-negatif")
def post_report_net_negatif_route(
    payslip_id: str,
    body: ReportNetNegatifActionRequest,
    current_user: User = Depends(get_current_user),
):
    """Crée, met à jour ou supprime le report. Idempotent ; refuse si le mois suivant est verrouillé."""
    _require_rh_company_context(current_user)
    meta = _require_payslip_scope(current_user, payslip_id, "payslips.view_all")
    try:
        return executer_report(body.action, payslip_id, meta)
    except ReportNapRefuse as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        logger.exception("Échec de post_report_net_negatif_route")
        raise HTTPException(
            status_code=500,
            detail=f"Écriture du report du net négatif impossible : {e}",
        )


def _exiger_regle_connue(rule_id: str) -> None:
    """Refuse en 422 un code de règle que le moteur ne produit pas (« R99 »)."""
    if rule_id not in REGLES_CONNUES:
        raise HTTPException(
            status_code=422,
            detail=f"Règle d'alerte inconnue : « {rule_id} ». Les règles vont de R01 à R12.",
        )


def _tracer_l_alerte(
    action: str,
    payslip_id: str,
    rule_id: str,
    comment: str | None,
    current_user: User,
    request: Request,
) -> None:
    """Journal d'audit d'un acquittement ou d'une alerte ignorée : qui, quand
    (la date du journal), quelle règle, quel commentaire. Jamais bloquant."""
    try:
        meta = get_payslip_meta_for_access(payslip_id)
        cid = str(meta.get("company_id") or "") if meta else ""
        if not cid:
            return
        log_audit_event(
            company_id=cid,
            user_id=str(current_user.id),
            user_email=current_user.email,
            action=action,
            resource_type="payslip",
            resource_id=payslip_id,
            details={
                "employee_id": str(meta.get("employee_id") or ""),
                "rule_id": rule_id,
                "comment": comment,
            },
            ip_address=request.client.host if request.client else None,
        )
    except Exception:  # noqa: BLE001 — l'alerte est déjà traitée, la trace ne doit pas la défaire
        logger.warning("Trace d'audit de l'alerte %s non écrite", rule_id, exc_info=True)


@router.post("/api/payslips/{payslip_id}/alerts/{rule_id}/acquit")
def acquit_payslip_alert_route(
    payslip_id: str,
    rule_id: str,
    request: Request,
    body: AcquitAlertRequest = AcquitAlertRequest(),
    current_user: User = Depends(get_current_user),
):
    """Acquitte une alerte (RH / admin entreprise)."""
    _exiger_regle_connue(rule_id)
    try:
        acquit_payslip_alert_for_user(
            payslip_id,
            rule_id,
            _to_user_context(current_user),
            body.comment,
        )
        _tracer_l_alerte("payslip.alert_acquit", payslip_id, rule_id, body.comment, current_user, request)
        return {"ok": True, "rule_id": rule_id, "status": "acquittee"}
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de acquit_payslip_alert_route")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/payslips/{payslip_id}/alerts/{rule_id}/ignore")
def ignore_payslip_alert_route(
    payslip_id: str,
    rule_id: str,
    request: Request,
    body: AcquitAlertRequest = AcquitAlertRequest(),
    current_user: User = Depends(get_current_user),
):
    """Ignore une alerte (RH / admin entreprise)."""
    _exiger_regle_connue(rule_id)
    try:
        ignore_payslip_alert_for_user(
            payslip_id,
            rule_id,
            _to_user_context(current_user),
            body.comment,
        )
        _tracer_l_alerte("payslip.alert_ignore", payslip_id, rule_id, body.comment, current_user, request)
        return {"ok": True, "rule_id": rule_id, "status": "ignoree"}
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de ignore_payslip_alert_route")
        raise HTTPException(status_code=500, detail=str(e))


def _tracer_la_validation(
    meta: dict | None, payslip_id: str, current_user: User, request: Request
) -> None:
    """Journal d'audit et webhook d'un bulletin validé."""
    cid = str(meta.get("company_id") or "") if meta else ""
    if not cid:
        return
    log_audit_event(
        company_id=cid,
        user_id=str(current_user.id),
        user_email=current_user.email,
        action="payslip.validate",
        resource_type="payslip",
        resource_id=payslip_id,
        details={
            "employee_id": str(meta.get("employee_id") or ""),
        },
        ip_address=request.client.host if request.client else None,
    )
    trigger_webhook_event(
        cid,
        "payslip.validated",
        {
            "payslip_id": payslip_id,
            "employee_id": str(meta.get("employee_id") or ""),
        },
    )


@router.post("/api/payslips/validate-batch", response_model=ValidationGroupeeResponse)
def validate_payslips_batch_route(
    body: ValidationGroupeeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Valide les bulletins prêts du mois, chacun par la règle d'un seul ;
    rend ceux qui sont refusés, avec leur raison."""
    ctx = _to_user_context(current_user)

    def valider_un(payslip_id: str) -> None:
        try:
            meta = _require_payslip_scope(current_user, payslip_id, "payslips.validate")
        except HTTPException as exc:
            if exc.status_code == 404:
                raise PayslipNotFoundError(str(exc.detail)) from exc
            raise PayslipForbiddenError(
                "Vous n'avez pas le droit de valider ce bulletin."
            ) from exc
        validate_payslip_for_user(payslip_id, ctx)
        _tracer_la_validation(meta, payslip_id, current_user, request)

    return valider_plusieurs_bulletins(body.payslip_ids, valider_un)


@router.post("/api/payslips/{payslip_id}/validate", response_model=PayslipDetail)
def validate_payslip_route(
    payslip_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Valide le bulletin si aucune alerte critique active."""
    try:
        meta = _require_payslip_scope(
            current_user, payslip_id, "payslips.validate"
        )
        validate_payslip_for_user(payslip_id, _to_user_context(current_user))
        _tracer_la_validation(meta, payslip_id, current_user, request)
        return get_payslip_details_for_user(payslip_id, _to_user_context(current_user))
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de validate_payslip_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Détail ---
@router.get("/api/payslips/{payslip_id}", response_model=PayslipDetail)
def get_payslip_details_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détail d'un bulletin (cumuls, historique, URL signée)."""
    try:
        return get_payslip_details_for_user(payslip_id, _to_user_context(current_user))
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de get_payslip_details_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Édition ---
@router.post("/api/payslips/{payslip_id}/edit", response_model=PayslipEditResponse)
def edit_payslip_route(
    payslip_id: str,
    edit_request: PayslipEditRequest,
    current_user: User = Depends(get_current_user),
):
    """Corrige un bulletin par ses variables du mois, puis le recalcule (RH)."""
    try:
        _require_payslip_scope(current_user, payslip_id, "payslips.edit")
        result = edit_payslip_for_user(
            payslip_id,
            edit_request.corrections.vers_domaine(),
            _to_user_context(current_user),
            changes_summary=edit_request.changes_summary,
            pdf_notes=edit_request.pdf_notes,
            internal_note=edit_request.internal_note,
            base_updated_at=edit_request.base_updated_at,
        )
        erreur = result.get("recalcul_erreur")
        return PayslipEditResponse(
            status="success",
            message=(
                "Corrections enregistrées, mais le bulletin n'a pas pu être recalculé."
                if erreur
                else "Bulletin corrigé et recalculé."
                if result.get("recalcule")
                else "Notes du bulletin enregistrées."
            ),
            payslip=result["payslip"],
            new_pdf_url=result.get("new_pdf_url"),
            recalcule=bool(result.get("recalcule")),
            recalcul_erreur=erreur,
            recalcul_refus=result.get("recalcul_refus"),
        )
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de edit_payslip_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Aperçu ---
@router.post(
    "/api/payslips/{payslip_id}/preview", response_model=PayslipPreviewResponse
)
def preview_payslip_route(
    payslip_id: str,
    preview_request: PayslipPreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """Rend le bulletin tel qu'il sortira, sans rien enregistrer."""
    try:
        _require_payslip_scope(current_user, payslip_id, "payslips.edit")

        from jinja2 import Environment, FileSystemLoader

        from app.core.paths import payroll_engine_templates
        from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin

        from app.modules.payroll.documents.payslip_editor import cumuls_pour_le_rendu
        from app.modules.payslips.application.queries import get_payslip_details

        detail = get_payslip_details(payslip_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Bulletin introuvable")
        enregistre = detail.get("payslip_data") or {}
        donnees = {
            **enregistre,
            "cumuls": cumuls_pour_le_rendu(enregistre, detail.get("cumuls")),
            "pdf_notes": preview_request.pdf_notes,
        }

        env = Environment(loader=FileSystemLoader(str(payroll_engine_templates())))
        template = env.get_template("template_bulletin.html")
        return PayslipPreviewResponse(
            html=template.render(vue=construire_vue_bulletin(donnees))
        )
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de preview_payslip_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Historique ---
@router.get("/api/payslips/{payslip_id}/history", response_model=List[HistoryEntry])
def get_payslip_history_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Historique des modifications d'un bulletin."""
    try:
        return get_payslip_history_for_user(payslip_id, _to_user_context(current_user))
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de get_payslip_history_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Restauration ---
@router.post(
    "/api/payslips/{payslip_id}/restore", response_model=PayslipRestoreResponse
)
def restore_payslip_route(
    payslip_id: str,
    restore_request: PayslipRestoreRequest,
    current_user: User = Depends(get_current_user),
):
    """Revient aux heures sup et aux primes d'une version, puis recalcule (RH)."""
    try:
        _require_payslip_scope(current_user, payslip_id, "payslips.edit")
        result = restore_payslip_for_user(
            payslip_id,
            restore_request.version,
            _to_user_context(current_user),
        )
        erreur = result.get("recalcul_erreur")
        return PayslipRestoreResponse(
            status="success",
            message=(
                f"Version {restore_request.version} : variables rétablies, mais "
                "le bulletin n'a pas pu être recalculé."
                if erreur
                else f"Bulletin revenu à la version {restore_request.version} et recalculé."
            ),
            payslip=result["payslip"],
            restored_version=restore_request.version,
            recalcule=bool(result.get("recalcule")),
            recalcul_erreur=erreur,
            recalcul_refus=result.get("recalcul_refus"),
        )
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de restore_payslip_route")
        raise HTTPException(status_code=500, detail=str(e))


# --- Debug storage ---
@router.get("/api/debug-storage/{employee_id}/{year}/{month}")
def debug_storage_file(
    employee_id: str,
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Métadonnées Storage pour diagnostic (administrateur plateforme uniquement).

    Ouverte à toute RH, elle laissait lire les métadonnées de stockage du
    bulletin de n'importe quel salarié, d'une autre société comprise.
    """
    try:
        if not current_user.is_platform_admin:
            raise HTTPException(status_code=403, detail="Accès réservé à l'administration")
        return get_debug_storage_info(employee_id, year, month)
    except PayslipNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec de debug_storage_file")
        raise HTTPException(status_code=500, detail=str(e))
