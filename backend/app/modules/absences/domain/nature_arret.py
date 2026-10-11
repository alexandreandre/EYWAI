"""Nature d'un arrêt de travail et type d'arrêt : ce qui va ensemble.

La nature (`type` de la demande : arrêt maladie, accident du travail…) décide
du motif DSN et de l'attestation de salaire (salaires nets en AT/MP) ; le type
d'arrêt (`arret_type`) décide du maintien de salaire et des IJSS (carences,
taux). Une combinaison qui les fait diverger — « Arrêt maladie » typé
« Accident du travail » : maintien sans carence d'un AT, DSN et attestation
d'une maladie — est refusée à l'enregistrement.

La parentalité n'a pas encore de type d'arrêt propre (défaut F12, décision
attendue) : sous « Congé maternité » ou « Congé paternité », le seul choix
possible à l'écran, « Maladie simple », reste permis, comme « Arrêt
exceptionnel ».

Module pur.
"""

from __future__ import annotations

from typing import Optional

LIBELLES_NATURE: dict[str, str] = {
    "arret_maladie": "Arrêt maladie",
    "arret_at": "Accident du travail",
    "arret_maladie_pro": "Maladie professionnelle",
    "arret_maternite": "Congé maternité",
    "arret_paternite": "Congé paternité",
}

LIBELLES_TYPE_D_ARRET: dict[str, str] = {
    "maladie_simple": "Maladie simple",
    "accident_travail": "Accident du travail",
    "maladie_professionnelle": "Maladie professionnelle",
    "accident_trajet": "Accident de trajet",
    "mi_temps_therapeutique": "Mi-temps thérapeutique",
    "ald": "ALD",
    "rechute_at": "Rechute AT",
    "arret_exceptionnel": "Arrêt exceptionnel",
}

#: Types d'arrêt permis pour chaque nature, dans l'ordre de l'écran.
TYPES_D_ARRET_PAR_NATURE: dict[str, tuple[str, ...]] = {
    "arret_maladie": (
        "maladie_simple",
        "ald",
        "mi_temps_therapeutique",
        "arret_exceptionnel",
    ),
    "arret_at": ("accident_travail", "accident_trajet", "rechute_at"),
    "arret_maladie_pro": ("maladie_professionnelle", "rechute_at"),
    "arret_maternite": ("maladie_simple", "arret_exceptionnel"),
    "arret_paternite": ("maladie_simple", "arret_exceptionnel"),
}

#: La nature à proposer quand on garde le type d'arrêt choisi.
NATURE_DU_TYPE_D_ARRET: dict[str, str] = {
    "maladie_simple": "arret_maladie",
    "ald": "arret_maladie",
    "mi_temps_therapeutique": "arret_maladie",
    "arret_exceptionnel": "arret_maladie",
    "accident_travail": "arret_at",
    "accident_trajet": "arret_at",
    "rechute_at": "arret_at",
    "maladie_professionnelle": "arret_maladie_pro",
}


def _guillemets(libelle: str) -> str:
    return f"« {libelle} »"


def _enumerer(libelles: list[str]) -> str:
    if len(libelles) <= 1:
        return "".join(libelles)
    return f"{', '.join(libelles[:-1])} ou {libelles[-1]}"


def incoherence_nature_type_d_arret(
    nature: Optional[str], type_arret: Optional[str]
) -> Optional[str]:
    """La phrase de refus si le type d'arrêt ne va pas avec la nature, sinon None.

    Rien à contrôler hors arrêt de travail, ni sans type d'arrêt (le schéma
    d'entrée l'exige déjà pour un arrêt).
    """
    permis = TYPES_D_ARRET_PAR_NATURE.get(str(nature or ""))
    if permis is None or not type_arret or type_arret in permis:
        return None
    libelle_type = LIBELLES_TYPE_D_ARRET.get(type_arret, type_arret)
    libelle_nature = LIBELLES_NATURE[str(nature)]
    choix = _enumerer([_guillemets(LIBELLES_TYPE_D_ARRET[t]) for t in permis])
    message = (
        f"Le type d'arrêt {_guillemets(libelle_type)} ne correspond pas à la nature "
        f"{_guillemets(libelle_nature)}. Pour cette nature, choisissez {choix}"
    )
    autre_nature = NATURE_DU_TYPE_D_ARRET.get(type_arret)
    if autre_nature and autre_nature != nature:
        message += (
            f" ; ou gardez {_guillemets(libelle_type)} et choisissez la nature "
            f"{_guillemets(LIBELLES_NATURE[autre_nature])}"
        )
    return message + "."


__all__ = [
    "LIBELLES_NATURE",
    "LIBELLES_TYPE_D_ARRET",
    "NATURE_DU_TYPE_D_ARRET",
    "TYPES_D_ARRET_PAR_NATURE",
    "incoherence_nature_type_d_arret",
]
