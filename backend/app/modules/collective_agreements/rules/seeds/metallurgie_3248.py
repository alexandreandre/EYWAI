"""Seed officiel IDCC 3248 — barème SMH national + prime d'ancienneté métallurgie.

Source : CCN métallurgie du 7 février 2022, annexe barème SMH (revalorisation 2025).
Les montants annuels sont convertis en mensuels (÷ 12) pour le moteur de paie.
"""

from __future__ import annotations

from app.modules.collective_agreements.rules.seeds import CCRulesSeed
from app.modules.collective_agreements.rules.schema import (
    BaseCalculPrime,
    CpAnciennete,
    CpAncienneteTier,
    GrilleSalaires,
    PrimeAnciennete,
    PrimeAncienneteEligibilite,
    PrimeAncienneteProrata,
    SalaireMinimum,
    ValeurPointZone,
)

# Barème SMH 2025 — salaire annuel brut 35h (source annexe officielle étendue)
_SMH_ANNUEL_2025: list[tuple[str, int, float]] = [
    ("A", 1, 21_700.0),
    ("A", 2, 21_850.0),
    ("B", 3, 22_450.0),
    ("B", 4, 23_400.0),
    ("C", 5, 24_250.0),
    ("C", 6, 25_550.0),
    ("D", 7, 26_400.0),
    ("D", 8, 28_450.0),
    ("E", 9, 30_500.0),
    ("E", 10, 33_700.0),
    ("F", 11, 34_900.0),
    ("F", 12, 36_700.0),
    ("G", 13, 40_000.0),
    ("G", 14, 43_900.0),
    ("H", 15, 47_000.0),
    ("H", 16, 52_000.0),
    ("I", 17, 59_300.0),
    ("I", 18, 68_000.0),
]

# Taux base spécifique prime d'ancienneté par classe d'emploi (1→10), art. 142
_TAUX_PRIME_PAR_CLASSE: dict[str, float] = {
    "1": 0.0145,
    "2": 0.016,
    "3": 0.0175,
    "4": 0.0195,
    "5": 0.022,
    "6": 0.0245,
    "7": 0.026,
    "8": 0.029,
    "9": 0.033,
    "10": 0.038,
}


def _build_smh_grille() -> GrilleSalaires:
    minima = [
        SalaireMinimum(
            coefficient=float(classe),
            valeur=round(annuel / 12, 2),
            libelle=f"Groupe {groupe} — Classe {classe}",
        )
        for groupe, classe, annuel in _SMH_ANNUEL_2025
    ]
    return GrilleSalaires(
        zone_type="national",
        zone_libelle="National — SMH",
        minima=minima,
        date_effet="2025",
        source_titre="Barème unique SMH métallurgie (seed 2025)",
    )


def _build_prime() -> PrimeAnciennete:
    return PrimeAnciennete(
        bareme=[],
        base_de_calcul=BaseCalculPrime(
            methode="metallurgie_prime_anciennete",
            valeur=5.83,
        ),
        taux_par_classe=dict(_TAUX_PRIME_PAR_CLASSE),
        eligibilite=PrimeAncienneteEligibilite(
            min_annees=3.0,
            max_annees=15.0,
            statuts_exclus=["Cadre"],
            classe_max_taux=10,
        ),
        prorata=PrimeAncienneteProrata(
            enabled=True,
            mode="heures_contrat",
            inclure_heures_sup=True,
            maladie_si_maintien=True,
            sans_pointage_policy="plein_mois",
        ),
        valeurs_point=[
            ValeurPointZone(
                zone_type="national",
                zone_libelle="National — valeur du point",
                departements=[],
                valeur=5.83,
            ),
            ValeurPointZone(
                zone_type="departemental",
                zone_libelle="Deux-Sèvres — valeur du point",
                departements=["79"],
                valeur=5.70,
            ),
            ValeurPointZone(
                zone_type="departemental",
                zone_libelle="Seine-et-Marne — valeur du point",
                departements=["77"],
                valeur=5.24,
            ),
        ],
    )


def _build_cp_anciennete() -> CpAnciennete:
    return CpAnciennete(
        mode="cumulative_rules",
        seniority_reference="cp_period_end",
        tiers=[
            CpAncienneteTier(category="all", min_years=2, days=1),
            CpAncienneteTier(category="all", min_years=2, min_age=45, days=1),
            CpAncienneteTier(category="all", min_years=20, min_age=55, days=1),
            CpAncienneteTier(category="forfait", min_years=1, days=1),
        ],
    )


METALLURGIE_3248_SEED = CCRulesSeed(
    grille=_build_smh_grille(),
    prime=_build_prime(),
    cp_anciennete=_build_cp_anciennete(),
)
