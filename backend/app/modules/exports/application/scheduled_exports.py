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
from app.modules.exports.schemas import (
    ExportGenerateRequest,
    ExportHistoryEntry,
    ExportHistoryResponse,
    ExportTotals,
)
from app.modules.exports.schemas.requests import ExportType
from app.modules.exports.schemas.scheduled_exports import (
    ScheduledExportCreate,
    ScheduledExportOut,
    ScheduledExportRunNowResponse,
    ScheduledExportUpdate,
)

EXPORT_TYPE_LABELS: Dict[str, str] = {
    "journal_paie": "Journal de paie",
    "virement_salaires": "Paiement des salaires (virement)",
    "od_salaires": "Écritures OD — Salaires",
    "od_charges_sociales": "Écritures OD — Charges sociales",
    "od_pas": "Écritures OD — PAS",
    "od_globale": "Écritures OD — Globale",
    "export_cabinet_generique": "Export cabinet (générique)",
    "export_cabinet_quadra": "Export cabinet Quadra",
    "export_cabinet_sage": "Export cabinet Sage",
    "dsn_mensuelle": "DSN mensuelle",
}

FREQUENCY_LABELS = {
    "daily": "Quotidien",
    "weekly": "Hebdomadaire",
    "monthly": "Mensuel",
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
    return r.data if r.data else None


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


def run_scheduled_now(
    schedule_id: str, company_id: str, user_id: str
) -> ScheduledExportRunNowResponse:
    row = get_scheduled(schedule_id, company_id)
    if not row:
        raise ValueError("Planification introuvable.")
    export_type = str(row.get("export_type") or "")
    if export_type not in EXPORT_TYPES_GENERATE:
        raise ValueError("Type d'export invalide pour ce planning.")

    period = _previous_payroll_period()
    req = ExportGenerateRequest(
        export_type=cast(ExportType, export_type),
        period=period,
        company_id=company_id,
        format="csv",
        employee_ids=None,
        filters={},
    )
    result: Union[Any, Any] = export_service.generate_export(
        company_id, user_id, req
    )
    export_id = str(getattr(result, "export_id", "") or "")
    if not export_id:
        raise RuntimeError("Génération sans export_id")

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
        now=_utc_now(),
    ).isoformat()

    supabase.table("scheduled_exports").update(
        {"last_run_at": now, "next_run_at": next_at}
    ).eq("id", schedule_id).eq("company_id", company_id).execute()

    return ScheduledExportRunNowResponse(
        export_id=export_id,
        message=f"Export généré pour la période {period}.",
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
