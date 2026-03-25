"""
Utilitaires IBAN (validation, masquage, normalisation).

Logique alignée sur services/exports/paiement_salaires (validation / masquage).
Utilisable par rib_alerts et tout module app/* sans dépendance legacy.
"""

from __future__ import annotations

import re


def normalize_iban(iban: str) -> str:
    """Normalise un IBAN pour comparaison (sans espaces, tirets, majuscules)."""
    if not iban or not isinstance(iban, str):
        return ""
    return iban.replace(" ", "").replace("-", "").upper().strip()


def validate_iban(iban: str) -> bool:
    """Valide le format d'un IBAN."""
    if not iban:
        return False
    iban_clean = iban.replace(" ", "").replace("-", "").upper()
    if len(iban_clean) < 15 or len(iban_clean) > 34:
        return False
    if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban_clean):
        return False
    return True


def mask_iban(iban: str) -> str:
    """Masque partiellement un IBAN pour l'affichage (4 premiers + 4 derniers)."""
    if not iban:
        return ""
    iban_clean = iban.replace(" ", "").replace("-", "").upper()
    if len(iban_clean) < 8:
        return iban_clean
    return f"{iban_clean[:4]} **** **** {iban_clean[-4:]}"
