"""
Envois compta / banque : génération groupée et suivi de transmission.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, cast

from app.core.database import supabase

from app.modules.exports.application import service as export_service
from app.modules.exports.infrastructure import mappers
from app.modules.exports.infrastructure import queries as export_infra_queries
from app.modules.exports.schemas import ExportGenerateRequest, ExportPreviewRequest
from app.modules.exports.schemas.dispatch import (
    DispatchBanqueRequest,
    DispatchChannelStatus,
    DispatchComptaRequest,
    DispatchFileDownload,
    DispatchHistoryEntry,
    DispatchHistoryResponse,
    DispatchResultResponse,
    DispatchStatusResponse,
    MarkDispatchTransmittedResponse,
)

DispatchChannel = Literal["compta", "banque"]

CHANNEL_PREVIEW_TYPE: Dict[str, str] = {
    "compta": "od_globale",
    "banque": "virement_salaires",
}

CHANNEL_GENERATE_TYPES: Dict[str, List[str]] = {
    "compta": ["od_globale", "journal_paie", "fec"],
    "banque": ["virement_salaires"],
}

STATUS_PENDING = "pending"
STATUS_GENERATED = "generated"
STATUS_TRANSMITTED = "transmitted"
STATUS_FAILED = "failed"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_dispatch_row(
    company_id: str, channel: str, period: str
) -> Optional[Dict[str, Any]]:
    r = (
        supabase.table("export_dispatches")
        .select("*")
        .eq("company_id", company_id)
        .eq("channel", channel)
        .eq("period", period)
        .maybe_single()
        .execute()
    )
    return r.data if r.data else None


def _preview_channel(company_id: str, channel: str, period: str) -> Dict[str, Any]:
    export_type = CHANNEL_PREVIEW_TYPE[channel]
    req = ExportPreviewRequest(export_type=cast(Any, export_type), period=period)
    preview = export_service.preview_export(company_id, req)
    blocking = sum(
        1 for a in preview.anomalies if a.severity == "blocking" or a.type == "error"
    )
    return {
        "can_generate": preview.can_generate and blocking == 0,
        "blocking_anomalies_count": blocking,
        "totals": preview.totals,
    }


def _build_channel_status(
    company_id: str, channel: str, period: str
) -> DispatchChannelStatus:
    row = _get_dispatch_row(company_id, channel, period)
    preview_info = _preview_channel(company_id, channel, period)

    if not row:
        return DispatchChannelStatus(
            channel=channel,
            period=period,
            status=STATUS_PENDING,
            can_generate=preview_info["can_generate"],
            blocking_anomalies_count=preview_info["blocking_anomalies_count"],
            totals=preview_info["totals"],
        )

    export_ids = row.get("export_ids") or []
    if not isinstance(export_ids, list):
        export_ids = []

    db_status = str(row.get("status") or STATUS_GENERATED)
    status = db_status if db_status in (STATUS_GENERATED, STATUS_TRANSMITTED, STATUS_FAILED) else STATUS_GENERATED

    return DispatchChannelStatus(
        channel=channel,
        period=period,
        status=status,
        dispatch_id=str(row["id"]),
        export_ids=[str(x) for x in export_ids],
        files_count=len(export_ids),
        totals=preview_info["totals"],
        generated_at=row.get("created_at"),
        transmitted_at=row.get("transmitted_at"),
        transmission_note=row.get("transmission_note"),
        can_generate=preview_info["can_generate"],
        blocking_anomalies_count=preview_info["blocking_anomalies_count"],
    )


def get_dispatch_status(company_id: str, period: str) -> DispatchStatusResponse:
    return DispatchStatusResponse(
        period=period,
        compta=_build_channel_status(company_id, "compta", period),
        banque=_build_channel_status(company_id, "banque", period),
    )


def _collect_downloads(export_ids: List[str], company_id: str) -> List[DispatchFileDownload]:
    downloads: List[DispatchFileDownload] = []
    for export_id in export_ids:
        try:
            url = export_service.get_export_download_url(company_id, export_id)
            exp = export_infra_queries.get_export_by_id(export_id, company_id)
            if not exp:
                continue
            file_paths = exp.get("file_paths") or []
            filename = "export"
            if isinstance(file_paths, list) and file_paths:
                first = file_paths[0]
                if isinstance(first, dict):
                    filename = str(first.get("filename") or filename)
                elif isinstance(first, str):
                    filename = first.rsplit("/", 1)[-1]
            downloads.append(
                DispatchFileDownload(
                    export_id=export_id,
                    export_type=str(exp.get("export_type") or ""),
                    filename=filename,
                    download_url=url,
                )
            )
        except Exception:
            continue
    return downloads


def _upsert_dispatch(
    company_id: str,
    channel: str,
    period: str,
    user_id: str,
    export_ids: List[str],
    parameters: Dict[str, Any],
) -> str:
    existing = _get_dispatch_row(company_id, channel, period)
    payload: Dict[str, Any] = {
        "company_id": company_id,
        "channel": channel,
        "period": period,
        "status": STATUS_GENERATED,
        "export_ids": export_ids,
        "parameters": parameters,
        "created_by": user_id,
        "transmitted_at": None,
        "transmitted_by": None,
        "transmission_note": None,
    }
    if existing:
        up = (
            supabase.table("export_dispatches")
            .update(
                {
                    "status": STATUS_GENERATED,
                    "export_ids": export_ids,
                    "parameters": parameters,
                    "created_by": user_id,
                    "transmitted_at": None,
                    "transmitted_by": None,
                    "transmission_note": None,
                }
            )
            .eq("id", existing["id"])
            .execute()
        )
        row = up.data[0] if up.data else existing
        return str(row["id"])

    ins = supabase.table("export_dispatches").insert(payload).execute()
    if not ins.data:
        raise RuntimeError("Échec enregistrement dispatch")
    row = ins.data[0] if isinstance(ins.data, list) else ins.data
    return str(row["id"])


def _generate_for_channel(
    company_id: str,
    user_id: str,
    channel: str,
    period: str,
    fmt: str,
    extra_params: Optional[Dict[str, Any]] = None,
) -> tuple[List[str], List[Any], List[DispatchFileDownload]]:
    export_ids: List[str] = []
    all_files: List[Any] = []
    extra_params = extra_params or {}

    for export_type in CHANNEL_GENERATE_TYPES[channel]:
        req_format: str = fmt
        if export_type == "fec":
            req_format = "csv"
        req = ExportGenerateRequest(
            export_type=cast(Any, export_type),
            period=period,
            company_id=company_id,
            format=cast(Any, req_format),
            filters={},
        )
        if channel == "banque":
            if extra_params.get("execution_date"):
                req.execution_date = extra_params["execution_date"]
            if extra_params.get("payment_label"):
                req.payment_label = extra_params["payment_label"]

        result = export_service.generate_export(company_id, user_id, req)
        export_id = str(getattr(result, "export_id", "") or "")
        if not export_id:
            raise RuntimeError(f"Génération sans export_id pour {export_type}")
        export_ids.append(export_id)
        all_files.extend(getattr(result, "files", []) or [])

    downloads = _collect_downloads(export_ids, company_id)
    return export_ids, all_files, downloads


def dispatch_compta(
    company_id: str, user_id: str, body: DispatchComptaRequest
) -> DispatchResultResponse:
    preview = _preview_channel(company_id, "compta", body.period)
    if not preview["can_generate"]:
        raise ValueError(
            "Génération impossible : anomalies bloquantes sur la période sélectionnée."
        )

    export_ids, files, downloads = _generate_for_channel(
        company_id, user_id, "compta", body.period, body.format
    )
    dispatch_id = _upsert_dispatch(
        company_id,
        "compta",
        body.period,
        user_id,
        export_ids,
        {"format": body.format},
    )
    return DispatchResultResponse(
        dispatch_id=dispatch_id,
        channel="compta",
        period=body.period,
        status=STATUS_GENERATED,
        export_ids=export_ids,
        files=files,
        downloads=downloads,
        message=f"Export comptable généré pour {body.period} (OD globale + journal + FEC).",
    )


def dispatch_banque(
    company_id: str, user_id: str, body: DispatchBanqueRequest
) -> DispatchResultResponse:
    preview = _preview_channel(company_id, "banque", body.period)
    if not preview["can_generate"]:
        raise ValueError(
            "Génération impossible : anomalies bloquantes sur la période sélectionnée."
        )

    params: Dict[str, Any] = {"format": body.format}
    if body.execution_date:
        params["execution_date"] = body.execution_date
    if body.payment_label:
        params["payment_label"] = body.payment_label

    export_ids, files, downloads = _generate_for_channel(
        company_id,
        user_id,
        "banque",
        body.period,
        body.format,
        params,
    )
    dispatch_id = _upsert_dispatch(
        company_id, "banque", body.period, user_id, export_ids, params
    )
    return DispatchResultResponse(
        dispatch_id=dispatch_id,
        channel="banque",
        period=body.period,
        status=STATUS_GENERATED,
        export_ids=export_ids,
        files=files,
        downloads=downloads,
        message=f"Fichier virement généré pour {body.period}.",
    )


def mark_transmitted(
    dispatch_id: str,
    company_id: str,
    user_id: str,
    note: Optional[str] = None,
) -> MarkDispatchTransmittedResponse:
    r = (
        supabase.table("export_dispatches")
        .select("*")
        .eq("id", dispatch_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    if not r.data:
        raise ValueError("Envoi introuvable.")

    now = _utc_now()
    up = (
        supabase.table("export_dispatches")
        .update(
            {
                "status": STATUS_TRANSMITTED,
                "transmitted_at": now.isoformat(),
                "transmitted_by": user_id,
                "transmission_note": note,
            }
        )
        .eq("id", dispatch_id)
        .eq("company_id", company_id)
        .execute()
    )
    if not up.data:
        raise RuntimeError("Mise à jour transmission impossible")

    return MarkDispatchTransmittedResponse(
        dispatch_id=dispatch_id,
        status=STATUS_TRANSMITTED,
        transmitted_at=now,
        message="Envoi marqué comme transmis.",
    )


def get_dispatch_history(
    company_id: str,
    channel: Optional[str] = None,
    limit: int = 10,
) -> DispatchHistoryResponse:
    q = (
        supabase.table("export_dispatches")
        .select("*")
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if channel:
        q = q.eq("channel", channel)
    r = q.execute()
    rows = [x for x in (r.data or []) if isinstance(x, dict)]

    user_ids = list({str(row.get("created_by")) for row in rows if row.get("created_by")})
    profiles_map = export_infra_queries.get_profiles_map(user_ids)

    entries: List[DispatchHistoryEntry] = []
    for row in rows:
        created_by = row.get("created_by")
        profile = profiles_map.get(created_by) if created_by else None
        user_name = mappers.build_display_name_from_profile(profile)
        export_ids = row.get("export_ids") or []
        if not isinstance(export_ids, list):
            export_ids = []
        db_status = str(row.get("status") or STATUS_GENERATED)
        status = (
            db_status
            if db_status in (STATUS_GENERATED, STATUS_TRANSMITTED, STATUS_FAILED)
            else STATUS_GENERATED
        )
        entries.append(
            DispatchHistoryEntry(
                id=str(row["id"]),
                channel=str(row.get("channel") or "compta"),
                period=str(row.get("period") or ""),
                status=status,
                export_ids=[str(x) for x in export_ids],
                generated_at=row.get("created_at") or _utc_now(),
                transmitted_at=row.get("transmitted_at"),
                transmission_note=row.get("transmission_note"),
                created_by_name=user_name,
            )
        )
    return DispatchHistoryResponse(dispatches=entries, total=len(entries))
