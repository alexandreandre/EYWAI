"""Normalisation des classifications conventionnelles issues de la DSN."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from app.modules.collective_agreements.rules.constants import SMH_NATIONAL_IDCC

# Niveau DSN métallurgie (S21.G00.40.041) : "<classe 1-18> <groupe A-I>"
# ex. "2 A", "11 F", ou classe seule "7". Un coefficient de position (3 chiffres,
# ex. "710") ne doit PAS être interprété comme une classe.
_METALLURGIE_NIVEAU_RE = re.compile(r"^\s*(\d{1,2})(?:\s+([A-Ia-i]))?\s*$")


def _is_plasturgie(idcc: Any) -> bool:
    value = str(idcc or "").strip()
    return value.zfill(4) == "0292"


def _is_smh_national(idcc: Any) -> bool:
    value = str(idcc or "").strip()
    if not value:
        return False
    if value in SMH_NATIONAL_IDCC:
        return True
    stripped = value.lstrip("0") or "0"
    return stripped in {x.lstrip("0") for x in SMH_NATIONAL_IDCC}


def _normalize_metallurgie(classification: dict[str, Any]) -> dict[str, Any]:
    """Expose la classe d'emploi (1-18) à partir du niveau DSN "classe groupe".

    La grille SMH métallurgie est indexée par classe d'emploi, pas par le
    coefficient de position. Sans `classe_emploi`, le contrôle du minimum
    conventionnel ne peut pas résoudre la ligne de grille.
    """
    match = _METALLURGIE_NIVEAU_RE.match(str(classification.get("niveau_dsn") or ""))
    if not match:
        return classification
    classe = int(match.group(1))
    if not 1 <= classe <= 18:
        return classification
    classification.setdefault("classe_emploi", classe)
    classification.setdefault("classe", classe)
    groupe = (match.group(2) or "").upper()
    if groupe:
        classification.setdefault("groupe", groupe)
    return classification


def normalize_classification_for_payroll(value: Any) -> dict[str, Any]:
    """Enrichit la classification DSN pour le contrôle des minima conventionnels.

    - Plasturgie (0292) : le niveau DSN numérique EST le coefficient officiel.
    - Métallurgie (SMH national, 3248) : le niveau DSN "classe groupe" fournit la
      classe d'emploi (1-18) indexant la grille SMH.
    """
    if not isinstance(value, dict):
        return {}
    classification = deepcopy(value)

    if _is_smh_national(classification.get("idcc")):
        return _normalize_metallurgie(classification)

    if not _is_plasturgie(classification.get("idcc")):
        return classification

    niveau_dsn = classification.get("niveau_dsn")
    try:
        coefficient = float(niveau_dsn)
    except (TypeError, ValueError):
        return classification
    if coefficient <= 0:
        return classification

    classification["coefficient"] = (
        int(coefficient) if coefficient.is_integer() else coefficient
    )
    return classification


__all__ = ["normalize_classification_for_payroll"]
