"""Service applicatif intégration comptable."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core import settings
from app.core.logging import get_logger
from app.modules.accounting_integration.domain.providers import (
    PROVIDER_REGISTRY,
    get_provider_definition,
    list_provider_definitions,
    mode_from_provider_key,
    provider_key_from_mode,
)
from app.modules.accounting_integration.domain.value_objects import (
    TransmissionMode,
    TransmissionStatus,
    is_api_mode,
)
from app.modules.accounting_integration.infrastructure.connector_factory import (
    resolve_connector,
)
from app.modules.accounting_integration.infrastructure.cegid_quadra_connector import (
    CegidQuadraConnector,
    has_complete_cegid_credentials,
    parse_cegid_credentials,
)
from app.modules.accounting_integration.infrastructure import repository
from app.modules.accounting_integration.schemas.responses import (
    AccountingConfigResponse,
    AccountingConfigUpdate,
    AccountingTransmissionEntry,
    AccountingTransmissionsResponse,
    ConnectionTestResponse,
    PlatformCatalogResponse,
    PlatformProviderEntry,
    PlatformProviderUpdate,
    ProviderDefinitionResponse,
    ProvidersListResponse,
    TransmitComptaResult,
)
from app.shared.utils.secret_store import encrypt_secret, has_stored_secret

logger = get_logger("modules.accounting_integration.service")


def _api_globally_enabled() -> bool:
    return bool(getattr(settings, "ACCOUNTING_API_ENABLED", False))


def _connection_state(
    config: Optional[Dict[str, Any]],
    platform_row: Optional[Dict[str, Any]] = None,
) -> str:
    if not config or not config.get("enabled"):
        return "not_configured"
    if config.get("force_manual"):
        return "manual"
    provider_key = str(config.get("provider") or provider_key_from_mode(
        str(config.get("mode") or "manual")
    ))
    mode = str(config.get("mode") or "manual")
    if mode == "manual" or provider_key == "manual":
        return "manual"
    definition = get_provider_definition(provider_key)
    if platform_row is not None and not platform_row.get("enabled"):
        return "not_configured"
    if definition and definition.connector_class == "cegid_quadra":
        if (
            _api_globally_enabled()
            and has_complete_cegid_credentials(config)
            and config.get("last_test_status") == "connected"
        ):
            return "connected"
        if has_stored_secret(config.get("credentials_ref")):
            return "failed" if config.get("last_test_status") == "failed" else "not_configured"
        return "not_configured"
    if is_api_mode(mode):
        return "stub"
    return "manual"


def _config_to_response(
    row: Optional[Dict[str, Any]],
    platform_row: Optional[Dict[str, Any]] = None,
) -> AccountingConfigResponse:
    if not row:
        return AccountingConfigResponse()
    rec = row.get("recipients_compta") or []
    if not isinstance(rec, list):
        rec = []
    provider = str(row.get("provider") or provider_key_from_mode(
        str(row.get("mode") or "manual")
    ))
    cegid_complete = (
        provider == "cegid_quadra" and has_complete_cegid_credentials(row)
    )
    return AccountingConfigResponse(
        enabled=bool(row.get("enabled")),
        mode=row.get("mode") or "manual",
        provider=provider,
        default_format=row.get("default_format") or "csv",
        recipients_compta=[str(x) for x in rec if x],
        has_credentials=has_stored_secret(row.get("credentials_ref")),
        cegid_credentials_complete=cegid_complete,
        force_manual=bool(row.get("force_manual")),
        last_transmission_at=row.get("last_transmission_at"),
        last_test_at=row.get("last_test_at"),
        last_test_status=row.get("last_test_status"),
        last_test_message=row.get("last_test_message"),
        connection_state=_connection_state(row, platform_row),
    )


def get_config(company_id: str) -> AccountingConfigResponse:
    row = repository.get_config(company_id)
    provider_key = str((row or {}).get("provider") or "manual")
    platform_row = repository.get_platform_provider(provider_key)
    return _config_to_response(row, platform_row)


def update_config(
    company_id: str, body: AccountingConfigUpdate
) -> AccountingConfigResponse:
    fields = body.model_dump(exclude_unset=True)
    credentials = fields.pop("credentials", None)
    if credentials is not None:
        fields["credentials_ref"] = encrypt_secret(credentials)
        definition = get_provider_definition(str(fields.get("provider") or "manual"))
        if definition:
            fields.setdefault("auth_type", definition.auth_type)
    if "provider" in fields and "mode" not in fields:
        fields["mode"] = mode_from_provider_key(str(fields["provider"]))
    if "mode" in fields and "provider" not in fields:
        fields["provider"] = provider_key_from_mode(str(fields["mode"]))
    repository.upsert_config(company_id, fields)
    return get_config(company_id)


def test_connection(company_id: str) -> ConnectionTestResponse:
    row = repository.get_config(company_id) or {"enabled": False, "mode": "manual"}
    provider_key = str(row.get("provider") or provider_key_from_mode(
        str(row.get("mode") or "manual")
    ))
    platform_row = repository.get_platform_provider(provider_key)
    connector = resolve_connector(row, platform_row, force_manual=bool(row.get("force_manual")))
    result = connector.test_connection(row)
    update_fields: Dict[str, Any] = {
        "last_test_at": datetime.now(timezone.utc).isoformat(),
        "last_test_status": result.status,
        "last_test_message": result.message,
    }
    if result.success and provider_key == "cegid_quadra":
        update_fields["enabled"] = True
    repository.upsert_config(company_id, update_fields)
    return ConnectionTestResponse(
        success=result.success,
        status=result.status,
        message=result.message,
    )


def list_providers_for_company(company_id: str) -> ProvidersListResponse:
    platform_rows = {r["provider_key"]: r for r in repository.list_platform_providers()}
    items: List[ProviderDefinitionResponse] = []
    for definition in list_provider_definitions():
        platform_row = platform_rows.get(definition.key)
        platform_enabled = (
            True if definition.key == "manual" else bool((platform_row or {}).get("enabled"))
        )
        connector_ready = definition.connector_class in ("manual", "cegid_quadra")
        items.append(
            ProviderDefinitionResponse(
                key=definition.key,
                name=definition.name,
                logo_key=definition.logo_key,
                mode=definition.mode,
                capabilities=list(definition.capabilities),
                auth_type=definition.auth_type,
                supported_formats=list(definition.supported_formats),
                doc_url=definition.doc_url,
                description=definition.description,
                platform_enabled=platform_enabled,
                connector_ready=connector_ready and (
                    definition.key == "manual" or _api_globally_enabled() or definition.connector_class == "stub"
                ),
            )
        )
    return ProvidersListResponse(providers=items)


def _transmission_to_entry(row: Dict[str, Any], company_name: Optional[str] = None) -> AccountingTransmissionEntry:
    export_ids = row.get("export_ids") or []
    if not isinstance(export_ids, list):
        export_ids = []
    return AccountingTransmissionEntry(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        company_name=company_name,
        period=str(row.get("period") or ""),
        channel=str(row.get("channel") or "compta"),
        provider=str(row.get("provider") or "manual"),
        mode=str(row.get("mode") or "manual"),
        status=row.get("status") or "generated",
        export_ids=[str(x) for x in export_ids],
        external_ref=row.get("external_ref"),
        error_message=row.get("error_message"),
        created_at=row.get("created_at"),
        submitted_at=row.get("submitted_at"),
        acknowledged_at=row.get("acknowledged_at"),
    )


def list_company_transmissions(
    company_id: str,
    *,
    period: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
) -> AccountingTransmissionsResponse:
    rows = repository.list_transmissions(
        company_id, period=period, status=status, limit=limit
    )
    entries = [_transmission_to_entry(r) for r in rows]
    counts: Dict[str, int] = {}
    for e in entries:
        counts[e.status] = counts.get(e.status, 0) + 1
    return AccountingTransmissionsResponse(
        transmissions=entries,
        total=len(entries),
        counts_by_status=counts,
    )


def transmit_compta_files(
    company_id: str,
    files: List[tuple[str, bytes]],
    metadata: Dict[str, Any],
    *,
    user_id: Optional[str] = None,
    export_ids: Optional[List[str]] = None,
    force_manual: bool = False,
) -> TransmitComptaResult:
    """Enregistre et tente une transmission. Ne bloque jamais le dispatch."""
    period = str(metadata.get("period") or "")
    channel = str(metadata.get("channel") or "compta")
    row = repository.get_config(company_id) or {}
    provider_key = str(row.get("provider") or "manual")
    mode = str(row.get("mode") or "manual")
    platform_row = repository.get_platform_provider(provider_key)

    use_manual = (
        force_manual
        or bool(row.get("force_manual"))
        or mode == TransmissionMode.MANUAL.value
        or provider_key == "manual"
        or not row.get("enabled")
    )

    if not use_manual:
        existing = repository.find_existing_transmission(company_id, period, channel)
        if existing:
            return TransmitComptaResult(
                success=True,
                status=str(existing.get("status") or "sent"),
                message="Transmission déjà enregistrée pour cette période.",
                transmission_id=str(existing.get("id")),
                external_ref=existing.get("external_ref"),
                manual_fallback=False,
            )

    transmission_id = repository.insert_transmission(
        {
            "company_id": company_id,
            "period": period,
            "channel": channel,
            "provider": provider_key,
            "mode": mode if not use_manual else "manual",
            "export_ids": export_ids or [],
            "status": TransmissionStatus.MANUAL.value if use_manual else TransmissionStatus.GENERATED.value,
            "metadata": {"filenames": [f[0] for f in files]},
            "created_by": user_id,
        }
    )

    if use_manual:
        return TransmitComptaResult(
            success=True,
            status=TransmissionStatus.MANUAL.value,
            message="Mode manuel — fichiers disponibles au téléchargement.",
            transmission_id=transmission_id,
            manual_fallback=False,
        )

    connector = resolve_connector(row, platform_row, force_manual=False)
    try:
        result = connector.submit_files(row, files, metadata)
        now = datetime.now(timezone.utc).isoformat()
        status = result.status
        if result.success:
            repository.update_transmission(
                transmission_id or "",
                {
                    "status": status,
                    "external_ref": result.external_ref,
                    "submitted_at": now,
                    "error_message": None,
                },
            )
            repository.upsert_config(company_id, {"last_transmission_at": now})
            return TransmitComptaResult(
                success=True,
                status=status,
                message=result.message,
                transmission_id=transmission_id,
                external_ref=result.external_ref,
                manual_fallback=False,
            )
        repository.update_transmission(
            transmission_id or "",
            {
                "status": TransmissionStatus.FAILED.value,
                "error_message": result.message,
            },
        )
        return TransmitComptaResult(
            success=False,
            status=TransmissionStatus.FAILED.value,
            message=result.message,
            transmission_id=transmission_id,
            manual_fallback=True,
        )
    except Exception as exc:
        logger.exception("Transmission compta API échouée")
        if transmission_id:
            repository.update_transmission(
                transmission_id,
                {
                    "status": TransmissionStatus.FAILED.value,
                    "error_message": str(exc),
                },
            )
        return TransmitComptaResult(
            success=False,
            status=TransmissionStatus.FAILED.value,
            message=f"Repli manuel : {exc}",
            transmission_id=transmission_id,
            manual_fallback=True,
        )


def try_transmit_compta_files(
    company_id: str,
    files: List[tuple[str, bytes]],
    metadata: Dict[str, Any],
) -> tuple[bool, str]:
    """Compat dispatch legacy."""
    result = transmit_compta_files(company_id, files, metadata)
    return result.success or result.manual_fallback, result.message


def retry_transmission(transmission_id: str, company_id: str) -> TransmitComptaResult:
    row = repository.get_transmission(transmission_id)
    if not row or str(row.get("company_id")) != company_id:
        return TransmitComptaResult(
            success=False,
            status="failed",
            message="Transmission introuvable.",
            manual_fallback=True,
        )
    from app.modules.exports.infrastructure.storage import download_export_file
    from app.modules.exports.infrastructure import queries as export_queries

    file_payloads: list[tuple[str, bytes]] = []
    for export_id in row.get("export_ids") or []:
        exp = export_queries.get_export_by_id(str(export_id), company_id)
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
    return transmit_compta_files(
        company_id,
        file_payloads,
        {
            "period": row.get("period"),
            "channel": row.get("channel") or "compta",
            "retry_of": transmission_id,
        },
        export_ids=[str(x) for x in (row.get("export_ids") or [])],
        force_manual=False,
    )


def poll_pending_accounting_transmissions(*, limit: int = 50) -> Dict[str, int]:
    """Polling des imports Cegid Loop en statut sent (traitement asynchrone FEC)."""
    rows = repository.list_transmissions(status=TransmissionStatus.SENT.value, limit=limit)
    stats = {"polled": 0, "transmitted": 0, "failed": 0, "unchanged": 0}
    connector = CegidQuadraConnector()

    for row in rows:
        if str(row.get("provider")) != "cegid_quadra":
            continue
        import_id = str(row.get("external_ref") or "").strip()
        if not import_id:
            continue
        company_id = str(row.get("company_id"))
        config = repository.get_config(company_id) or {}
        parsed = parse_cegid_credentials(config)
        if not parsed:
            continue
        stats["polled"] += 1
        try:
            new_status, message = connector.poll_import_status(parsed, import_id)
        except Exception as exc:
            logger.warning("Polling Cegid %s : %s", import_id, exc)
            stats["unchanged"] += 1
            continue
        if new_status == TransmissionStatus.SENT.value:
            stats["unchanged"] += 1
            continue
        now = datetime.now(timezone.utc).isoformat()
        fields: Dict[str, Any] = {
            "status": new_status,
            "error_message": message if new_status == TransmissionStatus.FAILED.value else None,
        }
        if new_status == TransmissionStatus.TRANSMITTED.value:
            fields["acknowledged_at"] = now
        repository.update_transmission(str(row["id"]), fields)
        if new_status == TransmissionStatus.TRANSMITTED.value:
            stats["transmitted"] += 1
        elif new_status == TransmissionStatus.FAILED.value:
            stats["failed"] += 1

    return stats


# --- Plateforme (super-admin) ------------------------------------------------


def _platform_entry(row: Dict[str, Any]) -> PlatformProviderEntry:
    definition = get_provider_definition(row.get("provider_key") or "")
    return PlatformProviderEntry(
        provider_key=str(row.get("provider_key")),
        name=definition.name if definition else str(row.get("provider_key")),
        logo_key=definition.logo_key if definition else "generic",
        enabled=bool(row.get("enabled")),
        has_platform_credentials=has_stored_secret(row.get("platform_credentials_ref")),
        settings=row.get("settings") or {},
        last_test_at=row.get("last_test_at"),
        last_test_status=row.get("last_test_status"),
        last_test_message=row.get("last_test_message"),
        description=definition.description if definition else "",
        connector_ready=bool(definition and definition.connector_class == "cegid_quadra"),
    )


def get_platform_catalog() -> PlatformCatalogResponse:
    rows = repository.list_platform_providers()
    if not rows:
        for key in PROVIDER_REGISTRY:
            repository.upsert_platform_provider(key, {"enabled": key == "manual"})
        rows = repository.list_platform_providers()
    entries = [_platform_entry(r) for r in rows]
    all_tx = repository.list_transmissions(limit=500)
    stats = {
        "transmissions_total": len(all_tx),
        "providers_enabled": sum(1 for e in entries if e.enabled),
        "enabled_providers": sum(1 for e in entries if e.enabled),
        "failures": sum(1 for t in all_tx if t.get("status") == "failed"),
        "sent": sum(1 for t in all_tx if t.get("status") in ("sent", "acknowledged", "transmitted")),
    }
    return PlatformCatalogResponse(providers=entries, stats=stats)


def update_platform_provider(
    provider_key: str, body: PlatformProviderUpdate
) -> PlatformProviderEntry:
    fields: Dict[str, Any] = {}
    if body.enabled is not None:
        fields["enabled"] = body.enabled
    if body.settings is not None:
        fields["settings"] = body.settings
    if body.platform_credentials is not None:
        fields["platform_credentials_ref"] = encrypt_secret(body.platform_credentials)
    row = repository.upsert_platform_provider(provider_key, fields)
    return _platform_entry(row or {"provider_key": provider_key})


def list_all_transmissions(
    *,
    company_id: Optional[str] = None,
    period: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = 100,
) -> AccountingTransmissionsResponse:
    rows = repository.list_transmissions(
        company_id,
        period=period,
        status=status,
        provider=provider,
        limit=limit,
    )
    company_names: Dict[str, str] = {}
    try:
        from app.core.database import get_supabase_admin_client

        ids = list({str(r["company_id"]) for r in rows})
        if ids:
            resp = (
                get_supabase_admin_client()
                .table("companies")
                .select("id, company_name")
                .in_("id", ids)
                .execute()
            )
            for c in resp.data or []:
                company_names[str(c["id"])] = str(c.get("company_name") or "")
    except Exception:
        pass
    entries = [
        _transmission_to_entry(r, company_names.get(str(r["company_id"])))
        for r in rows
    ]
    counts: Dict[str, int] = {}
    for e in entries:
        counts[e.status] = counts.get(e.status, 0) + 1
    return AccountingTransmissionsResponse(
        transmissions=entries,
        total=len(entries),
        counts_by_status=counts,
    )
