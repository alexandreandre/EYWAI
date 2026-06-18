"""Ports (interfaces) du domaine net_entreprises.

Le connecteur abstrait permet de brancher différentes implémentations (manuel, API
certificat, API déclarant) sans modifier la couche application.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from app.modules.net_entreprises.domain.value_objects import (
    ConnectionTestResult,
    IjDecomptesFetchResult,
    TransmissionResult,
)


class NetEntreprisesError(Exception):
    """Erreur générique côté connecteur Net-entreprises."""


class NetEntreprisesNotConfigured(NetEntreprisesError):
    """La connexion API n'est pas configurée / pas encore branchée."""


@runtime_checkable
class AbstractNetEntreprisesConnector(Protocol):
    """Contrat d'un connecteur Net-entreprises.

    Toute implémentation DOIT être tolérante : ne jamais laisser remonter
    d'exception non maîtrisée vers l'appelant de production (le service encapsule
    déjà les appels, mais les connecteurs renvoient un résultat structuré).
    """

    mode: str

    def test_connection(self, config: Dict[str, Any]) -> ConnectionTestResult:
        """Teste la connexion avec la config fournie."""
        ...

    def submit_dsn(
        self,
        config: Dict[str, Any],
        xml_content: bytes,
        metadata: Dict[str, Any],
    ) -> TransmissionResult:
        """Dépose le fichier DSN et retourne le résultat de la transmission."""
        ...

    def get_status(
        self, config: Dict[str, Any], net_entreprises_ref: str
    ) -> Optional[TransmissionResult]:
        """Récupère le statut d'un dépôt précédent (accusé / CRM)."""
        ...

    def fetch_ij_decomptes(
        self,
        config: Dict[str, Any],
        *,
        period: str,
        siret: str,
    ) -> IjDecomptesFetchResult:
        """Récupère les décomptes IJSS CPAM pour une période."""
        ...
