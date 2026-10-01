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


def _sans_pii(texte: str) -> str:
    t = _IBAN.sub("[iban]", texte)
    t = _EMAIL.sub("[email]", t)
    t = _NIR.sub("[nir]", t)
    t = _PDF.sub("[fichier]", t)
    t = _NOM.sub("[nom]", t)
    return t


def assainir_journal(brut: Mapping[str, Any] | None) -> dict[str, str]:
    """Ne retient que écran / action / message / pile, sans PII, pile tronquée."""
    src = brut or {}
    pile = str(src.get("pile") or "")
    lignes = pile.splitlines()[:MAX_LIGNES_PILE]
    pile_courte = "\n".join(lignes)[:MAX_PILE]
    return {
        "ecran": str(src.get("ecran") or "")[:80],
        "action": str(src.get("action") or "")[:80],
        "message": _sans_pii(str(src.get("message") or ""))[:MAX_MESSAGE],
        "pile": _sans_pii(pile_courte),
    }
