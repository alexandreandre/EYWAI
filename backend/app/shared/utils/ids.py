"""
Utilitaires génériques pour les identifiants (UUID, etc.).

Sans logique métier ; wrappers évidents pour validation/parsing.
"""

from __future__ import annotations

import uuid


def is_valid_uuid(value: str) -> bool:
    """Retourne True si la chaîne est un UUID valide."""
    if not value or not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def parse_uuid(value: str) -> uuid.UUID | None:
    """Parse une chaîne en UUID ; retourne None si invalide."""
    if not value or not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None
