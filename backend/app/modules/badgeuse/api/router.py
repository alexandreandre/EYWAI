"""
Routers du module badgeuse (pointage).

- Vue employé : /api/me/badgeuse
- Vue RH : /api/badgeuse
"""

from __future__ import annotations

from app.shared.domain.temps_local import FUSEAU_ENTREPRISE
from datetime import date, datetime
from io import StringIO
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.badgeuse.api.terminal_router import router_terminal
from app.modules.badgeuse.application import service as badgeuse_service
from app.modules.badgeuse.application import terminal_service
from app.modules.badgeuse.domain.time_tracking import TimeEntryType, TimeEntrySource
from app.modules.badgeuse.schemas.requests import SetAccountedHoursRequest
from app.modules.users.schemas.responses import User


PERMISSION_BADGEUSE_MANAGE = "badgeuse.manage"


def _require_badgeuse_rh_access(
    company_id: str, current_user: User = Depends(get_current_user)
) -> User:
    """
    Vérifie que l'utilisateur a le droit RH de gérer la badgeuse pour l'entreprise.

    Accès : super_admin, rôles RH (admin / rh / collaborateur_rh), custom avec
    permissions RH, ou permission granulaire ``badgeuse.manage`` si définie en base.
    """
    if not current_user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé pour cette entreprise",
        )
    if access_control_service.can_access_company_as_rh(current_user, company_id):
        return current_user
    if access_control_service.check_user_has_permission(
        str(current_user.id), company_id, PERMISSION_BADGEUSE_MANAGE
    ):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Accès RH badgeuse requis",
    )


# ----- Router employé : /api/me/badgeuse -----

router_me = APIRouter(
    prefix="/api/me/badgeuse",
    tags=["Badgeuse - Employé"],
)


