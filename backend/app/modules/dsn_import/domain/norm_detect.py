"""Détection de norme DSN (legacy vs courante NEODeS)."""

from __future__ import annotations

import re
from typing import List, Literal

from app.modules.dsn_import.domain.model import RubriqueLine

DsnFormat = Literal["modern", "legacy"]


def _clean(val: str) -> str:
    return val.replace(" ", "").replace("-", "").strip()


def _looks_like_nir(val: str) -> bool:
    c = _clean(val)
    return bool(c) and c.isdigit() and len(c) in (13, 15) and c[0] in ("1", "2")


def _looks_like_name(val: str) -> bool:
    if not val or val.isdigit():
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ]", val))


def detect_dsn_format(rubriques: List[RubriqueLine]) -> DsnFormat:
    """Infère la norme à partir des premières rubriques établissement / individu."""
    etab_val = ""
    ind001 = ""
    ind002 = ""

    for line in rubriques:
        if line.rubrique == "S21.G00.11.001" and not etab_val:
            etab_val = _clean(line.valeur)
        if line.rubrique == "S21.G00.30.001" and not ind001:
            ind001 = line.valeur.strip()
        if line.rubrique == "S21.G00.30.002" and not ind002:
            ind002 = line.valeur.strip()
        if etab_val and ind001 and ind002:
            break

    if etab_val:
        if len(etab_val) == 14 and etab_val.isdigit():
            return "legacy"
        if len(etab_val) <= 5:
            return "modern"

    if ind001 and ind002:
        if _looks_like_name(ind001) and not _looks_like_nir(ind001):
            return "legacy"
        if _looks_like_nir(ind001) or (_looks_like_name(ind002) and not _looks_like_nir(ind002)):
            return "modern"

    return "modern"
