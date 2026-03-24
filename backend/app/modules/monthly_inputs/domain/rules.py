"""
Règles métier pures du domaine monthly_inputs.

Aucune dépendance FastAPI, DB ou infrastructure. Utilisables par l'application si besoin.
Comportement actuel des routeurs inchangé (validation Pydantic côté API).
"""


def is_valid_period(year: int, month: int) -> bool:
    """Période (année, mois) valide pour une saisie mensuelle. Règle pure, sans I/O."""
    return isinstance(year, int) and isinstance(month, int) and 1 <= month <= 12 and year > 0
