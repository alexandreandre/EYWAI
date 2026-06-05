"""Exceptions métier CSE — sans dépendance FastAPI."""

from __future__ import annotations


class CseDelegationError(Exception):
    """Erreur liée à la délégation CSE."""


class DelegationNotFoundError(CseDelegationError):
    """Ressource de délégation introuvable."""


class DelegationValidationError(CseDelegationError):
    """Données ou règle de délégation invalides."""
