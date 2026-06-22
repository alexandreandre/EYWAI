"""Extraction IBAN/BIC depuis une cellule RIB (IBAN ou RIB français 23 car.)."""

from __future__ import annotations

import re
from typing import Dict, Tuple

from app.shared.utils.iban import normalize_iban, validate_iban

_BIC_RE = re.compile(r"\b([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b", re.IGNORECASE)
_FRENCH_RIB_RE = re.compile(r"^[A-Z0-9]{23}$")


def _iban_check_digits(bban: str, country_code: str = "FR") -> str:
    """Clé IBAN ISO 13616 : BBAN + code pays + « 00 » placeholder."""
    rearranged = bban + country_code.upper() + "00"
    expanded = ""
    for ch in rearranged:
        if ch.isdigit():
            expanded += ch
        else:
            expanded += str(ord(ch) - 55)
    remainder = 0
    for ch in expanded:
        remainder = (remainder * 10 + int(ch)) % 97
    return str(98 - remainder).zfill(2)


def _iban_mod97(iban: str) -> int:
    rearranged = iban[4:] + iban[:4]
    expanded = ""
    for ch in rearranged:
        if ch.isdigit():
            expanded += ch
        else:
            expanded += str(ord(ch) - 55)
    remainder = 0
    for ch in expanded:
        remainder = (remainder * 10 + int(ch)) % 97
    return remainder


def normalize_french_rib(raw: str) -> str:
    """Normalise un RIB français (23 car. alphanumériques)."""
    compact = re.sub(r"\s", "", (raw or "").upper())
    alnum = re.sub(r"[^A-Z0-9]", "", compact)
    if len(alnum) == 23 and _FRENCH_RIB_RE.match(alnum):
        return alnum
    digits = re.sub(r"\D", "", compact)
    if len(digits) == 23:
        return digits
    return ""


def french_rib_to_iban(rib: str) -> str:
    """Convertit un RIB français (23 car.) en IBAN FR."""
    bban = normalize_french_rib(rib)
    if not bban:
        return ""
    check = _iban_check_digits(bban, "FR")
    iban = normalize_iban(f"FR{check}{bban}")
    return iban if validate_iban(iban) and _iban_mod97(iban) == 1 else ""


def _extract_iban(compact: str) -> str:
    best = ""
    for match in re.finditer(r"[A-Z]{2}[0-9]{2}", compact):
        for size in range(34, 14, -1):
            end = match.start() + size
            if end > len(compact):
                continue
            candidate = normalize_iban(compact[match.start() : end])
            if not validate_iban(candidate):
                continue
            country = candidate[:2]
            expected = 27 if country == "FR" else None
            if expected and len(candidate) != expected:
                continue
            if len(candidate) > len(best):
                best = candidate
    return best


def _extract_bic(compact: str, *, after_iban: str = "") -> str:
    search_space = compact
    if after_iban:
        idx = compact.find(after_iban)
        if idx >= 0:
            search_space = compact[idx + len(after_iban) :]
    bic_match = _BIC_RE.search(search_space)
    return bic_match.group(1).upper() if bic_match else ""


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
    iban_part = compact
    bic_part = ""
    if "BIC" in compact:
        chunks = compact.split("BIC", 1)
        iban_part = chunks[0]
        bic_part = chunks[1] if len(chunks) > 1 else ""

    iban = _extract_iban(iban_part)
    bic = (bic_hint or "").strip().upper()

    if not bic and bic_part:
        bic = _extract_bic(bic_part)
    if not bic:
        bic = _extract_bic(compact, after_iban=iban)

    if not iban:
        iban = french_rib_to_iban(raw)

    if not iban:
        return "", bic, False, "RIB/IBAN introuvable ou invalide dans la cellule"

    if not validate_iban(iban):
        return iban, bic, False, "IBAN invalide (format ou longueur incorrecte)"

    return iban, bic, True, ""


def build_coordonnees_bancaires(iban: str, bic: str = "") -> Dict[str, str]:
    payload: Dict[str, str] = {"iban": normalize_iban(iban)}
    if bic:
        payload["bic"] = bic.replace(" ", "").upper()
    return payload
