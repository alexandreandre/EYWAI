"""
Exports planifiés : CRUD, calcul next_run_at, exécution manuelle (run-now).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union, cast

from app.core.database import supabase

from app.modules.exports.application import service as export_service
from app.modules.exports.domain.value_objects import EXPORT_TYPES_GENERATE
from app.modules.exports.infrastructure import queries as export_infra_queries
from app.modules.exports.infrastructure import mappers
from app.modules.exports.application.notifications import notify_export_recipients
from app.modules.exports.schemas import (
    ExportGenerateRequest,
    ExportHistoryEntry,
    ExportHistoryResponse,
    ExportPreviewRequest,
    ExportTotals,
)
from app.modules.exports.schemas.requests import ExportType
from app.modules.exports.schemas.scheduled_exports import (
    ScheduledExportCreate,
    ScheduledExportOut,
    ScheduledExportRunNowResponse,
    ScheduledExportUpdate,
)
from app.modules.exports.schemas.dispatch import (
    DispatchScheduleOut,
    DispatchScheduleRunResponse,
    DispatchSchedulesResponse,
    DispatchScheduleUpsert,
)

EXPORT_TYPE_LABELS: Dict[str, str] = {
    "journal_paie": "Journal de paie",
    "virement_salaires": "Paiement des salaires (virement)",
    "od_salaires": "Écritures OD — Salaires",
    "od_charges_sociales": "Écritures OD — Charges sociales",
    "od_pas": "Écritures OD — PAS",
    "od_globale": "Écritures OD — Globale",
    "charges_sociales": "Charges sociales par caisse",
    "notes_frais": "Notes de frais",
    "export_cabinet_generique": "Export cabinet (générique)",
    "export_cabinet_quadra": "Export cabinet Quadra",
    "export_cabinet_sage": "Export cabinet Sage",
    "acomptes": "Acomptes & avances",
    "saisies": "Saisies sur salaire",
    "prets_employeur": "Prêts employeur",
    "paiement_organismes": "Paiement organismes",
    "attestations_annexes": "Attestations & annexes",
    "fec": "FEC",
    "dsn_mensuelle": "DSN mensuelle",
}

FREQUENCY_LABELS = {
    "daily": "Quotidien",
    "weekly": "Hebdomadaire",
    "monthly": "Mensuel",
}

CHANNEL_EXPORT_TYPE: Dict[str, str] = {
    "compta": "od_globale",
    "banque": "virement_salaires",
}

CHANNEL_LABELS: Dict[str, str] = {
    "compta": "Envoi comptabilité",
    "banque": "Envoi banque",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _at_utc(d: date, hour: int) -> datetime:
    return datetime(d.year, d.month, d.day, hour, 0, 0, tzinfo=timezone.utc)


def _previous_payroll_period() -> str:
    """Mois civil précédent au format YYYY-MM (référence paie courante)."""
    now = _utc_now().date()
    y, m = now.year, now.month
    if m == 1:
        return f"{y - 1}-12"
    return f"{y}-{m - 1:02d}"


def compute_next_run_at(
    frequency: str,
    hour_utc: int,
    day_of_week: Optional[int],
    day_of_month: Optional[int],
    from_dt: Optional[datetime] = None,
) -> datetime:
    """
    Prochaine exécution strictement après from_dt (UTC).
    day_of_week : 0 = lundi … 6 = dimanche (ISO, aligné spec).
    """
    base = from_dt or _utc_now()
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)

    h = max(0, min(23, hour_utc))

    if frequency == "daily":
        cand = _at_utc(base.date(), h)
        if cand <= base:
            cand = _at_utc(base.date() + timedelta(days=1), h)
        return cand

    if frequency == "weekly":
        if day_of_week is None:
            raise ValueError("day_of_week requis pour une fréquence hebdomadaire.")
        target = int(day_of_week) % 7
        # Python : lundi = 0
        for delta in range(0, 14):
            d = (base + timedelta(days=delta)).date()
            if d.weekday() != target:
                continue
            cand = _at_utc(d, h)
            if cand > base:
                return cand
        raise ValueError("Impossible de calculer la prochaine exécution hebdomadaire.")

    if frequency == "monthly":
        if day_of_month is None:
            raise ValueError("day_of_month requis pour une fréquence mensuelle.")
        dom = max(1, min(28, int(day_of_month)))
        y, m = base.year, base.month
        try:
            cand = datetime(y, m, dom, h, 0, 0, tzinfo=timezone.utc)
        except ValueError:
            last = calendar.monthrange(y, m)[1]
            safe = min(dom, last)
            cand = datetime(y, m, safe, h, 0, 0, tzinfo=timezone.utc)
        if cand > base:
            return cand
        if m == 12:
            y2, m2 = y + 1, 1
        else:
            y2, m2 = y, m + 1
        try:
            return datetime(y2, m2, dom, h, 0, 0, tzinfo=timezone.utc)
        except ValueError:
            last2 = calendar.monthrange(y2, m2)[1]
            safe2 = min(dom, last2)
            return datetime(y2, m2, safe2, h, 0, 0, tzinfo=timezone.utc)

    raise ValueError(f"Fréquence inconnue: {frequency}")


def _validate_create(body: ScheduledExportCreate) -> None:
    if body.export_type not in EXPORT_TYPES_GENERATE:
        raise ValueError(
            f"Type d'export non autorisé pour la génération: {body.export_type}"
        )
    if body.frequency == "weekly" and body.day_of_week is None:
        raise ValueError("day_of_week est obligatoire pour une fréquence hebdomadaire.")
    if body.frequency == "monthly" and body.day_of_month is None:
        raise ValueError("day_of_month est obligatoire pour une fréquence mensuelle.")


def _row_to_out(row: Dict[str, Any]) -> ScheduledExportOut:
    et = str(row.get("export_type") or "")
    fq = str(row.get("frequency") or "")
    rec = row.get("recipients")
    if not isinstance(rec, list):
        rec = []
    return ScheduledExportOut(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        name=str(row.get("name") or ""),
        export_type=et,
        export_type_label=EXPORT_TYPE_LABELS.get(et, et),
        frequency=fq,
        frequency_label=FREQUENCY_LABELS.get(fq, fq),
        day_of_week=row.get("day_of_week"),
        day_of_month=row.get("day_of_month"),
        hour_utc=int(row.get("hour_utc") or 6),
        recipients=[str(x) for x in rec if x],
        is_active=bool(row.get("is_active", True)),
        last_run_at=row.get("last_run_at"),
        next_run_at=row.get("next_run_at"),
        created_at=row["created_at"],
    )


def list_scheduled(company_id: str) -> List[ScheduledExportOut]:
    r = (
        supabase.table("scheduled_exports")
        .select("*")
        .eq("company_id", company_id)
        .is_("channel", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return [_row_to_out(x) for x in (r.data or []) if isinstance(x, dict)]


def create_scheduled(
    company_id: str, body: ScheduledExportCreate, created_by: str
) -> ScheduledExportOut:
    _validate_create(body)
    next_at = compute_next_run_at(
        body.frequency,
        body.hour_utc,
        body.day_of_week,
        body.day_of_month,
        _utc_now(),
    )
    payload: Dict[str, Any] = {
        "company_id": company_id,
        "name": body.name,
        "export_type": body.export_type,
        "frequency": body.frequency,
        "day_of_week": body.day_of_week,
        "day_of_month": body.day_of_month,
        "hour_utc": body.hour_utc,
        "recipients": body.recipients or [],
        "is_active": True,
        "next_run_at": next_at.isoformat(),
        "created_by": created_by,
    }
    ins = supabase.table("scheduled_exports").insert(payload).execute()
    if not ins.data:
        raise RuntimeError("Échec création export planifié")
    row = ins.data[0] if isinstance(ins.data, list) else ins.data
    return _row_to_out(row)


def get_scheduled(schedule_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    r = (
        supabase.table("scheduled_exports")
        .select("*")
        .eq("id", schedule_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


def update_scheduled(
    schedule_id: str, company_id: str, body: ScheduledExportUpdate
) -> ScheduledExportOut:
    row = get_scheduled(schedule_id, company_id)
    if not row:
        raise ValueError("Planification introuvable.")

    patch: Dict[str, Any] = {}
    if body.name is not None:
        patch["name"] = body.name
    if body.export_type is not None:
        if body.export_type not in EXPORT_TYPES_GENERATE:
            raise ValueError(f"Type d'export non autorisé: {body.export_type}")
        patch["export_type"] = body.export_type
    if body.frequency is not None:
        patch["frequency"] = body.frequency
    if body.day_of_week is not None:
        patch["day_of_week"] = body.day_of_week
    if body.day_of_month is not None:
        patch["day_of_month"] = body.day_of_month
    if body.hour_utc is not None:
        patch["hour_utc"] = body.hour_utc
    if body.recipients is not None:
        patch["recipients"] = body.recipients
    if body.is_active is not None:
        patch["is_active"] = body.is_active

    if not patch:
        return _row_to_out(row)

    merged = {**row, **patch}
    freq = str(merged.get("frequency") or "daily")
    hour_utc = int(merged.get("hour_utc") or 6)
    dow = merged.get("day_of_week")
    dom = merged.get("day_of_month")
    if freq == "weekly" and dow is None:
        raise ValueError("day_of_week requis pour hebdomadaire.")
    if freq == "monthly" and dom is None:
        raise ValueError("day_of_month requis pour mensuel.")

    if any(
        k in patch
        for k in (
            "frequency",
            "hour_utc",
            "day_of_week",
            "day_of_month",
            "is_active",
        )
    ):
        if merged.get("is_active", True):
            patch["next_run_at"] = compute_next_run_at(
                freq,
                hour_utc,
                int(dow) if dow is not None else None,
                int(dom) if dom is not None else None,
                _utc_now(),
            ).isoformat()
        else:
            patch["next_run_at"] = None

    up = (
        supabase.table("scheduled_exports")
        .update(patch)
        .eq("id", schedule_id)
        .eq("company_id", company_id)
        .execute()
    )
    if not up.data:
        raise RuntimeError("Mise à jour impossible")
    out = up.data[0] if isinstance(up.data, list) else up.data
    return _row_to_out(out)


def delete_scheduled(schedule_id: str, company_id: str) -> None:
    row = get_scheduled(schedule_id, company_id)
    if not row:
        raise ValueError("Planification introuvable.")
    supabase.table("scheduled_exports").delete().eq("id", schedule_id).eq(
        "company_id", company_id
    ).execute()


def _default_format_for_type(export_type: str) -> str:
    if export_type == "dsn_mensuelle":
        return "xml"
    if export_type in (
        "fec",
        "virement_salaires",
        "od_salaires",
        "od_charges_sociales",
        "od_pas",
        "od_globale",
    ):
        return "csv"
    return "xlsx"


def run_scheduled_now(
    schedule_id: str,
    company_id: str,
    user_id: str,
    period: Optional[str] = None,
) -> ScheduledExportRunNowResponse:
    row = get_scheduled(schedule_id, company_id)
    if not row:
        raise ValueError("Planification introuvable.")
    export_type = str(row.get("export_type") or "")
    if export_type not in EXPORT_TYPES_GENERATE:
        raise ValueError("Type d'export invalide pour ce planning.")

    pay_period = period or _previous_payroll_period()
    fmt = _default_format_for_type(export_type)

    preview_req = ExportPreviewRequest(
        export_type=cast(ExportType, export_type),
        period=pay_period,
        company_id=company_id,
        employee_ids=None,
        filters={},
    )
    preview = export_service.preview_export(company_id, preview_req)
    if not preview.can_generate:
        raise ValueError(
            "Génération impossible : anomalies bloquantes sur la période sélectionnée."
        )

    req = ExportGenerateRequest(
        export_type=cast(ExportType, export_type),
        period=pay_period,
        company_id=company_id,
        format=cast(Any, fmt),
        employee_ids=None,
        filters={},
    )
    result: Union[Any, Any] = export_service.generate_export(
        company_id, user_id, req
    )
    export_id = str(getattr(result, "export_id", "") or "")
    if not export_id:
        raise RuntimeError("Génération sans export_id")

    recipients = row.get("recipients") or []
    if not isinstance(recipients, list):
        recipients = []
    notify = notify_export_recipients(
        company_id,
        [str(x) for x in recipients if x],
        [export_id],
        export_type_label=EXPORT_TYPE_LABELS.get(export_type, export_type),
        period=pay_period,
    )

    now = _utc_now().isoformat()
    freq = str(row.get("frequency") or "daily")
    hour_utc = int(row.get("hour_utc") or 6)
    dow = row.get("day_of_week")
    dom = row.get("day_of_month")
    next_at = compute_next_run_at(
        freq,
        hour_utc,
        int(dow) if dow is not None else None,
        int(dom) if dom is not None else None,
        _utc_now(),
    ).isoformat()

    supabase.table("scheduled_exports").update(
        {"last_run_at": now, "next_run_at": next_at}
    ).eq("id", schedule_id).eq("company_id", company_id).execute()

    msg = f"Export généré pour la période {pay_period}."
    if notify.message:
        msg = f"{msg} {notify.message}"

    return ScheduledExportRunNowResponse(
        export_id=export_id,
        message=msg,
        email_status=notify.status,
        email_message=notify.message or None,
    )


def history_for_schedule(schedule_id: str, company_id: str) -> ExportHistoryResponse:
    row = get_scheduled(schedule_id, company_id)
    if not row:
        raise ValueError("Planification introuvable.")
    export_type = str(row.get("export_type") or "")
    exports_raw = export_infra_queries.list_exports_by_company(
        company_id, export_type=export_type, period=None, limit=10
    )
    user_ids = list(
        {exp["generated_by"] for exp in exports_raw if exp.get("generated_by")}
    )
    profiles_map = export_infra_queries.get_profiles_map(user_ids)
    history_entries: List[ExportHistoryEntry] = []
    for exp in exports_raw:
        user_id = exp.get("generated_by")
        profile = profiles_map.get(user_id) if user_id else None
        user_name = mappers.build_display_name_from_profile(profile)
        entry_dict = mappers.build_history_entry_dict(exp, user_name)
        totals_raw = entry_dict.get("totals")
        entry_dict["totals"] = ExportTotals(**totals_raw) if totals_raw else None
        history_entries.append(ExportHistoryEntry(**entry_dict))
    return ExportHistoryResponse(exports=history_entries, total=len(history_entries))


def _get_channel_schedule_row(company_id: str, channel: str) -> Optional[Dict[str, Any]]:
    r = (
        supabase.table("scheduled_exports")
        .select("*")
        .eq("company_id", company_id)
        .eq("channel", channel)
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


def _default_schedule_out(channel: str) -> DispatchScheduleOut:
    return DispatchScheduleOut(
        channel=cast(str, channel),
        schedule_id=None,
        name=CHANNEL_LABELS.get(channel, channel),
        export_type=CHANNEL_EXPORT_TYPE.get(channel, ""),
        is_active=False,
        day_of_month=5,
        hour_utc=6,
        recipients=[],
        last_run_at=None,
        next_run_at=None,
    )


def _row_to_dispatch_schedule(row: Dict[str, Any]) -> DispatchScheduleOut:
    channel = str(row.get("channel") or "")
    return DispatchScheduleOut(
        channel=channel,
        schedule_id=str(row["id"]),
        name=str(row.get("name") or CHANNEL_LABELS.get(channel, channel)),
        export_type=str(row.get("export_type") or CHANNEL_EXPORT_TYPE.get(channel, "")),
        is_active=bool(row.get("is_active", True)),
        day_of_month=int(row.get("day_of_month") or 5),
        hour_utc=int(row.get("hour_utc") or 6),
        recipients=[str(x) for x in (row.get("recipients") or []) if x],
        last_run_at=row.get("last_run_at"),
        next_run_at=row.get("next_run_at"),
    )


def list_channel_schedules(company_id: str) -> DispatchSchedulesResponse:
    schedules: List[DispatchScheduleOut] = []
    for channel in ("compta", "banque"):
        row = _get_channel_schedule_row(company_id, channel)
        if row:
            schedules.append(_row_to_dispatch_schedule(row))
        else:
            schedules.append(_default_schedule_out(channel))
    return DispatchSchedulesResponse(schedules=schedules)


def upsert_channel_schedule(
    company_id: str,
    channel: str,
    body: DispatchScheduleUpsert,
    created_by: str,
) -> DispatchScheduleOut:
    if channel not in CHANNEL_EXPORT_TYPE:
        raise ValueError("Canal invalide (compta ou banque).")

    export_type = CHANNEL_EXPORT_TYPE[channel]
    existing = _get_channel_schedule_row(company_id, channel)
    next_at = (
        compute_next_run_at("monthly", body.hour_utc, None, body.day_of_month, _utc_now())
        if body.is_active
        else None
    )
    payload: Dict[str, Any] = {
        "name": CHANNEL_LABELS[channel],
        "export_type": export_type,
        "frequency": "monthly",
        "day_of_week": None,
        "day_of_month": body.day_of_month,
        "hour_utc": body.hour_utc,
        "recipients": body.recipients or [],
        "is_active": body.is_active,
        "channel": channel,
        "next_run_at": next_at.isoformat() if next_at else None,
    }

    if existing:
        up = (
            supabase.table("scheduled_exports")
            .update(payload)
            .eq("id", existing["id"])
            .eq("company_id", company_id)
            .execute()
        )
        if not up.data:
            raise RuntimeError("Mise à jour planning impossible")
        row = up.data[0] if isinstance(up.data, list) else up.data
        return _row_to_dispatch_schedule(row)

    payload["company_id"] = company_id
    payload["created_by"] = created_by
    ins = supabase.table("scheduled_exports").insert(payload).execute()
    if not ins.data:
        raise RuntimeError("Création planning impossible")
    row = ins.data[0] if isinstance(ins.data, list) else ins.data
    return _row_to_dispatch_schedule(row)


def run_channel_schedule_now(
    company_id: str, channel: str, user_id: str, period: Optional[str] = None
) -> DispatchScheduleRunResponse:
    if channel not in CHANNEL_EXPORT_TYPE:
        raise ValueError("Canal invalide (compta ou banque).")

    row = _get_channel_schedule_row(company_id, channel)
    pay_period = period or _previous_payroll_period()

    from app.modules.exports.application import dispatch as dispatch_service
    from app.modules.exports.schemas.dispatch import (
        DispatchBanqueRequest,
        DispatchComptaRequest,
    )

    if channel == "compta":
        result = dispatch_service.dispatch_compta(
            company_id, user_id, DispatchComptaRequest(period=pay_period)
        )
    else:
        result = dispatch_service.dispatch_banque(
            company_id, user_id, DispatchBanqueRequest(period=pay_period)
        )

    if row:
        now = _utc_now().isoformat()
        freq = str(row.get("frequency") or "monthly")
        hour_utc = int(row.get("hour_utc") or 6)
        dom = row.get("day_of_month")
        next_at = compute_next_run_at(
            freq,
            hour_utc,
            None,
            int(dom) if dom is not None else 5,
            _utc_now(),
        ).isoformat()
        supabase.table("scheduled_exports").update(
            {"last_run_at": now, "next_run_at": next_at}
        ).eq("id", row["id"]).execute()

    return DispatchScheduleRunResponse(
        dispatch_id=result.dispatch_id,
        export_id=result.export_ids[0] if result.export_ids else None,
        message=result.message,
        parameters={"period": pay_period},
    )


def get_due_channel_schedules() -> List[Dict[str, Any]]:
    """Plannings canal actifs dont next_run_at est dépassé (UTC)."""
    now_iso = _utc_now().isoformat()
    r = (
        supabase.table("scheduled_exports")
        .select("*")
        .eq("is_active", True)
        .not_.is_("channel", "null")
        .lte("next_run_at", now_iso)
        .execute()
    )
    return [x for x in (r.data or []) if isinstance(x, dict)]


def run_due_channel_schedules() -> List[Dict[str, Any]]:
    """
    Exécute tous les plannings compta/banque échus.
    Retourne un résumé par planning (succès ou erreur).
    """
    due = get_due_channel_schedules()
    results: List[Dict[str, Any]] = []

    for row in due:
        schedule_id = str(row.get("id") or "")
        company_id = str(row.get("company_id") or "")
        channel = str(row.get("channel") or "")
        user_id = str(row.get("created_by") or "")

        if not company_id or channel not in CHANNEL_EXPORT_TYPE:
            results.append(
                {
                    "schedule_id": schedule_id,
                    "company_id": company_id,
                    "channel": channel,
                    "success": False,
                    "error": "Planning invalide (company_id ou canal manquant).",
                }
            )
            continue

        if not user_id:
            results.append(
                {
                    "schedule_id": schedule_id,
                    "company_id": company_id,
                    "channel": channel,
                    "success": False,
                    "error": "created_by manquant sur le planning.",
                }
            )
            continue

        try:
            response = run_channel_schedule_now(company_id, channel, user_id)
            results.append(
                {
                    "schedule_id": schedule_id,
                    "company_id": company_id,
                    "channel": channel,
                    "success": True,
                    "dispatch_id": response.dispatch_id,
                    "message": response.message,
                    "period": response.parameters.get("period"),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "schedule_id": schedule_id,
                    "company_id": company_id,
                    "channel": channel,
                    "success": False,
                    "error": str(exc),
                }
            )

    return results


def get_due_rh_schedules() -> List[Dict[str, Any]]:
    """Plannings RH génériques (sans canal) actifs et échus."""
    now_iso = _utc_now().isoformat()
    r = (
        supabase.table("scheduled_exports")
        .select("*")
        .eq("is_active", True)
        .is_("channel", "null")
        .lte("next_run_at", now_iso)
        .execute()
    )
    return [x for x in (r.data or []) if isinstance(x, dict)]


def run_due_rh_schedules() -> List[Dict[str, Any]]:
    """Exécute les exports RH planifiés par type dont l'échéance est dépassée."""
    due = get_due_rh_schedules()
    results: List[Dict[str, Any]] = []

    for row in due:
        schedule_id = str(row.get("id") or "")
        company_id = str(row.get("company_id") or "")
        user_id = str(row.get("created_by") or "")
        export_type = str(row.get("export_type") or "")

        if not company_id or not user_id:
            results.append(
                {
                    "schedule_id": schedule_id,
                    "company_id": company_id,
                    "export_type": export_type,
                    "success": False,
                    "error": "Planning invalide (company_id ou created_by manquant).",
                }
            )
            continue

        try:
            response = run_scheduled_now(schedule_id, company_id, user_id)
            results.append(
                {
                    "schedule_id": schedule_id,
                    "company_id": company_id,
                    "export_type": export_type,
                    "success": True,
                    "export_id": response.export_id,
                    "message": response.message,
                    "email_status": response.email_status,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "schedule_id": schedule_id,
                    "company_id": company_id,
                    "export_type": export_type,
                    "success": False,
                    "error": str(exc),
                }
            )

    return results
