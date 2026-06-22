"""Service applicatif net_entreprises.

Responsabilités :
  - résoudre le connecteur adapté (fallback systématique sur le mode manuel) ;
  - exposer config (masquée), test de connexion, suivi des transmissions ;
  - point d'entrée `record_and_transmit_dsn` appelé par le module exports après
    génération du fichier XML.

Garde-fou : aucune fonction ne doit faire planter l'appelant. Les appels API
risqués sont encapsulés et retombent toujours sur le mode manuel.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core import settings
from app.core.logging import get_logger
from app.modules.net_entreprises.domain.interfaces import (
    AbstractNetEntreprisesConnector,
    NetEntreprisesError,
)
from app.modules.net_entreprises.domain.value_objects import (
    ConnectionTestResult,
    TransmissionMode,
    TransmissionStatus,
    is_api_mode,
)
from app.modules.net_entreprises.infrastructure import repository
from app.modules.net_entreprises.infrastructure.api_connector import (
    NetEntreprisesApiConnector,
)
from app.modules.net_entreprises.infrastructure.manual_connector import (
    ManualNetEntreprisesConnector,
)
from app.modules.net_entreprises.schemas.responses import (
    AdminDSNTransmissionEntry,
    AdminDSNTransmissionsResponse,
    ConnectionTestResponse,
    DSNTransmissionEntry,
    DSNTransmissionsResponse,
    NetEntreprisesConfigResponse,
)

logger = get_logger("modules.net_entreprises.service")

_MANUAL = ManualNetEntreprisesConnector()


def _api_enabled() -> bool:
    """Le flag global autorise-t-il les appels API ?"""
    return bool(getattr(settings, "NET_ENTREPRISES_ENABLED", False))


def resolve_connector(config: Optional[Dict[str, Any]]) -> AbstractNetEntreprisesConnector:
    """Choisit le connecteur. Fallback manuel si désactivé / non configuré.

    Le mode API n'est retenu que si TOUTES les conditions sont réunies :
      - flag global NET_ENTREPRISES_ENABLED actif ;
      - config entreprise présente, `enabled=true` et mode API.
    """
    if not config:
        return _MANUAL
    if not config.get("enabled"):
        return _MANUAL
    mode = config.get("mode") or TransmissionMode.MANUAL.value
    if is_api_mode(mode) and _api_enabled():
        return NetEntreprisesApiConnector(mode=mode)
    return _MANUAL


def _connection_state(config: Optional[Dict[str, Any]]) -> str:
    """État synthétique pour l'UI."""
    if not config:
        return "not_configured"
    mode = config.get("mode") or TransmissionMode.MANUAL.value
    if config.get("enabled") and is_api_mode(mode) and _api_enabled():
        return "connected"
    if config.get("enabled"):
        return "manual"
    return "not_configured"


# --- Config -----------------------------------------------------------------


def get_config(company_id: str) -> NetEntreprisesConfigResponse:
    """Retourne la config (sans secret)."""
    row = repository.get_config(company_id)
    if not row:
        return NetEntreprisesConfigResponse()
    return _config_to_response(row)


def _config_to_response(row: Dict[str, Any]) -> NetEntreprisesConfigResponse:
    return NetEntreprisesConfigResponse(
        enabled=bool(row.get("enabled")),
        mode=row.get("mode") or "manual",
        siret_declarant=row.get("siret_declarant"),
        raison_sociale_declarant=row.get("raison_sociale_declarant"),
        identifiant=row.get("identifiant"),
        contact_email=row.get("contact_email"),
        certificat_label=row.get("certificat_label"),
        certificat_expires_at=row.get("certificat_expires_at"),
        has_secret=bool(row.get("secret_ref")),
        last_test_at=row.get("last_test_at"),
        last_test_status=row.get("last_test_status"),
        last_test_message=row.get("last_test_message"),
        connection_state=_connection_state(row),
    )


_ALLOWED_MODES = {m.value for m in TransmissionMode}


def update_config(
    company_id: str, fields: Dict[str, Any], user_id: Optional[str] = None
) -> NetEntreprisesConfigResponse:
    """Crée/met à jour la config. Le secret en clair est stocké via secret_ref.

    Lève ValueError si le mode est invalide.
    """
    payload: Dict[str, Any] = {}
    for key in (
        "enabled",
        "mode",
        "siret_declarant",
        "raison_sociale_declarant",
        "identifiant",
        "contact_email",
        "certificat_label",
        "certificat_expires_at",
    ):
        if key in fields and fields[key] is not None:
            payload[key] = fields[key]

    if "mode" in payload and payload["mode"] not in _ALLOWED_MODES:
        raise ValueError(
            f"Mode invalide : {payload['mode']} (attendu : {', '.join(sorted(_ALLOWED_MODES))})"
        )

    # Le secret en clair n'est jamais relu : on stocke une référence opaque.
    # (placeholder ; le stockage chiffré réel sera branché avec l'API.)
    secret = fields.get("secret")
    if secret:
        payload["secret_ref"] = "set"
    if user_id:
        payload["updated_by"] = user_id

    row = repository.upsert_config(company_id, payload)
    if not row:
        # Lecture de repli pour rester cohérent.
        return get_config(company_id)
    return _config_to_response(row)


def test_connection(company_id: str) -> ConnectionTestResponse:
    """Teste la connexion via le connecteur résolu. Ne lève jamais."""
    config = repository.get_config(company_id)
    connector = resolve_connector(config)
    try:
        result: ConnectionTestResult = connector.test_connection(config or {})
    except Exception as e:  # garde-fou absolu
        logger.exception("Test connexion net_entreprises échoué (company=%s)", company_id)
        result = ConnectionTestResult(
            success=False,
            status="failure",
            message=f"Échec du test de connexion : {e}",
        )
    repository.update_test_result(company_id, result.status, result.message)
    return ConnectionTestResponse(
        success=result.success, status=result.status, message=result.message
    )


