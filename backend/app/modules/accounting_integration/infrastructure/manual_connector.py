"""Connecteur manuel : dépôt fichier = flux actuel (téléchargement)."""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.accounting_integration.domain.value_objects import (
    ConnectionTestResult,
    TransmissionMode,
    TransmissionResult,
)


class ManualAccountingConnector:
    mode = TransmissionMode.MANUAL.value

    def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        return ConnectionTestResult(
            success=True,
            status="manual",
            message="Mode manuel actif — les fichiers sont à transmettre manuellement.",
        )

    def submit_files(
        self,
        config: Dict[str, Any],
        files: List[tuple[str, bytes]],
        metadata: Dict[str, Any],
    ) -> TransmissionResult:
        return TransmissionResult(
            success=True,
            status="manual",
            message="Fichiers générés — transmission manuelle requise.",
        )
