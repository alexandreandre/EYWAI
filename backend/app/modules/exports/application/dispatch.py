"""
Envois compta / banque : génération groupée et suivi de transmission.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, cast

from app.core.database import supabase

from app.modules.exports.application import service as export_service
from app.modules.exports.application.notifications import notify_export_recipients
from app.modules.exports.application.scheduled_exports import _get_channel_schedule_row
from app.modules.exports.infrastructure import mappers
from app.modules.exports.infrastructure import queries as export_infra_queries
from app.modules.exports.schemas import (
    ExportGenerateRequest,
    ExportPreviewRequest,
    ExportPreviewResponse,
)
from app.modules.exports.schemas.dispatch import (
    DispatchBanqueRequest,
    DispatchBlockingAnomaly,
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

# Type d'export utilisé pour les totaux affichés sur la carte du canal.
# Pour la compta, le journal de paie expose total_brut + nombre de salariés,
# contrairement à l'OD globale (total_debit uniquement).
CHANNEL_TOTALS_TYPE: Dict[str, str] = {
    "compta": "journal_paie",
    "banque": "virement_salaires",
}

EXPORT_TYPE_LABELS: Dict[str, str] = {
    "od_globale": "OD globale",
    "journal_paie": "Journal de paie",
    "fec": "FEC",
    "virement_salaires": "Virement salaires",
}

STATUS_PENDING = "pending"
STATUS_GENERATED = "generated"
STATUS_TRANSMITTED = "transmitted"
STATUS_FAILED = "failed"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _remediation_action(
    export_type: str,
    message: str,
    employee_id: Optional[str] = None,
    employee_name: Optional[str] = None,
) -> tuple[str, str]:
    """Un seul bouton d'action par anomalie — chemin frontend exact."""
    msg = message.lower()
    if employee_id and "iban" in msg:
        who = employee_name or "le salarié"
        return (f"Corriger l'IBAN de {who}", f"/employees/{employee_id}")
    if "iban" in msg:
        return ("Ouvrir les collaborateurs", "/employees")
    if employee_id and "montant" in msg and ("≤ 0" in message or "<= 0" in msg):
        who = employee_name or "le salarié"
        return (f"Corriger le bulletin de {who}", f"/payroll/{employee_id}")
    if employee_id and ("doublon" in msg or "bulletin invalide" in msg):
        who = employee_name or "le salarié"
        return (f"Ouvrir le bulletin de {who}", f"/payroll/{employee_id}")
    if "équilibr" in msg or "equilibr" in msg or "fec invalide" in msg:
        return ("Contrôler la paie du mois", "/payroll")
    if "aucune écriture" in msg:
        return (
            "Configurer les mappings comptables",
            "/exports?tab=paie-comptabilite#accounting-mappings",
        )
    if export_type == "virement_salaires":
        return (
            "Ouvrir le virement salaires",
            "/exports?tab=paiements&export=virement-salaires",
        )
    if export_type == "journal_paie":
        if "aucun bulletin" in msg or "bulletin" in msg:
            return ("Générer la paie du mois", "/payroll")
        return (
            "Ouvrir le journal de paie",
            "/exports?tab=paie-comptabilite&export=journal_paie",
        )
    if export_type in ("od_globale", "fec"):
        return ("Contrôler la paie du mois", "/payroll")
    return ("Ouvrir Paie & Comptabilité", "/exports?tab=paie-comptabilite")


def _context_note_for(export_type: str, message: str) -> Optional[str]:
    msg = message.lower()
    if "équilibr" in msg or "equilibr" in msg or "fec invalide" in msg:
        return (
            "Écart comptable : vérifiez d'abord les bulletins (votre périmètre RH). "
            "Si la paie est correcte, les mappings comptables doivent être validés "
            "par la comptabilité (Exports → Paie & Comptabilité → Mappings en bas de page)."
        )
    if "aucune écriture" in msg:
        return (
            "Aucune écriture générée : assurez-vous que la paie du mois est bien produite, "
            "puis faites configurer les comptes par rubrique avec la comptabilité si besoin."
        )
    if export_type in ("od_globale", "fec") and "mappings" in msg:
        return (
            "Point comptable : faites valider les mappings avec votre comptable "
            "si les bulletins vous semblent corrects."
        )
    return None


def _extract_balance_debug(preview: ExportPreviewResponse) -> Optional[Dict[str, Any]]:
    details = preview.details or {}
    debug = details.get("balance_debug")
    return debug if isinstance(debug, dict) else None


def _to_blocking_anomaly(
    export_type: str,
    label: str,
    message: str,
    employee_id: Optional[str] = None,
    employee_name: Optional[str] = None,
    balance_debug: Optional[Dict[str, Any]] = None,
) -> DispatchBlockingAnomaly:
    action_label, action_path = _remediation_action(
        export_type, message, employee_id, employee_name
    )
    return DispatchBlockingAnomaly(
        source_key=export_type,
        source_label=label,
        message=message,
        employee_id=employee_id,
        employee_name=employee_name,
        action_label=action_label,
        action_path=action_path,
        context_note=_context_note_for(export_type, message),
        balance_debug=balance_debug,
    )


