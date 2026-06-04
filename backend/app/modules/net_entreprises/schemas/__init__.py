"""Schémas API du module net_entreprises."""

from app.modules.net_entreprises.schemas.requests import (
    NetEntreprisesConfigUpdate,
    MarkTransmittedRequest,
)
from app.modules.net_entreprises.schemas.responses import (
    NetEntreprisesConfigResponse,
    ConnectionTestResponse,
    DSNTransmissionEntry,
    DSNTransmissionsResponse,
    AdminDSNTransmissionEntry,
    AdminDSNTransmissionsResponse,
)

__all__ = [
    "NetEntreprisesConfigUpdate",
    "MarkTransmittedRequest",
    "NetEntreprisesConfigResponse",
    "ConnectionTestResponse",
    "DSNTransmissionEntry",
    "DSNTransmissionsResponse",
    "AdminDSNTransmissionEntry",
    "AdminDSNTransmissionsResponse",
]
