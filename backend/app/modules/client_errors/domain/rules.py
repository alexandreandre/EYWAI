"""Assainit un signalement d'erreur d'écran : pas de donnée personnelle, pile courte."""

from __future__ import annotations

import re
from typing import Any, Mapping

MAX_MESSAGE = 300
MAX_PILE = 2000
MAX_LIGNES_PILE = 20
CLES = ("ecran", "action", "message", "pile")

_IBAN = re.compile(r"\bFR\d{2}[\s\d]{10,}\b", re.I)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_NIR = re.compile(r"\b[12]\s?\d{2}[\s\d]{10,}\b")
_PDF = re.compile(r"\b[\w.-]+\.pdf\b", re.I)
_NOM = re.compile(
    r"\b[A-ZÉÈÊÀ][a-zàâäéèêëïîôùûüç]+(?:[-\s][A-ZÉÈÊÀ][a-zàâäéèêëïîôùûüç]+)+\b"
)
# « Prénom NOM » et « NOM Prénom », comme sur un bulletin.
_PRENOM = r"[A-ZÉÈÊÀ][a-zàâäéèêëïîôùûüç]+(?:-[A-ZÉÈÊÀ][a-zàâäéèêëïîôùûüç]+)?"
_MAJUSCULES = r"[A-ZÉÈÊÀÂÎÔÛÇ]{2,}(?:[-\s][A-ZÉÈÊÀÂÎÔÛÇ]{2,})*"
_NOM_MAJUSCULES = re.compile(rf"\b(?:{_PRENOM}\s+{_MAJUSCULES}|{_MAJUSCULES}\s+{_PRENOM})\b")
# Un mot à majuscule collé à un nom déjà masqué en fait partie (« Jeanne [nom] »).
_VOISIN_DE_NOM = re.compile(
    rf"\b(?:{_PRENOM}|{_MAJUSCULES})\s+\[nom\]|\[nom\]\s+(?:{_PRENOM}|{_MAJUSCULES})\b"
)
# Montant : décimales à la virgule ou au point, milliers espacés, euro facultatif.
_MONTANT = re.compile(
    r"\b(?:\d{1,3}(?:[\s ]\d{3})+|\d+)[.,]\d{1,2}\b(?:\s?€)?|\b\d+\s?€"
)


def _sans_pii(texte: str) -> str:
    t = _IBAN.sub("[iban]", texte)
    t = _EMAIL.sub("[email]", t)
    t = _NIR.sub("[nir]", t)
    t = _PDF.sub("[fichier]", t)
    t = _NOM_MAJUSCULES.sub("[nom]", t)
    t = _NOM.sub("[nom]", t)
    precedent = None
    while precedent != t:
        precedent, t = t, _VOISIN_DE_NOM.sub("[nom]", t)
    t = _MONTANT.sub("[montant]", t)
    return t


def assainir_journal(brut: Mapping[str, Any] | None) -> dict[str, str]:
    """Ne retient que écran / action / message / pile, sans PII, pile tronquée."""
    src = brut or {}
    pile = str(src.get("pile") or "")
    lignes = pile.splitlines()[:MAX_LIGNES_PILE]
    pile_courte = "\n".join(lignes)[:MAX_PILE]
    return {
        "ecran": _sans_pii(str(src.get("ecran") or ""))[:80],
        "action": _sans_pii(str(src.get("action") or ""))[:80],
        "message": _sans_pii(str(src.get("message") or ""))[:MAX_MESSAGE],
        "pile": _sans_pii(pile_courte),
    }
