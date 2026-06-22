"""Extraction IBAN/BIC depuis une cellule RIB."""

from __future__ import annotations

import re
from typing import Dict, Tuple

from app.shared.utils.iban import normalize_iban, validate_iban

_IBAN_RE = re.compile(r"\b([A-Z]{2}[0-9]{2}[A-Z0-9]{11,30})\b", re.IGNORECASE)
_BIC_RE = re.compile(r"\b([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b", re.IGNORECASE)


def parse_rib_cell(value: str, *, bic_hint: str = "") -> Tuple[str, str, bool, str]:
    """
    Extrait IBAN et BIC d'une cellule RIB.

    Returns:
        (iban, bic, iban_valid, error_message)
    """
    raw = (value or "").strip()
    if not raw:
        return "", "", False, "RIB vide"

    compact = re.sub(r"\s+", "", raw.upper())
    iban = ""
    bic = (bic_hint or "").strip().upper()

    match = _IBAN_RE.search(compact)
    if match:
        iban = normalize_iban(match.group(1))
    elif re.match(r"^[A-Z]{2}[0-9]{2}", compact) and len(compact) >= 15:
        iban = normalize_iban(compact)

    if not bic:
        bic_match = _BIC_RE.search(compact)
        if bic_match:
            bic = bic_match.group(1).upper()

    if not iban:
        digits_only = re.sub(r"\D", "", raw)
        if len(digits_only) == 23:
            return "", bic, False, "Format RIB français détecté — saisir l'IBAN ou coller le RIB complet avec IBAN"

    if not iban:
        return "", bic, False, "IBAN introuvable dans la cellule RIB"

    if not validate_iban(iban):
        return iban, bic, False, "IBAN invalide (format ou longueur incorrecte)"

    return iban, bic, True, ""


def build_coordonnees_bancaires(iban: str, bic: str = "") -> Dict[str, str]:
    payload: Dict[str, str] = {"iban": normalize_iban(iban)}
    if bic:
        payload["bic"] = bic.replace(" ", "").upper()
    return payload
