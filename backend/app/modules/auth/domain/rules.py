# Règles métier pures du module auth.
# Aucune dépendance à FastAPI ni à la base de données.

# Durée de validité du token de réinitialisation (heures)
RESET_TOKEN_VALIDITY_HOURS = 1


def is_email_like(s: str) -> bool:
    """True si la chaîne ressemble à un email (contient @). Règle pure, pas d’IO."""
    return "@" in s
