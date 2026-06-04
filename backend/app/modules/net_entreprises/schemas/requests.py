"""Schémas de requête net_entreprises."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class NetEntreprisesConfigUpdate(BaseModel):
    """Body pour PUT /api/net-entreprises/config.

    Le secret éventuel (`secret` en clair) n'est jamais renvoyé : le backend le
    stocke et renvoie uniquement un indicateur `has_secret`.
    """

    enabled: Optional[bool] = None
    mode: Optional[str] = Field(
        None,
        description="manual | api_certificat | api_declarant",
    )
    siret_declarant: Optional[str] = None
    raison_sociale_declarant: Optional[str] = None
    identifiant: Optional[str] = None
    contact_email: Optional[str] = None
    certificat_label: Optional[str] = None
    certificat_expires_at: Optional[str] = Field(
        None, description="Date d'échéance du certificat (YYYY-MM-DD)"
    )
    # Secret en clair (mot de passe / clé) — écrit côté serveur, jamais relu.
    secret: Optional[str] = None

    model_config = {"extra": "ignore"}


class MarkTransmittedRequest(BaseModel):
    """Body pour marquer une transmission comme déposée manuellement."""

    net_entreprises_ref: Optional[str] = Field(
        None, description="Numéro de dépôt / accusé Net-entreprises (optionnel)"
    )