def _is_equilibre_anomaly(anomaly: DispatchBlockingAnomaly) -> bool:
    msg = anomaly.message.lower()
    return (
        anomaly.source_key in ("od_globale", "fec")
        and (
            "équilibr" in msg
            or "equilibr" in msg
            or "fec invalide" in msg
        )
    )


def _dedupe_blocking_anomalies(
    anomalies: List[DispatchBlockingAnomaly],
) -> List[DispatchBlockingAnomaly]:
    """OD globale et FEC signalent le même déséquilibre — une seule entrée."""
    equilibre_items = [a for a in anomalies if _is_equilibre_anomaly(a)]
    if len(equilibre_items) < 2:
        return anomalies

    best_message = equilibre_items[0].message
    for item in equilibre_items:
        if "écart" in item.message.lower():
            best_message = item.message
            break

    balance_debug = next(
        (a.balance_debug for a in equilibre_items if a.balance_debug), None
    )
    merged = DispatchBlockingAnomaly(
        source_key="od_globale",
        source_label="Écritures comptables",
        message=best_message,
        action_label="Contrôler la paie du mois",
        action_path="/payroll",
        context_note=_context_note_for("od_globale", best_message),
        balance_debug=balance_debug,
    )
    others = [a for a in anomalies if not _is_equilibre_anomaly(a)]
    return others + [merged]


def _synthetic_blocking_anomaly(
    export_type: str,
    preview: ExportPreviewResponse,
) -> Optional[DispatchBlockingAnomaly]:
    """Raison explicite quand can_generate=False sans anomalie bloquante listée."""
    if preview.can_generate:
        return None
    label = EXPORT_TYPE_LABELS.get(export_type, export_type)
    if export_type == "virement_salaires":
        if preview.employees_count == 0:
            message = "Aucun virement à générer — paie absente ou nets à zéro"
        else:
            message = "Virement salaires non générable pour cette période"
    elif export_type == "journal_paie":
        if preview.employees_count == 0:
            message = "Aucun bulletin de paie validé pour cette période"
        else:
            message = "Journal de paie non générable pour cette période"
    elif export_type == "od_globale":
        message = "OD globale non générable — paie ou mappings comptables incomplets"
    elif export_type == "fec":
        message = "FEC non générable — écritures comptables non prêtes"
    else:
        message = "Export non générable pour cette période"
    return _to_blocking_anomaly(export_type, label, message)


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
    return r.data if r and r.data else None


