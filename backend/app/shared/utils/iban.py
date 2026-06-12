"""
Utilitaires IBAN (validation, masquage, normalisation).

Logique alignée sur services/exports/paiement_salaires (validation / masquage).
Utilisable par rib_alerts et tout module app/* sans dépendance legacy.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict


def normalize_iban(iban: str) -> str:
    """Normalise un IBAN pour comparaison (sans espaces, tirets, majuscules)."""
    if not iban or not isinstance(iban, str):
        return ""
    return iban.replace(" ", "").replace("-", "").upper().strip()


def validate_iban(iban: str) -> bool:
    """Valide le format d'un IBAN."""
    iban_clean = normalize_iban(iban)
    if not iban_clean:
        return False
    if len(iban_clean) < 15 or len(iban_clean) > 34:
        return False
    if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban_clean):
        return False
    return True


def parse_coordonnees_bancaires(raw: Any) -> Dict[str, Any]:
    """Parse coordonnees_bancaires depuis la DB (dict, chaîne JSON ou null)."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def extract_iban(raw_coords: Any) -> str:
    """Extrait et normalise l'IBAN depuis coordonnees_bancaires."""
    coords = parse_coordonnees_bancaires(raw_coords)
    for key in ("iban", "IBAN"):
        value = coords.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_iban(value)
    return ""


def extract_bic(raw_coords: Any) -> str:
    """Extrait et normalise le BIC depuis coordonnees_bancaires."""
    coords = parse_coordonnees_bancaires(raw_coords)
    for key in ("bic", "BIC"):
        value = coords.get(key)
        if isinstance(value, str) and value.strip():
            return value.replace(" ", "").replace("-", "").upper().strip()
    return ""


def has_valid_iban(raw_coords: Any) -> bool:
    """True si coordonnees_bancaires contient un IBAN au format export banque."""
    return validate_iban(extract_iban(raw_coords))


def mask_iban(iban: str) -> str:
    """Masque partiellement un IBAN pour l'affichage (4 premiers + 4 derniers)."""
    if not iban:
        return ""
    iban_clean = iban.replace(" ", "").replace("-", "").upper()
    if len(iban_clean) < 8:
        return iban_clean
    return f"{iban_clean[:4]} **** **** {iban_clean[-4:]}"
