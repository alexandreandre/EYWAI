"""Ports du domaine accounting_integration."""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable

from app.modules.accounting_integration.domain.value_objects import (
    ConnectionTestResult,
    TransmissionResult,
)


class AccountingIntegrationError(Exception):
    """Erreur générique côté connecteur comptable."""


@runtime_checkable
class AbstractAccountingConnector(Protocol):
    mode: str

    def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        ...

    def submit_files(
        self,
        config: Dict[str, Any],
        files: List[tuple[str, bytes]],
        metadata: Dict[str, Any],
    ) -> TransmissionResult:
        ...
