"""Maintien du salaire pendant les congés de maternité, de paternité et d'adoption.

Ce que chaque convention impose (textes relus sur Légifrance le 13-14/11/2026) :

- Métallurgie (IDCC 3248), CCN du 07/02/2022 :
  - art. 92.1.1 : maternité indemnisée à 100 %, plus d'un an d'ancienneté à la
    date de l'arrêt ;
  - art. 92.2 : adoption, mêmes règles, un an à l'arrivée de l'enfant au foyer ;
  - rien pour la paternité.
- Plasturgie (IDCC 292) :
  - avenant collaborateurs art. 12 et avenant cadres art. 6 : maternité
    indemnisée pendant 16 semaines, sans condition d'ancienneté, sur le net,
    sous déduction des IJ « déclarées à l'entreprise par l'intéressée » ;
  - annexe X art. 9 (accord du 08/12/2010, étendu) : paternité à 100 % pour
    tout salarié, pendant la durée légale ;
  - adoption : aucune clause trouvée, pas de maintien imposé.
- Syntec (IDCC 1486), avenant n° 49 du 22/10/2025, en vigueur au 01/05/2026 :
  maternité, adoption et paternité maintenues après un an d'ancienneté. La
  paternité est bornée au plafond de la Sécurité sociale, que Martine
  n'applique pas encore (alerte).

Sans convention, le Code du travail n'impose aucun maintien. Le réglage de la
société « maintien pendant les congés parentaux » reste possible : il étend le
maintien à tous ces congés, au-delà de la convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MATERNITE = "maternite"
PATERNITE = "paternite"
ADOPTION = "adoption"

_TYPES = {
    "maternite": MATERNITE,
    "maternite_paternite": MATERNITE,
    "paternite": PATERNITE,
    "paternite_accueil_enfant": PATERNITE,
    "adoption": ADOPTION,
}


@dataclass(frozen=True)
class RegleParentalite:
    anciennete_min_mois: int
    #: Jours calendaires maintenus depuis le début du congé (None : tout le congé).
    jours_max: Optional[int]
    source: str
    alerte: Optional[str] = None


_REGLES: dict[tuple[str, str], RegleParentalite] = {
    ("3248", MATERNITE): RegleParentalite(12, None, "CCN métallurgie, art. 92.1.1"),
    ("3248", ADOPTION): RegleParentalite(12, None, "CCN métallurgie, art. 92.2"),
    ("292", MATERNITE): RegleParentalite(
        0, 16 * 7, "CCN plasturgie, avenant collaborateurs art. 12 et cadres art. 6"
    ),
    ("292", PATERNITE): RegleParentalite(0, None, "CCN plasturgie, annexe X art. 9"),
    ("1486", MATERNITE): RegleParentalite(12, None, "CCN Syntec, art. 9.3 (avenant n° 49)"),
    ("1486", ADOPTION): RegleParentalite(12, None, "CCN Syntec, art. 9.3 (avenant n° 49)"),
    ("1486", PATERNITE): RegleParentalite(
        12,
        None,
        "CCN Syntec, art. 9.3 (avenant n° 49)",
        alerte=(
            "Congé de paternité Syntec : le maintien est borné au plafond de la "
            "Sécurité sociale, que Martine n'applique pas. Pour un salaire au-dessus "
            "du plafond, corrigez le maintien à la main."
        ),
    ),
}

_LIBELLES = {MATERNITE: "maternité", PATERNITE: "paternité", ADOPTION: "adoption"}


def type_parental(arret_type: str) -> Optional[str]:
    return _TYPES.get((arret_type or "").strip())


def normaliser_idcc(idcc: object) -> str:
    return str(idcc or "").strip().lstrip("0")


def regle_parentalite(idcc: object, arret_type: str) -> Optional[RegleParentalite]:
    """La règle de la convention, ou None si elle n'impose aucun maintien."""
    nature = type_parental(arret_type)
    if nature is None:
        return None
    return _REGLES.get((normaliser_idcc(idcc), nature))


def decider_parentalite(
    *,
    idcc: object,
    arret_type: str,
    anciennete_mois: int,
    maintien_societe: bool,
    anciennete_min_societe: int,
) -> dict:
    """Maintenu ou non, pourquoi, et sur combien de jours.

    La convention s'applique d'office ; le réglage de la société l'étend (plus
    favorable), avec la condition d'ancienneté du maintien maladie, comme avant.
    """
    nature = type_parental(arret_type) or MATERNITE
    libelle = _LIBELLES[nature]
    regle = regle_parentalite(idcc, arret_type)
    if regle is not None and anciennete_mois >= regle.anciennete_min_mois:
        return {
            "maintenu": True,
            "par_convention": True,
            "jours_max": regle.jours_max,
            "source": regle.source,
            "alerte": regle.alerte,
            "motif": None,
        }
    if maintien_societe and anciennete_mois >= anciennete_min_societe:
        return {
            "maintenu": True,
            "par_convention": False,
            "jours_max": None,
            "source": "Réglage de la société",
            "alerte": None,
            "motif": None,
        }
    if regle is not None:
        motif = (
            f"Pas de maintien pendant le congé de {libelle} : la convention ({regle.source}) "
            f"demande {regle.anciennete_min_mois} mois d'ancienneté au début du congé, "
            f"le salarié en a {anciennete_mois}."
        )
    else:
        motif = (
            f"Pas de maintien pendant le congé de {libelle} : ni la convention ni le "
            "réglage de la société ne le prévoient. La caisse verse les indemnités "
            "journalières au salarié."
        )
    return {
        "maintenu": False,
        "par_convention": regle is not None,
        "jours_max": None,
        "source": regle.source if regle else None,
        "alerte": None,
        "motif": motif,
    }
