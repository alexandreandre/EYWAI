"""Helpers présentation salaire contractuel (> 35 h) et base prime d'ancienneté."""

from __future__ import annotations

import json
from typing import Any

from app.modules.payroll.engine import legal_constants as lc


def _parse_specificites_paie(contrat: dict[str, Any]) -> dict[str, Any]:
    spec = (contrat or {}).get("specificites_paie") or {}
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except json.JSONDecodeError:
            return {}
    return spec if isinstance(spec, dict) else {}


def salaire_hors_hs_structurelles(contrat: dict[str, Any]) -> bool:
    """
    True si le salaire mensuel stocké est la base 151,67 h hors HS structurelles
    (présentation bulletin type Cegid : base + HS struct en complément).
    """
    return bool(_parse_specificites_paie(contrat).get("salaire_hors_hs_structurelles"))


def heures_sup_structurelles_mensuelles(duree_hebdo: float) -> float:
    return round(
        ((duree_hebdo - lc.DUREE_LEGALE_HEBDO) * 52) / 12,
        2,
    ) if duree_hebdo > lc.DUREE_LEGALE_HEBDO else 0.0


def heures_mensuelles_legales() -> float:
    return round((lc.DUREE_LEGALE_HEBDO * 52) / 12, 2)


def taux_horaire_base_hors_hs_structurelles(salaire_mensuel: float) -> float:
    heures = heures_mensuelles_legales()
    return salaire_mensuel / heures if heures > 0 else 0.0


def salaire_contractuel_total_hors_hs_mode(
    salaire_mensuel: float,
    duree_hebdo: float,
    majoration_hs25: float,
) -> float:
    """Total contractuel affiché = base mensuelle + HS structurelles majorées."""
    if duree_hebdo <= lc.DUREE_LEGALE_HEBDO:
        return round(salaire_mensuel, 2)
    hs_m = heures_sup_structurelles_mensuelles(duree_hebdo)
    taux = taux_horaire_base_hors_hs_structurelles(salaire_mensuel)
    part_hs = round(hs_m * taux * (1 + majoration_hs25), 2)
    return round(salaire_mensuel + part_hs, 2)
