"""
Dépendances HTTP du module copilot (types minimaux pour l’auth).

Permet au router de ne dépendre que de app.core.security, sans importer
le schéma User d’un autre module. Contrat minimal : objet avec id (str).
"""
from __future__ import annotations

from typing import Protocol


class AuthenticatedUser(Protocol):
    """Contrat minimal pour l’utilisateur authentifié (router copilot). Seul .id est utilisé."""

    id: str