# --- Transmissions (suivi entreprise) ---------------------------------------


def list_transmissions(
    company_id: str, period: Optional[str] = None
) -> DSNTransmissionsResponse:
    rows = repository.list_transmissions_by_company(company_id, period)
    return DSNTransmissionsResponse(
        transmissions=[_transmission_to_entry(r) for r in rows]
    )


def _transmission_to_entry(row: Dict[str, Any]) -> DSNTransmissionEntry:
    return DSNTransmissionEntry(
        id=str(row.get("id")),
        period=row.get("period") or "",
        dsn_type=row.get("dsn_type") or "dsn_mensuelle_normale",
        status=row.get("status") or "generated",
        mode=row.get("mode") or "manual",
        net_entreprises_ref=row.get("net_entreprises_ref"),
        submitted_at=row.get("submitted_at"),
        acknowledged_at=row.get("acknowledged_at"),
        error_message=row.get("error_message"),
        crm_retour=row.get("crm_retour"),
        created_at=row.get("created_at"),
    )


def mark_transmitted(
    company_id: str, transmission_id: str, net_entreprises_ref: Optional[str]
) -> DSNTransmissionEntry:
    """Mode manuel : marque une transmission comme déposée (accusé)."""
    existing = repository.get_transmission(company_id, transmission_id)
    if not existing:
        raise LookupError("Transmission non trouvée")
    fields: Dict[str, Any] = {
        "status": TransmissionStatus.ACKNOWLEDGED.value,
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
    }
    if net_entreprises_ref:
        fields["net_entreprises_ref"] = net_entreprises_ref
    if not existing.get("submitted_at"):
        fields["submitted_at"] = datetime.now(timezone.utc).isoformat()
    updated = repository.update_transmission(transmission_id, fields)
    return _transmission_to_entry(updated or {**existing, **fields})


# --- Suivi plateforme (super-admin) -----------------------------------------


def list_all_transmissions_admin(
    status: Optional[str] = None,
    period: Optional[str] = None,
    company_names: Optional[Dict[str, str]] = None,
) -> AdminDSNTransmissionsResponse:
    rows = repository.list_all_transmissions(status=status, period=period)
    if company_names is None:
        company_ids = [str(r.get("company_id")) for r in rows if r.get("company_id")]
        company_names = repository.get_company_names(company_ids)
    names = company_names or {}
    entries: List[AdminDSNTransmissionEntry] = []
    counts: Dict[str, int] = {}
    for r in rows:
        base = _transmission_to_entry(r)
        cid = str(r.get("company_id"))
        entries.append(
            AdminDSNTransmissionEntry(
                **base.model_dump(),
                company_id=cid,
                company_name=names.get(cid),
            )
        )
        counts[base.status] = counts.get(base.status, 0) + 1
    return AdminDSNTransmissionsResponse(transmissions=entries, counts_by_status=counts)


# --- Branchement génération DSN (appelé par le module exports) --------------


def record_and_transmit_dsn(
    company_id: str,
    export_id: Optional[str],
    period: str,
    dsn_type: str,
    xml_content: bytes,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée le suivi de transmission et tente l'envoi si l'API est active.

    Ne lève jamais : en cas d'erreur ou d'API non branchée, retombe sur le mode
    manuel. Retourne un dict {transmission_id, status, mode, message}.
    """
    config = repository.get_config(company_id)
    connector = resolve_connector(config)
    mode = getattr(connector, "mode", TransmissionMode.MANUAL.value)

    record: Dict[str, Any] = {
        "company_id": company_id,
        "export_id": export_id,
        "period": period,
        "dsn_type": dsn_type,
        "status": TransmissionStatus.GENERATED.value,
        "mode": mode,
        "created_by": user_id,
    }
    transmission_id = repository.insert_transmission(record)

    # Mode manuel : on s'arrête là (statut manual), aucun appel réseau.
    if mode == TransmissionMode.MANUAL.value:
        result = _MANUAL.submit_dsn(config or {}, xml_content, {"period": period})
        if transmission_id:
            repository.update_transmission(
                transmission_id, {"status": result.status, "mode": result.mode}
            )
        return {
            "transmission_id": transmission_id,
            "status": result.status,
            "mode": result.mode,
            "message": result.message,
        }

    # Mode API : tentative encapsulée, fallback manuel en cas d'échec.
    try:
        result = connector.submit_dsn(
            config or {}, xml_content, {"period": period, "dsn_type": dsn_type}
        )
        if transmission_id:
            repository.update_transmission(
                transmission_id,
                {
                    "status": result.status,
                    "mode": result.mode,
                    "net_entreprises_ref": result.net_entreprises_ref,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "crm_retour": result.crm_retour,
                },
            )
        return {
            "transmission_id": transmission_id,
            "status": result.status,
            "mode": result.mode,
            "message": result.message,
        }
    except NetEntreprisesError as e:
        logger.warning("Envoi API Net-entreprises indisponible : %s", e)
    except Exception:
        logger.exception("Envoi API Net-entreprises échoué (company=%s)", company_id)

    # Fallback manuel.
    if transmission_id:
        repository.update_transmission(
            transmission_id,
            {
                "status": TransmissionStatus.MANUAL.value,
                "mode": TransmissionMode.MANUAL.value,
            },
        )
    from app.modules.net_entreprises.infrastructure.manual_connector import MANUAL_MESSAGE

    return {
        "transmission_id": transmission_id,
        "status": TransmissionStatus.MANUAL.value,
        "mode": TransmissionMode.MANUAL.value,
        "message": MANUAL_MESSAGE,
    }
