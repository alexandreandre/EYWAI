"""Fabrique de connecteurs comptables."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core import settings
from app.modules.accounting_integration.domain.interfaces import (
    AbstractAccountingConnector,
)
from app.modules.accounting_integration.domain.providers import (
    get_provider_definition,
    provider_key_from_mode,
)
from app.modules.accounting_integration.domain.value_objects import (
    TransmissionMode,
    is_api_mode,
)
from app.modules.accounting_integration.infrastructure.api_connector import (
    StubAccountingConnector,
)
from app.modules.accounting_integration.infrastructure.cegid_quadra_connector import (
    CegidQuadraConnector,
    has_complete_cegid_credentials,
)
from app.modules.accounting_integration.infrastructure.manual_connector import (
    ManualAccountingConnector,
)

_MANUAL = ManualAccountingConnector()


def _api_globally_enabled() -> bool:
    return bool(getattr(settings, "ACCOUNTING_API_ENABLED", False))


def resolve_connector(
    config: Optional[Dict[str, Any]],
    platform_row: Optional[Dict[str, Any]] = None,
    force_manual: bool = False,
) -> AbstractAccountingConnector:
    """Choisit le connecteur. Le manuel est toujours le repli."""
    if force_manual or not config or not config.get("enabled"):
        return _MANUAL

    provider_key = str(config.get("provider") or provider_key_from_mode(
        str(config.get("mode") or TransmissionMode.MANUAL.value)
    ))
    mode = str(config.get("mode") or TransmissionMode.MANUAL.value)

    if mode == TransmissionMode.MANUAL.value or provider_key == "manual":
        return _MANUAL

    definition = get_provider_definition(provider_key)
    if not definition:
        return _MANUAL

    if platform_row is not None and not platform_row.get("enabled"):
        return _MANUAL

    if definition.connector_class == "manual":
        return _MANUAL

    if definition.connector_class == "cegid_quadra":
        if _api_globally_enabled() and is_api_mode(mode):
            if has_complete_cegid_credentials(config or {}, platform_row):
                return CegidQuadraConnector(platform_row)
        return _MANUAL

    if definition.connector_class == "stub":
        if is_api_mode(mode):
            return StubAccountingConnector(mode=mode, provider_key=provider_key)
        return _MANUAL

    return _MANUAL
