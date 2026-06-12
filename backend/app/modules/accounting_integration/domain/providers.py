"""Registre des fournisseurs d'intégration comptable (source de vérité métier)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

AuthType = Literal["none", "api_key", "oauth2", "basic"]
Capability = Literal["manual", "api", "sftp"]


@dataclass(frozen=True)
class AccountingProviderDefinition:
    key: str
    name: str
    logo_key: str
    mode: str
    capabilities: tuple[Capability, ...]
    auth_type: AuthType
    supported_formats: tuple[str, ...]
    doc_url: str
    description: str
    connector_class: str  # manual | cegid_quadra | stub


PROVIDER_REGISTRY: Dict[str, AccountingProviderDefinition] = {
    "manual": AccountingProviderDefinition(
        key="manual",
        name="Manuel",
        logo_key="manual",
        mode="manual",
        capabilities=("manual",),
        auth_type="none",
        supported_formats=("csv", "xlsx", "fec"),
        doc_url="",
        description="Téléchargez les fichiers et importez-les dans votre logiciel comptable.",
        connector_class="manual",
    ),
    "cegid_quadra": AccountingProviderDefinition(
        key="cegid_quadra",
        name="Cegid / Quadra",
        logo_key="cegid",
        mode="api_quadra",
        capabilities=("manual", "api"),
        auth_type="api_key",
        supported_formats=("csv", "xlsx", "fec"),
        doc_url="https://www.cegid.com/fr/produits/quadra/",
        description="Transmission automatique des écritures FEC vers Cegid Loop (Quadra).",
        connector_class="cegid_quadra",
    ),
    "sage": AccountingProviderDefinition(
        key="sage",
        name="Sage",
        logo_key="sage",
        mode="api_sage",
        capabilities=("manual", "api"),
        auth_type="api_key",
        supported_formats=("csv", "xlsx", "fec"),
        doc_url="https://www.sage.com/fr-fr/",
        description="Connecteur Sage — bientôt disponible.",
        connector_class="stub",
    ),
    "pennylane": AccountingProviderDefinition(
        key="pennylane",
        name="Pennylane",
        logo_key="pennylane",
        mode="api_pennylane",
        capabilities=("manual", "api"),
        auth_type="api_key",
        supported_formats=("csv", "xlsx", "fec"),
        doc_url="https://www.pennylane.com/",
        description="Connecteur Pennylane — bientôt disponible.",
        connector_class="stub",
    ),
    "generic_sftp": AccountingProviderDefinition(
        key="generic_sftp",
        name="Dépôt SFTP",
        logo_key="generic",
        mode="sftp",
        capabilities=("manual", "sftp"),
        auth_type="basic",
        supported_formats=("csv", "xlsx", "fec"),
        doc_url="",
        description="Dépôt automatique sur serveur SFTP — bientôt disponible.",
        connector_class="stub",
    ),
}


def list_provider_definitions() -> List[AccountingProviderDefinition]:
    return list(PROVIDER_REGISTRY.values())


def get_provider_definition(key: str) -> Optional[AccountingProviderDefinition]:
    return PROVIDER_REGISTRY.get(key)


def provider_key_from_mode(mode: str) -> str:
    for p in PROVIDER_REGISTRY.values():
        if p.mode == mode:
            return p.key
    return "manual"


def mode_from_provider_key(key: str) -> str:
    p = PROVIDER_REGISTRY.get(key)
    return p.mode if p else "manual"
