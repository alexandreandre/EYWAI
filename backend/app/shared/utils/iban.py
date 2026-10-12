"""
Utilitaires IBAN (validation, masquage, normalisation).

Logique alignée sur services/exports/paiement_salaires (validation / masquage).
Utilisable par rib_alerts et tout module app/* sans dépendance legacy.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


def normalize_iban(iban: str) -> str:
    """Normalise un IBAN pour comparaison (sans espaces, tirets, majuscules)."""
    if not iban or not isinstance(iban, str):
        return ""
    return iban.replace(" ", "").replace("-", "").upper().strip()


# Longueur de l'IBAN par pays (registre ISO 13616). Pays absent : seules la plage
# 15 à 34 caractères et la clé sont contrôlées.
IBAN_LONGUEURS_PAR_PAYS: Dict[str, int] = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16,
    "BG": 22, "BH": 22, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28,
    "CZ": 24, "DE": 22, "DK": 18, "DO": 28, "EE": 20, "EG": 29, "ES": 24,
    "FI": 18, "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18,
    "GR": 27, "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23,
    "IS": 26, "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "LY": 25, "MC": 27, "MD": 24,
    "ME": 22, "MK": 19, "MR": 27, "MT": 31, "MU": 30, "NL": 18, "NO": 15,
    "PK": 24, "PL": 28, "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22,
    "SA": 24, "SC": 31, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "ST": 25,
    "SV": 28, "TL": 23, "TN": 24, "TR": 26, "UA": 29, "VA": 22, "VG": 24,
    "XK": 20,
}


def iban_mod97(iban_clean: str) -> int:
    """Reste mod 97 de l'IBAN normalisé (1 si la clé est juste)."""
    rearranged = iban_clean[4:] + iban_clean[:4]
    return int("".join(str(int(ch, 36)) for ch in rearranged)) % 97


def iban_problem(iban: str) -> Optional[str]:
    """Raison pour laquelle l'IBAN est refusé, en français ; None s'il est bon."""
    iban_clean = normalize_iban(iban)
    if not iban_clean:
        return "IBAN vide."
    if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban_clean):
        return "IBAN invalide : deux lettres de pays, deux chiffres de clé, puis le numéro de compte."
    attendue = IBAN_LONGUEURS_PAR_PAYS.get(iban_clean[:2])
    if attendue is not None and len(iban_clean) != attendue:
        return (
            f"IBAN {iban_clean[:2]} de longueur incorrecte : "
            f"{attendue} caractères attendus, {len(iban_clean)} saisis."
        )
    if attendue is None and not 15 <= len(iban_clean) <= 34:
        return "IBAN de longueur incorrecte : entre 15 et 34 caractères."
    if iban_mod97(iban_clean) != 1:
        return "Clé de contrôle de l'IBAN incorrecte : vérifiez la saisie."
    return None


def validate_iban(iban: str) -> bool:
    """Valide l'IBAN : format, longueur du pays et clé de contrôle (mod 97)."""
    return iban_problem(iban) is None


def iban_bien_forme(iban: str) -> bool:
    """Un IBAN est renseigné et bien formé : pays, clé, 15 à 34 caractères.

    Ni la clé (mod 97) ni la longueur propre au pays : un IBAN faux mais bien
    formé n'empêche pas de calculer la paie, seulement de faire le virement
    (`validate_iban`, à l'aperçu du virement).
    """
    iban_clean = normalize_iban(iban)
    return bool(
        15 <= len(iban_clean) <= 34 and re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban_clean)
    )


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
