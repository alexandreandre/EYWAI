"""
Exceptions du domaine schedules (sans dépendance FastAPI).

Utilisées par l'infrastructure ; l'application les convertit en ScheduleAppError si besoin.
"""


class ScheduleNotFoundError(Exception):
    """Ressource introuvable (employé, entreprise, etc.)."""

    pass


class ScheduleValidationError(Exception):
    """Données invalides (mois, année, durée hebdo, etc.)."""

    pass


class ScheduleDatabaseError(Exception):
    """Erreur de connexion ou d'accès à la base."""

    pass
