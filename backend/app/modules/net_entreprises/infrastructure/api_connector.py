"""Connecteur API Net-entreprises — STUB guardé.

À compléter quand les identifiants/certificat de l'entreprise seront disponibles.
En l'état, il signale proprement que la connexion n'est pas branchée
(`NetEntreprisesNotConfigured`) sans jamais effectuer d'appel réseau ni faire
planter l'application. Le service applicatif retombe alors sur le mode manuel.

Points d'extension (à implémenter le moment venu) :
  - authentification (OAuth2 / certificat client) ;
  - dépôt du fichier DSN (API « Dépôt de fichier » Net-entreprises) ;
  - récupération de l'accusé de réception et des bilans CRM.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.modules.net_entreprises.domain.interfaces import NetEntreprisesNotConfigured
from app.modules.net_entreprises.domain.value_objects import (
    ConnectionTestResult,
    TransmissionMode,
    TransmissionResult,
)

logger = get_logger("modules.net_entreprises.api_connector")

_NOT_READY_MSG = (
    "La connexion API Net-entreprises n'est pas encore disponible. "
    "Renseignez les identifiants/certificat puis activez la télétransmission, "
    "ou déposez le fichier manuellement sur net-entreprises.fr."
)


class NetEntreprisesApiConnector:
    """Connecteur API (certificat ou déclarant). Implémentation à brancher."""

    def __init__(self, mode: str = TransmissionMode.API_CERTIFICAT.value) -> None:
        self.mode = mode

    def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        logger.info("Test connexion Net-entreprises (API non branchée).")
        return ConnectionTestResult(
            success=False,
            status="not_configured",
            message=_NOT_READY_MSG,
        )

    def submit_dsn(
        self,
        config: Dict[str, Any],
        xml_content: bytes,
        metadata: Dict[str, Any],
    ) -> TransmissionResult:
        # Tant que l'API n'est pas implémentée, on signale clairement l'indisponibilité.
        # Le service applicatif intercepte cette exception et retombe en mode manuel.
        raise NetEntreprisesNotConfigured(_NOT_READY_MSG)

    def get_status(
        self, config: Dict[str, Any], net_entreprises_ref: str
    ) -> Optional[TransmissionResult]:
        return None
