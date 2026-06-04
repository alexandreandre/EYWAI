"""Connecteur « manuel » — défaut absolu, aucun appel réseau.

C'est la garantie anti-régression : tant que la connexion API n'est pas branchée,
toute DSN reste à déposer manuellement sur net-entreprises.fr. Ce connecteur ne
lève jamais d'exception et n'effectue aucun I/O réseau.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.net_entreprises.domain.value_objects import (
    ConnectionTestResult,
    TransmissionMode,
    TransmissionResult,
    TransmissionStatus,
)

MANUAL_MESSAGE = "Ce fichier doit être télétransmis manuellement sur net-entreprises.fr"


class ManualNetEntreprisesConnector:
    """Connecteur no-op : dépôt manuel uniquement."""

    mode = TransmissionMode.MANUAL.value

    def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        return ConnectionTestResult(
            success=True,
            status="manual",
            message=(
                "Mode manuel actif : la DSN est générée puis déposée manuellement "
                "sur net-entreprises.fr. Aucune connexion API n'est requise."
            ),
        )

    def submit_dsn(
        self,
        config: Dict[str, Any],
        xml_content: bytes,
        metadata: Dict[str, Any],
    ) -> TransmissionResult:
        return TransmissionResult(
            status=TransmissionStatus.MANUAL.value,
            mode=self.mode,
            message=MANUAL_MESSAGE,
        )

    def get_status(
        self, config: Dict[str, Any], net_entreprises_ref: str
    ) -> Optional[TransmissionResult]:
        return None
