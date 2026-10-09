"""
Cas d'usage comparaison N vs N-1, tendance, acquittements, validation.
"""

from __future__ import annotations

from datetime import datetime

from typing import Any, Callable, Iterable

from app.modules.payslips.application.dto import (
    PayslipBadRequestError,
    PayslipCriticalActiveError,
    PayslipForbiddenError,
    PayslipNotFoundError,
    UserContext,
)
from app.modules.payslips.application.coherence import signal_a_regenerer
from app.modules.payslips.application.queries import get_payslip_details
from app.modules.payslips.domain.coherence import raisons_de_ne_pas_valider
from app.modules.payslips.domain.comparison_engine import (
    _extract_values,
    compute_comparison,
    comparison_result_to_dict,
)
from app.modules.payslips.domain.rules import (
    can_edit_or_restore_payslip,
    can_view_payslip,
    is_forfait_jour,
)
from app.modules.payslips.infrastructure.comparison_queries import (
    fetch_employee_statut,
    fetch_noms_utilisateurs,
    fetch_previous_validated_payslip,
    fetch_recent_nets_asc_for_r10,
    fetch_validated_payslips_strictly_before,
    mark_payslip_validated,
    update_payslip_data_alerts_status,
)
from app.core.database import supabase
from app.core.logging import get_logger
from app.modules.payslips.application.commands import (
    _notify_payslip_available,
)
from app.modules.payslips.infrastructure.readers import payslip_meta_reader

logger = get_logger("modules.payslips.application.comparison_service")


def _etat_actuel_du_bulletin(detail: dict[str, Any]) -> Any:
    """L'état du bulletin dans sa chaîne (`EtatDuBulletin`) ; None si illisible :
    on ne bloque pas la validation sur une lecture ratée."""
    try:
        from app.modules.payroll.application.empreinte_entrees_service import (
            etat_dans_la_chaine,
        )

        return etat_dans_la_chaine(
            str(detail["employee_id"]), int(detail["year"]), int(detail["month"])
        )
    except Exception:  # noqa: BLE001 — une lecture ratée ne doit pas valider un bulletin faux ni tout casser
        logger.warning("Empreinte actuelle illisible, validation sans ce filet", exc_info=True)
        return None


def _ensure_view_detail(detail: dict[str, Any] | None, ctx: UserContext) -> dict[str, Any]:
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
    return detail


def _ensure_edit_meta(meta: dict[str, Any] | None, ctx: UserContext) -> dict[str, Any]:
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
            "Vous n'avez pas les permissions pour cette action sur les bulletins"
        )
    return meta


def _voit_comme_rh(detail: dict[str, Any], ctx: UserContext) -> bool:
    """La RH (ou l'admin) du bulletin, pas le salarié qui le consulte."""
    return can_edit_or_restore_payslip(
        detail,
        ctx.is_platform_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    )


def _extract_totals(payslip_data: dict[str, Any]) -> dict[str, float]:
    v = _extract_values(payslip_data)
    return {
        "salaire_brut": v["salaire_brut"],
        "net_a_payer": v["net_a_payer"],
        "total_cotisations": v["total_cotisations_salariales"],
    }


def _avec_noms_des_acquitteurs(resultat: dict[str, Any]) -> dict[str, Any]:
    """Remplace l'identifiant du compte qui a acquitté par « Prénom Nom ».

    Un compte dont le nom est introuvable n'est pas montré : mieux vaut aucune
    personne qu'un identifiant illisible.
    """
    alertes = resultat.get("alerts") or []
    noms = fetch_noms_utilisateurs([a.get("acquitted_by") for a in alertes if a.get("acquitted_by")])
    for alerte in alertes:
        if alerte.get("acquitted_by"):
            alerte["acquitted_by"] = noms.get(str(alerte["acquitted_by"]))
    return resultat


