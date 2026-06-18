from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

AccountingMode = Literal[
    "manual", "api_quadra", "api_sage", "api_pennylane", "sftp"
]
ConnectionState = Literal["not_configured", "manual", "connected", "stub", "failed"]
CegidAuthMode = Literal["shared", "dedicated"]
CegidAuthSource = Literal["shared", "dedicated", "incomplete"]
TransmissionStatusType = Literal[
    "generated", "queued", "sent", "transmitted", "acknowledged", "rejected", "manual", "failed"
]


class AccountingConfigResponse(BaseModel):
    enabled: bool = False
    mode: AccountingMode = "manual"
    provider: str = "manual"
    default_format: str = "csv"
    recipients_compta: List[str] = Field(default_factory=list)
    has_credentials: bool = False
    cegid_credentials_complete: bool = False
    has_platform_cegid_credentials: bool = False
    code_dossier_cegid: Optional[str] = None
    cegid_auth_mode: CegidAuthMode = "shared"
    cegid_auth_source: CegidAuthSource = "incomplete"
    force_manual: bool = False
    last_transmission_at: Optional[str] = None
    last_test_at: Optional[str] = None
    last_test_status: Optional[str] = None
    last_test_message: Optional[str] = None
    connection_state: ConnectionState = "not_configured"


class AccountingConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    mode: Optional[AccountingMode] = None
    provider: Optional[str] = None
    default_format: Optional[str] = None
    recipients_compta: Optional[List[str]] = None
    credentials: Optional[Dict[str, Any]] = None
    code_dossier_cegid: Optional[str] = None
    cegid_auth_mode: Optional[CegidAuthMode] = None
    clear_company_credentials: Optional[bool] = None
    force_manual: Optional[bool] = None


class BulkCegidDossierEntry(BaseModel):
    company_id: str
    code_dossier_cegid: str
    enabled: bool = True
    cegid_auth_mode: CegidAuthMode = "shared"


class BulkCegidDossiersUpdate(BaseModel):
    entries: List[BulkCegidDossierEntry]


class BulkCegidDossiersResponse(BaseModel):
    updated: int
    failed: List[str] = Field(default_factory=list)


class ConnectionTestResponse(BaseModel):
    success: bool
    status: str
    message: str


class ProviderDefinitionResponse(BaseModel):
    key: str
    name: str
    logo_key: str
    mode: str
    capabilities: List[str]
    auth_type: str
    supported_formats: List[str]
    doc_url: str
    description: str
    platform_enabled: bool = False
    connector_ready: bool = False


class ProvidersListResponse(BaseModel):
    providers: List[ProviderDefinitionResponse]


class AccountingTransmissionEntry(BaseModel):
    id: str
    company_id: str
    company_name: Optional[str] = None
    period: str
    channel: str
    provider: str
    mode: str
    status: TransmissionStatusType
    export_ids: List[str] = Field(default_factory=list)
    external_ref: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None


class AccountingTransmissionsResponse(BaseModel):
    transmissions: List[AccountingTransmissionEntry]
    total: int
    counts_by_status: Dict[str, int] = Field(default_factory=dict)


class PlatformProviderEntry(BaseModel):
    provider_key: str
    name: str
    logo_key: str
    enabled: bool
    has_platform_credentials: bool = False
    has_platform_cegid_credentials: bool = False
    settings: Dict[str, Any] = Field(default_factory=dict)
    last_test_at: Optional[str] = None
    last_test_status: Optional[str] = None
    last_test_message: Optional[str] = None
    description: str = ""
    connector_ready: bool = False


class PlatformCatalogResponse(BaseModel):
    providers: List[PlatformProviderEntry]
    stats: Dict[str, int] = Field(default_factory=dict)


class PlatformProviderUpdate(BaseModel):
    enabled: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None
    platform_credentials: Optional[Dict[str, Any]] = None


class TransmitComptaResult(BaseModel):
    success: bool
    status: str
    message: str
    transmission_id: Optional[str] = None
    external_ref: Optional[str] = None
    manual_fallback: bool = False
