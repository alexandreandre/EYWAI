"""Connecteur stub pour fournisseurs non encore branchés."""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.accounting_integration.domain.value_objects import (
    ConnectionTestResult,
    TransmissionResult,
)


class StubAccountingConnector:
    """Stub générique : signale l'indisponibilité et bascule en manuel."""

    def __init__(self, mode: str, provider_key: str = "") -> None:
        self.mode = mode
        self.provider_key = provider_key

    def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        if not config.get("enabled"):
            return ConnectionTestResult(
                success=False,
                status="not_configured",
                message="Intégration API non activée pour cette entreprise.",
            )
        return ConnectionTestResult(
            success=False,
            status="stub",
            message=(
                f"Connecteur {self.provider_key or self.mode} en préparation — "
                "utilisez le mode manuel en attendant."
            ),
        )

    def submit_files(
        self,
        config: Dict[str, Any],
        files: List[tuple[str, bytes]],
        metadata: Dict[str, Any],
    ) -> TransmissionResult:
        return TransmissionResult(
            success=False,
            status="manual",
            message=(
                f"Transmission API ({self.provider_key or self.mode}) non disponible — "
                "repli sur téléchargement manuel."
            ),
        )