def get_payslip_comparison_for_user(payslip_id: str, ctx: UserContext) -> dict[str, Any]:
    detail = _ensure_view_detail(get_payslip_details(payslip_id), ctx)
    if not _voit_comme_rh(detail, ctx):
        # Les alertes de contrôle (R03 critique, R08, R10…) sont un outil de la
        # RH : le salarié ne les reçoit pas pour son propre bulletin.
        raise PayslipForbiddenError(
            "La comparaison avec le mois précédent est réservée aux ressources humaines."
        )
    emp_id = str(detail["employee_id"])
    comp_id = str(detail["company_id"])
    year = int(detail["year"])
    month = int(detail["month"])
    pd = detail.get("payslip_data") or {}
    if not isinstance(pd, dict):
        pd = {}

    prev = fetch_previous_validated_payslip(emp_id, comp_id, year, month)
    prev_data = None
    if prev and isinstance(prev.get("payslip_data"), dict):
        prev_data = prev["payslip_data"]

    statut = fetch_employee_statut(emp_id)
    recent_nets = fetch_recent_nets_asc_for_r10(emp_id, comp_id, year, month, pd)

    ctx_engine: dict[str, Any] = {
        "bulletin_n_id": payslip_id,
        "month_n": month,
        "year_n": year,
        "bulletin_n1_id": str(prev["id"]) if prev else None,
        "month_n1": int(prev["month"]) if prev else None,
        "year_n1": int(prev["year"]) if prev else None,
        "is_forfait_jour": is_forfait_jour(statut),
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": recent_nets,
    }

    result = compute_comparison(pd, prev_data, ctx_engine)
    return _avec_noms_des_acquitteurs(comparison_result_to_dict(result))


def get_payslip_trend_for_user(payslip_id: str, ctx: UserContext) -> dict[str, Any]:
    detail = _ensure_view_detail(get_payslip_details(payslip_id), ctx)
    avec_alertes = _voit_comme_rh(detail, ctx)
    emp_id = str(detail["employee_id"])
    comp_id = str(detail["company_id"])
    year = int(detail["year"])
    month = int(detail["month"])

    rows = fetch_validated_payslips_strictly_before(emp_id, comp_id, year, month, limit=12)
    asc_rows = list(reversed(rows))

    months_out: list[dict[str, Any]] = []
    prev_pd: dict[str, Any] | None = None
    prev_id: str | None = None
    prev_my: tuple[int, int] | None = None
    fj = is_forfait_jour(fetch_employee_statut(emp_id))

    for row in asc_rows:
        pid = str(row["id"])
        y = int(row["year"])
        m = int(row["month"])
        pdata = row.get("payslip_data") or {}
        if not isinstance(pdata, dict):
            pdata = {}
        totals = _extract_totals(pdata)
        alerts_dicts: list[dict[str, Any]] = []
        if prev_pd is not None and prev_id is not None and prev_my is not None:
            ctx_engine = {
                "bulletin_n_id": pid,
                "month_n": m,
                "year_n": y,
                "bulletin_n1_id": prev_id,
                "month_n1": prev_my[1],
                "year_n1": prev_my[0],
                "is_forfait_jour": fj,
                "has_contract_change": False,
                "has_declared_advance": None,
                "recent_nets_asc": [],
            }
            comp = compute_comparison(pdata, prev_pd, ctx_engine)
            alerts_dicts = comparison_result_to_dict(comp)["alerts"]

        months_out.append(
            {
                "month": m,
                "year": y,
                "payslip_id": pid,
                "salaire_brut": totals["salaire_brut"],
                "net_a_payer": totals["net_a_payer"],
                "total_cotisations": totals["total_cotisations"],
                "alerts": alerts_dicts if avec_alertes else [],
            }
        )
        prev_pd = pdata
        prev_id = pid
        prev_my = (y, m)

    return {"employee_id": emp_id, "months": months_out}


def acquit_payslip_alert_for_user(
    payslip_id: str,
    rule_id: str,
    ctx: UserContext,
    comment: str | None,
) -> dict[str, Any]:
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    _ensure_edit_meta(meta, ctx)
    return update_payslip_data_alerts_status(
        payslip_id, rule_id, "acquittee", ctx.user_id, comment
    )


def ignore_payslip_alert_for_user(
    payslip_id: str,
    rule_id: str,
    ctx: UserContext,
    comment: str | None,
) -> dict[str, Any]:
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    _ensure_edit_meta(meta, ctx)
    return update_payslip_data_alerts_status(
        payslip_id, rule_id, "ignoree", ctx.user_id, comment
    )


def _persist_salarie_notifie_le(payslip_id: str, pd: dict[str, Any]) -> None:
    """Pose le marqueur d'idempotence de notification dans payslip_data."""
    pd = dict(pd)
    pd["salarie_notifie_le"] = datetime.now().isoformat()
    supabase.table("payslips").update({"payslip_data": pd}).eq(
        "id", payslip_id
    ).execute()


