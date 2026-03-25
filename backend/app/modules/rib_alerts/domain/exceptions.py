"""
Exceptions du domaine rib_alerts (sans dépendance FastAPI).

Utilisées par les règles métier ; l’API/application les convertit en HTTP (ex. 403, 404).
"""

from __future__ import annotations


class RibAlertDomainError(Exception):
    """Erreur métier générique rib_alerts."""

    pass


class MissingCompanyContextError(RibAlertDomainError):
    """Contexte entreprise absent (company_id requis pour toute opération)."""

    pass


class RibAlertNotFoundError(RibAlertDomainError):
    """Alerte introuvable ou n’appartient pas à l’entreprise du contexte."""

    pass