@router_me.get("/status-today")
def get_my_badgeuse_status_today(
    day: Optional[date] = Query(
        None,
        description="Date pour laquelle récupérer le statut (par défaut : aujourd'hui)",
    ),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Statut du jour pour l'employé connecté.
    """
    try:
        return badgeuse_service.get_today_status_for_me(current_user, day=day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router_me.post("/toggle")
def toggle_my_badge(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Bascule entre ENTREE et SORTIE pour l'employé connecté.
    """
    try:
        return badgeuse_service.toggle_badge_for_me(current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router_me.get("/qr")
def get_my_badge_qr(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Payload QR pour l'employé connecté."""
    try:
        company_id = badgeuse_service.get_company_id_from_user(current_user)
        employee_id = badgeuse_service.resolve_my_employee_id_for_user(current_user)
        if not employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Aucune fiche employé n'est reliée à votre compte.",
            )
        return badgeuse_service.get_qr_for_employee(
            employee_id=employee_id,
            company_id=company_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


# ----- Router RH : /api/badgeuse -----

router_rh = APIRouter(
    prefix="/api/badgeuse",
    tags=["Badgeuse - RH"],
)


@router_rh.get("/employees/{employee_id}/days")
def get_employee_days_summary(
    employee_id: str,
    company_id: str = Query(..., description="ID de l'entreprise"),
    start_date: date = Query(..., alias="from"),
    end_date: date = Query(..., alias="to"),
    current_user: User = Depends(get_current_user),
):
    """
    Résumé par jour pour un employé sur une période.
    """
    _require_badgeuse_rh_access(company_id, current_user)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Période invalide")

    summaries = badgeuse_service.get_summary_for_employee_period(
        employee_id=employee_id,
        company_id=company_id,
        start=start_date,
        end=end_date,
    )
    return [
        {
            "date": d.isoformat(),
            "status": dto.status,
            "total_seconds": dto.total_seconds,
            "computed_seconds": dto.computed_seconds,
            "accounted_seconds": dto.accounted_seconds,
            "effective_seconds": dto.effective_seconds,
            "has_override": dto.has_override,
            "override_differs_from_computed": dto.override_differs_from_computed,
            "sequences_count": dto.sequences_count,
            "has_anomalies": dto.has_anomalies,
            "validated": dto.validated,
        }
        for d, dto in sorted(summaries.items(), key=lambda x: x[0])
    ]


@router_rh.get("/employees/{employee_id}/days/{day}")
def get_employee_day_detail(
    employee_id: str,
    day: date,
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
):
    """
    Détail des pointages d'un employé pour un jour donné.
    """
    _require_badgeuse_rh_access(company_id, current_user)
    return badgeuse_service.get_day_detail_for_employee(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )


@router_rh.post("/employees/{employee_id}/days/{day}/validate")
def validate_employee_day(
    employee_id: str,
    day: date,
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
):
    """
    Valide une journée de badgeuse pour un employé (validation RH).
    """
    _require_badgeuse_rh_access(company_id, current_user)
    return badgeuse_service.validate_day_for_employee(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
        current_user=current_user,
    )


@router_rh.patch("/employees/{employee_id}/days/{day}/accounted-hours")
def set_employee_day_accounted_hours(
    employee_id: str,
    day: date,
    payload: SetAccountedHoursRequest,
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
):
    """Définit les heures comptabilisées RH pour une journée (override du brut)."""
    _require_badgeuse_rh_access(company_id, current_user)
    try:
        return badgeuse_service.set_accounted_hours_for_day(
            employee_id=employee_id,
            company_id=company_id,
            day=day,
            accounted_seconds=payload.accounted_seconds,
            current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router_rh.delete("/employees/{employee_id}/days/{day}/accounted-hours")
def clear_employee_day_accounted_hours(
    employee_id: str,
    day: date,
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
):
    """Supprime l'override RH : les heures effectives redeviennent le brut pointages."""
    _require_badgeuse_rh_access(company_id, current_user)
    return badgeuse_service.clear_accounted_hours_for_day(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )


@router_rh.post("/employees/{employee_id}/days/{day}/events")
def add_employee_day_event(
    employee_id: str,
    day: date,
    payload: Dict[str, Any],
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
):
    """
    Ajoute un évènement de pointage pour un jour donné (RH).
    """
    _require_badgeuse_rh_access(company_id, current_user)
    try:
        event_type = TimeEntryType(payload["event_type"])
        time_str = payload["time"]
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Champ manquant: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        hour, minute = map(int, time_str.split(":"))
        # « 08:00 » saisi par la RH est une heure MURALE Paris : construit
        # naïf, il serait stocké 08:00 UTC et relu 10:00 l'été.
        ts = datetime.combine(
            day, datetime.min.time(), tzinfo=FUSEAU_ENTREPRISE
        ).replace(hour=hour, minute=minute)
    except Exception as e:
        raise HTTPException(status_code=422, detail="Heure invalide") from e

    return badgeuse_service.add_event_for_employee_day(
        employee_id=employee_id,
        company_id=company_id,
        timestamp=ts,
        event_type=event_type,
        source=TimeEntrySource.RH,
        current_user=current_user,
    )


@router_rh.patch("/events/{event_id}")
def update_event(
    event_id: str,
    payload: Dict[str, Any],
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
):
    """
    Met à jour un évènement de pointage (heure et/ou type).
    """
    _require_badgeuse_rh_access(company_id, current_user)
    ts = None
    event_type = None

    if "time" in payload:
        time_str = payload["time"]
        try:
            # On nécessite aussi la date dans payload pour reconstruire le datetime
            day_str = payload.get("date")
            if not day_str:
                raise ValueError("date manquante pour la mise à jour de l'heure")
            d = date.fromisoformat(day_str)
            hour, minute = map(int, time_str.split(":"))
            ts = datetime.combine(
                d, datetime.min.time(), tzinfo=FUSEAU_ENTREPRISE
            ).replace(
                hour=hour, minute=minute
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Heure invalide: {e}") from e

    if "event_type" in payload:
        try:
            event_type = TimeEntryType(payload["event_type"])
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    return badgeuse_service.update_event_for_employee_day(
        event_id=event_id,
        timestamp=ts,
        event_type=event_type,
        current_user=current_user,
    )


@router_rh.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: str,
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
):
    """
    Supprime un évènement de pointage.
    """
    _require_badgeuse_rh_access(company_id, current_user)
    badgeuse_service.delete_event_for_employee_day(event_id=event_id)
    return {}


@router_rh.get("/summary")
def get_company_summary(
    company_id: str = Query(..., description="ID de l'entreprise"),
    start_date: date = Query(..., alias="from"),
    end_date: date = Query(..., alias="to"),
    employee_ids: Optional[List[str]] = Query(
        None, description="Liste optionnelle d'IDs employés à filtrer"
    ),
    with_anomalies_only: bool = Query(
        False, description="Ne retourner que les employés avec anomalies sur la période"
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Synthèse par employé sur la période : total d'heures et nombre de jours en anomalie.
    """
    _require_badgeuse_rh_access(company_id, current_user)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Période invalide")

    summaries = badgeuse_service.get_company_period_summary(
        company_id=company_id,
        start=start_date,
        end=end_date,
        employee_ids=employee_ids,
    )
    items = []
    for emp_id, dto in summaries.items():
        if with_anomalies_only and dto.days_with_anomalies == 0:
            continue
        items.append(
            {
                "employee_id": emp_id,
                "total_seconds": dto.total_seconds,
                "total_effective_seconds": dto.total_effective_seconds,
                "days_with_anomalies": dto.days_with_anomalies,
            }
        )
    return items


@router_rh.get("/punch-candidates")
def list_badgeuse_punch_candidates(
    company_id: str = Query(..., description="ID de l'entreprise"),
    q: str | None = Query(None, description="Recherche nom ou identifiant"),
    only_not_badged: bool = Query(
        False, description="Uniquement les employés sans pointage aujourd'hui"
    ),
    limit: int = Query(24, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Liste pour le secours RH (sans QR) : recherche et badgeage en un clic."""
    _require_badgeuse_rh_access(company_id, current_user)
    try:
        return badgeuse_service.list_punch_candidates(
            company_id=company_id,
            search=q,
            only_not_badged_today=only_not_badged,
            limit=limit,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router_rh.post("/scan")
def scan_badge_qr(
    payload: Dict[str, Any],
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Enregistre un pointage via scan QR ou identification manuelle."""
    _require_badgeuse_rh_access(company_id, current_user)
    try:
        if payload.get("username"):
            return badgeuse_service.punch_by_username(
                username=str(payload["username"]),
                company_id=company_id,
                actor_user_id=str(current_user.id),
            )
        manual = bool(payload.get("employee_id")) and not payload.get("qr_payload")
        return badgeuse_service.punch_from_qr(
            qr_payload=payload.get("qr_payload"),
            employee_id=payload.get("employee_id"),
            company_id=company_id,
            actor_user_id=str(current_user.id),
            source=TimeEntrySource.RH if manual else TimeEntrySource.QR_SCAN,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router_rh.post("/employees/{employee_id}/regenerate-badge")
def regenerate_employee_badge(
    employee_id: str,
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Régénère le QR d'un employé (invalide les anciennes cartes)."""
    _require_badgeuse_rh_access(company_id, current_user)
    try:
        return badgeuse_service.regenerate_badge_for_employee(
            employee_id=employee_id,
            company_id=company_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router_rh.get("/dashboard/today")
def get_badgeuse_dashboard_today(
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Compteurs temps réel pour la page scan."""
    _require_badgeuse_rh_access(company_id, current_user)
    return badgeuse_service.get_dashboard_today(company_id=company_id)


@router_rh.get("/settings")
def get_badgeuse_company_settings(
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_badgeuse_rh_access(company_id, current_user)
    return badgeuse_service.get_badgeuse_settings(company_id)


@router_rh.patch("/settings")
def patch_badgeuse_company_settings(
    payload: Dict[str, Any],
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_badgeuse_rh_access(company_id, current_user)
    return badgeuse_service.update_badgeuse_settings(
        company_id,
        allow_self_toggle=payload.get("allow_self_toggle"),
        scan_mode_enabled=payload.get("scan_mode_enabled"),
    )


@router_rh.get("/employees/{employee_id}/qr")
def get_employee_badge_qr(
    employee_id: str,
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """QR pour export carte (RH)."""
    _require_badgeuse_rh_access(company_id, current_user)
    try:
        return badgeuse_service.get_qr_for_employee(
            employee_id=employee_id,
            company_id=company_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router_rh.get("/terminal-devices")
def list_badgeuse_terminal_devices(
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    _require_badgeuse_rh_access(company_id, current_user)
    return terminal_service.list_terminal_devices(company_id=company_id)


@router_rh.post("/terminal-devices/activate-here")
def activate_badgeuse_terminal_here(
    payload: Dict[str, Any],
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Active la badgeuse sur l'appareil courant (tablette, iPad…)."""
    _require_badgeuse_rh_access(company_id, current_user)
    try:
        label = payload.get("label")
        return terminal_service.activate_terminal_device_here(
            company_id=company_id,
            created_by=str(current_user.id),
            label=str(label) if label else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router_rh.post("/terminal-devices")
def create_badgeuse_terminal_device(
    payload: Dict[str, Any],
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_badgeuse_rh_access(company_id, current_user)
    try:
        return terminal_service.create_terminal_device(
            company_id=company_id,
            label=str(payload.get("label") or ""),
            created_by=str(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router_rh.delete("/terminal-devices/{device_id}", status_code=204)
def revoke_badgeuse_terminal_device(
    device_id: str,
    company_id: str = Query(..., description="ID de l'entreprise"),
    current_user: User = Depends(get_current_user),
):
    _require_badgeuse_rh_access(company_id, current_user)
    terminal_service.revoke_terminal_device(
        device_id=device_id,
        company_id=company_id,
    )
    return {}


@router_rh.get("/export")
def export_badgeuse_csv(
    company_id: str = Query(..., description="ID de l'entreprise"),
    start_date: date = Query(..., alias="from"),
    end_date: date = Query(..., alias="to"),
    employee_ids: Optional[List[str]] = Query(
        None, description="Liste optionnelle d'IDs employés à filtrer"
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Export CSV des temps de présence par jour et par employé sur la période.
    Colonnes : employé_id, date, total_heures, nombre_de_séquences, anomalie_oui_non.
    """
    _require_badgeuse_rh_access(company_id, current_user)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Période invalide")

    filename, content = badgeuse_service.build_company_summary_csv(
        company_id=company_id,
        start=start_date,
        end=end_date,
        employee_ids=employee_ids,
    )

    output = StringIO(content)
    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router_me", "router_rh", "router_terminal"]
