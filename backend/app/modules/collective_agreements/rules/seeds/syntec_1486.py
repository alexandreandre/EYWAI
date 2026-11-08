"""Seed officiel IDCC 1486 (Syntec) : grille des minima, sans prime d'ancienneté.

Source : accord du 26 juin 2024 relatif aux salaires minima, étendu, en vigueur
au 1er janvier 2025 (montants mensuels bruts, base 35 h). La branche n'a pas de
prime d'ancienneté : la grille est donc écrite dans `convention_collective_rules`,
`_enrich_cc_rules_with_seed` ignorant les graines sans prime.

Les coefficients ETAM (240 à 500) et IC (95 à 270) ne se recoupent pas.
"""

from __future__ import annotations

from app.modules.collective_agreements.rules.schema import GrilleSalaires, SalaireMinimum
from app.modules.collective_agreements.rules.seeds import CCRulesSeed

_GRILLE: list[tuple[str, str, int, float]] = [
    ("ETAM", "1.1", 240, 1815.0),
    ("ETAM", "1.2", 250, 1845.0),
    ("ETAM", "2.1", 275, 1875.0),
    ("ETAM", "2.2", 310, 1905.0),
    ("ETAM", "2.3", 355, 2045.0),
    ("ETAM", "3.1", 400, 2185.0),
    ("ETAM", "3.2", 450, 2340.0),
    ("ETAM", "3.3", 500, 2490.0),
    ("IC", "1.1", 95, 2135.0),
    ("IC", "1.2", 100, 2240.0),
    ("IC", "2.1", 105, 2315.0),
    ("IC", "2.1", 115, 2530.0),
    ("IC", "2.2", 130, 2850.0),
    ("IC", "2.3", 150, 3275.0),
    ("IC", "3.1", 170, 3650.0),
    ("IC", "3.2", 210, 4495.0),
    ("IC", "3.3", 270, 5755.0),
]

SYNTEC_1486_SEED = CCRulesSeed(
    grille=GrilleSalaires(
        zone_type="national",
        zone_libelle="National",
        date_effet="2025-01-01",
        source_titre="Accord du 26 juin 2024 relatif aux salaires minima (Syntec)",
        minima=[
            SalaireMinimum(
                coefficient=float(coefficient),
                valeur=valeur,
                libelle=f"{categorie} position {position}",
            )
            for categorie, position, coefficient, valeur in _GRILLE
        ],
    )
)
