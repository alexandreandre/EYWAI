"""Seed officiel IDCC 0292 — prime d'ancienneté plasturgie.

Source : accord du 28 juin 2011 relatif à la prime d'ancienneté (CCN plasturgie).
Barème par paliers sur le salaire de base (hors cadres).
"""

from __future__ import annotations

from app.modules.collective_agreements.rules.seeds import CCRulesSeed
from app.modules.collective_agreements.rules.schema import (
    BaseCalculPrime,
    CpAnciennete,
    CpAncienneteTier,
    PrimeAnciennete,
)

# Paliers officiels (% du salaire de base)
_BAREME_PLASTURGIE = [
    {"annees_min": 3, "taux": 0.024},
    {"annees_min": 6, "taux": 0.048},
    {"annees_min": 9, "taux": 0.072},
    {"annees_min": 12, "taux": 0.096},
    {"annees_min": 15, "taux": 0.12},
]


def _build_prime() -> PrimeAnciennete:
    return PrimeAnciennete(
        bareme=_BAREME_PLASTURGIE,
        base_de_calcul=BaseCalculPrime(
            methode="pourcentage_salaire_de_base",
            valeur=1.0,
        ),
    )


def _build_cp_anciennete() -> CpAnciennete:
    return CpAnciennete(
        mode="tier_total",
        seniority_reference="cp_period_end",
        tiers=[
            CpAncienneteTier(category="cadre", min_years=3, days=1),
            CpAncienneteTier(category="cadre", min_years=5, days=2),
            CpAncienneteTier(category="cadre", min_years=10, days=3),
            CpAncienneteTier(category="ouvrier_etam", min_years=5, days=1),
            CpAncienneteTier(category="ouvrier_etam", min_years=10, days=2),
        ],
    )


PLASTURGIE_0292_SEED = CCRulesSeed(
    grille=None,
    prime=_build_prime(),
    cp_anciennete=_build_cp_anciennete(),
)
