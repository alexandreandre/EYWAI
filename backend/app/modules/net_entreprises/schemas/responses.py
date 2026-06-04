"""Schémas de réponse net_entreprises (jamais de secret en clair)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NetEntreprisesConfigResponse(BaseModel):
    """Config de connexion exposée au frontend (sans secret)."""

    enabled: bool = False
    mode: str = "manual"
    siret_declarant: Optional[str] = None
    raison_sociale_declarant: Optional[str] = None
    identifiant: Optional[str] = None
    contact_email: Optional[str] = None
    certificat_label: Optional[str] = None
    certificat_expires_at: Optional[str] = None
    has_secret: bool = False
    last_test_at: Optional[datetime] = None
    last_test_status: Optional[str] = None
    last_test_message: Optional[str] = None
    # État synthétique pour l'UI : 'not_configured' | 'manual' | 'connected'
    connection_state: str = "not_configured"


class ConnectionTestResponse(BaseModel):
    """Résultat d'un test de connexion."""

    success: bool
    status: str
    message: str


class DSNTransmissionEntry(BaseModel):
    """Une transmission DSN (vue entreprise)."""

    id: str
    period: str
    dsn_type: str = "dsn_mensuelle_normale"
    status: str
    mode: str
    net_entreprises_ref: Optional[str] = None
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    error_message: Optional[str] = None
    crm_retour: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class DSNTransmissionsResponse(BaseModel):
    """Liste des transmissions d'une entreprise."""

    transmissions: List[DSNTransmissionEntry] = Field(default_factory=list)


class AdminDSNTransmissionEntry(DSNTransmissionEntry):
    """Transmission enrichie pour le suivi plateforme."""

    company_id: str
    company_name: Optional[str] = None


class AdminDSNTransmissionsResponse(BaseModel):
    """Suivi plateforme : transmissions toutes entreprises + compteurs par statut."""

    transmissions: List[AdminDSNTransmissionEntry] = Field(default_factory=list)
    counts_by_status: Dict[str, int] = Field(default_factory=dict)