def validate_payslip_for_user(payslip_id: str, ctx: UserContext) -> None:
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    _ensure_edit_meta(meta, ctx)
    detail = get_payslip_details(payslip_id)
    if not detail:
        raise PayslipNotFoundError("Bulletin non trouvé")
    emp_id = str(detail["employee_id"])
    comp_id = str(detail["company_id"])
    year = int(detail["year"])
    month = int(detail["month"])
    pd = detail.get("payslip_data") or {}
    if not isinstance(pd, dict):
        pd = {}

    etat = _etat_actuel_du_bulletin(detail)
    raisons = raisons_de_ne_pas_valider(pd, getattr(etat, "raison_a_recalculer", None))
    signal = signal_a_regenerer(
        detail,
        getattr(etat, "cumuls_precedents_changes", None),
        getattr(etat, "cascade_depuis", None),
    )
    if signal and signal not in raisons:
        raisons.append(signal)
    if raisons:
        raise PayslipBadRequestError(" ".join(raisons))

    prev = fetch_previous_validated_payslip(emp_id, comp_id, year, month)
    prev_data = None
    if prev and isinstance(prev.get("payslip_data"), dict):
        prev_data = prev["payslip_data"]

    statut = fetch_employee_statut(emp_id)
    recent_nets = fetch_recent_nets_asc_for_r10(emp_id, comp_id, year, month, pd)

    ctx_engine: dict[str, Any] = {
        "bulletin_n_id": payslip_id,
        "month_n": month,
        "year_n": year,
        "bulletin_n1_id": str(prev["id"]) if prev else None,
        "month_n1": int(prev["month"]) if prev else None,
        "year_n1": int(prev["year"]) if prev else None,
        "is_forfait_jour": is_forfait_jour(statut),
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": recent_nets,
    }
    result = compute_comparison(pd, prev_data, ctx_engine)
    active_crit = [
        {
            "rule_id": a.rule_id,
            "message": a.message,
            "field": a.field,
        }
        for a in result.alerts
        if a.level == "CRITIQUE" and a.status == "active"
    ]
    if active_crit:
        raise PayslipCriticalActiveError(active_crit)

    updated = mark_payslip_validated(payslip_id, ctx.user_id)

    # Lot 3 : le salarié est notifié ICI — jamais à la génération — et une
    # seule fois par contenu (le marqueur vit dans payslip_data : une
    # régénération forcée le balaie, donc une re-validation renotifie).
    #
    # F1 : le marqueur se pose sur l'état FRAIS retourné par la validation
    # (qui vient de nettoyer les alertes moteur) — réécrire `pd` lu en début
    # de fonction ressusciterait ces alertes et écraserait toute écriture
    # concurrente de payslip_data.
    fresh_pd = updated.get("payslip_data") if isinstance(updated, dict) else None
    if not isinstance(fresh_pd, dict):
        fresh_pd = pd
    if not fresh_pd.get("salarie_notifie_le"):
        try:
            if _notify_payslip_available(emp_id, comp_id, year, month):
                _persist_salarie_notifie_le(payslip_id, fresh_pd)
        except Exception:
            logger.warning(
                "Notification bulletin %s après validation en échec", payslip_id
            )
            logger.exception("Exception")


REFUS_INTROUVABLE = (
    "Bulletin introuvable : il a été supprimé ou régénéré depuis l'affichage. "
    "Rechargez la page."
)
REFUS_INATTENDU = (
    "La validation a échoué sur une erreur inattendue. "
    "Ouvrez le bulletin et validez-le depuis son écran."
)


def raison_du_refus(exc: Exception) -> str | None:
    """La raison d'un refus de validation, dite pour la gestionnaire ; None si inconnue."""
    if isinstance(exc, PayslipCriticalActiveError):
        messages = [
            str(a.get("message") or "").strip()
            for a in exc.critical_alerts
            if isinstance(a, dict) and a.get("message")
        ]
        return "Alerte à acquitter dans le bulletin : " + " ".join(messages)
    if isinstance(exc, PayslipNotFoundError):
        return REFUS_INTROUVABLE
    if isinstance(exc, (PayslipBadRequestError, PayslipForbiddenError)):
        return str(exc)
    return None


def valider_plusieurs_bulletins(
    payslip_ids: Iterable[str], valider_un: Callable[[str], None]
) -> dict[str, list[Any]]:
    """Valide chaque bulletin par la règle d'un seul (`valider_un`) ; un refus
    n'arrête pas le lot et revient avec sa raison (revue du 05/10)."""
    valides: list[str] = []
    refus: list[dict[str, str]] = []
    for payslip_id in dict.fromkeys(payslip_ids):
        try:
            valider_un(payslip_id)
        except Exception as exc:  # noqa: BLE001 — chaque bulletin a sa réponse, le lot continue
            raison = raison_du_refus(exc)
            if raison is None:
                logger.exception("Validation groupée : échec inattendu sur %s", payslip_id)
                raison = REFUS_INATTENDU
            refus.append({"payslip_id": payslip_id, "raison": raison})
        else:
            valides.append(payslip_id)
    return {"valides": valides, "refus": refus}