def _preview_channel(company_id: str, channel: str, period: str) -> Dict[str, Any]:
    """Valide l'ensemble des exports réellement générés pour le canal.

    L'envoi compta produit OD globale + journal de paie + FEC : chacun a ses
    propres contrôles bloquants (ex. FEC refusé si OD déséquilibrée). On agrège
    donc les anomalies bloquantes de tous les types générés pour éviter qu'une
    prévisualisation « verte » débouche sur une génération en erreur.
    """
    totals_type = CHANNEL_TOTALS_TYPE.get(channel, CHANNEL_PREVIEW_TYPE[channel])
    generate_types = CHANNEL_GENERATE_TYPES.get(channel, [CHANNEL_PREVIEW_TYPE[channel]])

    blocking_details: List[DispatchBlockingAnomaly] = []
    totals: Any = None

    for export_type in generate_types:
        req = ExportPreviewRequest(export_type=cast(Any, export_type), period=period)
        preview = export_service.preview_export(company_id, req)
        label = EXPORT_TYPE_LABELS.get(export_type, export_type)
        type_had_blocking = False
        for a in preview.anomalies:
            if a.severity == "blocking" or a.type == "error":
                type_had_blocking = True
                blocking_details.append(
                    _to_blocking_anomaly(
                        export_type,
                        label,
                        a.message,
                        a.employee_id,
                        a.employee_name,
                        balance_debug=_extract_balance_debug(preview)
                        if export_type in ("od_globale", "fec")
                        else None,
                    )
                )
        if not preview.can_generate and not type_had_blocking:
            synthetic = _synthetic_blocking_anomaly(export_type, preview)
            if synthetic:
                blocking_details.append(synthetic)
        if export_type == totals_type:
            totals = preview.totals

    if totals is None:
        # Repli : aucune preview du type d'affichage n'a abouti.
        req = ExportPreviewRequest(
            export_type=cast(Any, CHANNEL_PREVIEW_TYPE[channel]), period=period
        )
        totals = export_service.preview_export(company_id, req).totals

    blocking_details = _dedupe_blocking_anomalies(blocking_details)

    return {
        "can_generate": len(blocking_details) == 0,
        "blocking_anomalies_count": len(blocking_details),
        "blocking_anomalies": blocking_details,
        "totals": totals,
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
            blocking_anomalies=preview_info.get("blocking_anomalies") or [],
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
        blocking_anomalies=preview_info.get("blocking_anomalies") or [],
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
            exp = export_infra_queries.get_export_by_id(export_id, company_id)
            if not exp:
                continue
            export_type = str(exp.get("export_type") or "")
            for file_info in export_service.get_export_download_files(company_id, export_id):
                downloads.append(
                    DispatchFileDownload(
                        export_id=export_id,
                        export_type=export_type,
                        filename=file_info["filename"],
                        download_url=file_info["download_url"],
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
    status: str = STATUS_GENERATED,
) -> str:
    existing = _get_dispatch_row(company_id, channel, period)
    payload: Dict[str, Any] = {
        "company_id": company_id,
        "channel": channel,
        "period": period,
        "status": status,
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
                    "status": status,
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
    parameters: Dict[str, Any] = {"format": fmt, **extra_params}

    try:
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
    except Exception as exc:
        if export_ids:
            _upsert_dispatch(
                company_id,
                channel,
                period,
                user_id,
                export_ids,
                {**parameters, "error": str(exc), "partial": True},
                status=STATUS_FAILED,
            )
        raise

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
    api_msg = ""
    tx_result = None
    transmission_status = None
    transmission_provider = None
    try:
        from app.modules.accounting_integration.application import (
            service as accounting_service,
        )
        from app.modules.accounting_integration.infrastructure import (
            repository as accounting_repository,
        )
        from app.modules.exports.infrastructure.storage import download_export_file

        file_payloads: list[tuple[str, bytes]] = []
        for dl in downloads:
            exp = export_infra_queries.get_export_by_id(dl.export_id, company_id)
            if not exp:
                continue
            for entry in exp.get("file_paths") or []:
                if isinstance(entry, dict):
                    path = str(entry.get("path") or "")
                    name = str(entry.get("filename") or path.rsplit("/", 1)[-1])
                else:
                    path = str(entry)
                    name = path.rsplit("/", 1)[-1]
                if path:
                    try:
                        file_payloads.append((name, download_export_file(path)))
                    except Exception:
                        continue
        tx_result = accounting_service.transmit_compta_files(
            company_id,
            file_payloads,
            {"period": body.period, "channel": "compta"},
            user_id=user_id,
            export_ids=export_ids,
            force_manual=bool(body.force_manual),
        )
        if tx_result.message:
            api_msg = f" {tx_result.message}"
        transmission_status = tx_result.status
        cfg = accounting_repository.get_config(company_id) or {}
        transmission_provider = str(cfg.get("provider") or "manual")
    except Exception:
        api_msg = ""
        tx_result = None
        transmission_status = None
        transmission_provider = None

    dispatch_status = STATUS_GENERATED
    if transmission_status in ("sent", "acknowledged"):
        dispatch_status = STATUS_TRANSMITTED

    dispatch_id = _upsert_dispatch(
        company_id,
        "compta",
        body.period,
        user_id,
        export_ids,
        {
            "format": body.format,
            "force_manual": body.force_manual,
            "transmission_status": transmission_status,
        },
        status=dispatch_status if dispatch_status == STATUS_TRANSMITTED else STATUS_GENERATED,
    )
    msg = f"Export comptable généré pour {body.period} (OD globale + journal + FEC).{api_msg}"
    schedule_row = None
    try:
        schedule_row = _get_channel_schedule_row(company_id, "compta")
    except Exception:
        schedule_row = None
    if schedule_row:
        rec = schedule_row.get("recipients") or []
        if isinstance(rec, list) and rec:
            notify = notify_export_recipients(
                company_id,
                [str(x) for x in rec if x],
                export_ids,
                export_type_label="Comptabilité",
                period=body.period,
                channel="compta",
            )
            if notify.message:
                msg = f"{msg} {notify.message}"
    return DispatchResultResponse(
        dispatch_id=dispatch_id,
        channel="compta",
        period=body.period,
        status=dispatch_status,
        export_ids=export_ids,
        files=files,
        downloads=downloads,
        message=msg,
        transmission_id=tx_result.transmission_id if tx_result else None,
        transmission_status=transmission_status,
        transmission_provider=transmission_provider,
        transmission_manual_fallback=bool(tx_result.manual_fallback) if tx_result else False,
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
    msg = f"Fichier virement généré pour {body.period}."
    schedule_row = None
    try:
        schedule_row = _get_channel_schedule_row(company_id, "banque")
    except Exception:
        schedule_row = None
    if schedule_row:
        rec = schedule_row.get("recipients") or []
        if isinstance(rec, list) and rec:
            notify = notify_export_recipients(
                company_id,
                [str(x) for x in rec if x],
                export_ids,
                export_type_label="Banque",
                period=body.period,
                channel="banque",
            )
            if notify.message:
                msg = f"{msg} {notify.message}"
    return DispatchResultResponse(
        dispatch_id=dispatch_id,
        channel="banque",
        period=body.period,
        status=STATUS_GENERATED,
        export_ids=export_ids,
        files=files,
        downloads=downloads,
        message=msg,
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
    if not r or not r.data:
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
