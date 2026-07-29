"""Erreurs métier de la resynchro de l'environnement de test."""

from __future__ import annotations


class TestEnvRefreshError(Exception):
    """Base des erreurs de resynchro."""


class RefreshNotConfigured(TestEnvRefreshError):
    """Le service n'a pas de quoi déclencher le workflow (jeton ou dépôt absent)."""


class RefreshDispatchRefused(TestEnvRefreshError):
    """GitHub a refusé le déclenchement du workflow."""
