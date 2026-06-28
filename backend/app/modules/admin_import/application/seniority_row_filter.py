"""Filtre lignes Excel ancienneté — ignore notes / footers métier."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional

from app.modules.admin_import.application.rib_matching import (
    _is_reliable_payslip_identity,
    is_junk_employee_name,
)

# Motifs typiques des lignes de note paie (pas des commentaires salarié).
_INSTRUCTION_PATTERNS = (
    re.compile(r"prime.*anciennet|anciennet.*prime", re.IGNORECASE),
    re.compile(r"cadres?.*(prime|anciennet)|(prime|anciennet).*cadres?", re.IGNORECASE),
    re.compile(r"arr[eê]t.*(travail|maladie)|maladie.*arr[eê]t", re.IGNORECASE),
    re.compile(r"maintien.*salaire|151h|si et seulement", re.IGNORECASE),
    re.compile(r"pour les personnes|ne pas etre inferieur|ne pas modifier", re.IGNORECASE),
    re.compile(
        r"pour justifier.*prime|minimum de \d+ ans d.?anciennet",
        re.IGNORECASE,
    ),
)

_SENTENCE_START_RE = re.compile(
    r"^(les |la |le |pour |si |en |il |ne |on |des |du |de l|une |un )",
    re.IGNORECASE,
)


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def _is_instruction_phrase(text: str) -> bool:
    """True si le texte ressemble à une consigne Excel, pas à un nom ou commentaire salarié."""
    raw = (text or "").strip()
    if not raw:
        return False
    norm = _normalize_text(raw)
    if len(norm) > 90:
        return True
    if any(pattern.search(norm) for pattern in _INSTRUCTION_PATTERNS):
        return True
    if _SENTENCE_START_RE.match(norm) and len(norm.split()) >= 6:
        return True
    if norm.count(" ") >= 12:
        return True
    return False


def should_skip_seniority_row(
    *,
    first_name: str,
    last_name: str,
    full_name: str,
    identity: str,
    matricule: str,
    row: Optional[Dict[str, str]] = None,
) -> bool:
    """
    True si la ligne n'est pas un salarié (note Excel, footer, ligne vide partielle).

    Seuls les champs identité (nom / prénom) sont contrôlés — pas les colonnes
    Commentaire, montants, etc. qui peuvent contenir « ancienneté » légitimement.
    """
    del row  # conservé pour compatibilité appelant
    fn = (first_name or "").strip()
    ln = (last_name or "").strip()
    full = (full_name or "").strip()
    ident = (identity or "").strip()
    mat = (matricule or "").strip()

    combined_identity = " ".join(p for p in (fn, ln, full, ident) if p).strip()
    if not combined_identity and not mat:
        return True

    for candidate in (fn, ln, full, ident, combined_identity):
        if candidate and _is_instruction_phrase(candidate):
            return True

    if mat:
        return False

    if combined_identity and is_junk_employee_name(combined_identity):
        return True

    if not _is_reliable_payslip_identity(fn, ln, full or ident):
        return True

    return False
