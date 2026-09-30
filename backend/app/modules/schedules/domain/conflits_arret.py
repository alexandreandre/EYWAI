"""Heures saisies au réel un jour où le prévu est un arrêt ou une absence non travaillée.

Le moteur range dans les jours non travaillés tout jour prévu qui n'est pas
`travail` (`payroll.application.analyzer`), puis compte chaque heure réelle
de la semaine : une heure pointée un jour d'arrêt devient une heure travaillée,
souvent une heure sup, et l'arrêt n'est plus retenu ce jour-là. Constat du
30/09/2026 : une salariée en arrêt tout septembre en recevait 70,75 h à 50 %.

Ce module dit quels jours sont dans ce cas. La génération refuse de calculer
tant qu'il en reste, l'import des pointages les signale, l'écran les montre.

Module pur : l'appelant fournit le prévu et le réel (avec `annee`/`mois` sur
chaque entrée quand plusieurs mois sont en jeu).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

from app.shared.domain.absence_calendar import ABSENCE_CALENDAR_TYPES

#: Absences que le moteur traite comme non travaillées, en plus des arrêts
#: (tout type qui commence par `arret`, comme dans `calcul_brut`) :
#: - ce qu'écrit la validation d'une absence (`ABSENCE_CALENDAR_TYPES`) ;
#: - les absences que `calcul_brut._est_une_absence` retient ;
#: - les suspensions sans salaire qui réduisent le plafond (`calcul_cotisations`).
#: Restent hors conflit : `travail`/`work`, `weekend`, `repos` et `ferie` (y
#: travailler se paie), et `absence_justifiee`, que le moteur paie comme des
#: heures faites (reprises DSN, souvent partielles).
TYPES_ABSENCE_NON_TRAVAILLEE: frozenset[str] = frozenset(
    ABSENCE_CALENDAR_TYPES
    | {"absence_non_remuneree", "sans_solde", "conge_sans_solde"}
)
_PREFIXES_NON_TRAVAILLES = ("arret", "absence_injustifiee")
#: Jours qu'un arrêt couvre sans que sa validation les retype
#: (`absences.infrastructure.providers.CalendarUpdateProvider`).
TYPES_NON_OUVRES_D_UN_ARRET: frozenset[str] = frozenset({"weekend", "repos", "ferie"})

#: Statut d'une demande d'absence validée (`absences.domain.enums.AbsenceStatus`).
_STATUT_VALIDE = "validated"

_MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

_LIBELLES = {
    "conges_payes": "congés payés",
    "conge": "congé",
    "rtt": "RTT",
    "evenement_familial": "événement familial",
    "absence_non_remuneree": "absence non rémunérée",
    "sans_solde": "congé sans solde",
    "conge_sans_solde": "congé sans solde",
}


@dataclass(frozen=True)
class JourEnConflit:
    jour: int
    type_prevu: str
    heures_saisies: float
    annee: int | None = None
    mois: int | None = None

    def en_detail(self) -> dict[str, Any]:
        """Le jour tel que l'API le rend : `{annee, mois, jour, heures}`."""
        return {
            "annee": self.annee,
            "mois": self.mois,
            "jour": self.jour,
            "heures": self.heures_saisies,
        }


def est_un_arret(type_jour: str | None) -> bool:
    return str(type_jour or "").startswith("arret")


def est_absence_non_travaillee(type_jour: str | None) -> bool:
    type_jour = str(type_jour or "")
    return type_jour in TYPES_ABSENCE_NON_TRAVAILLEE or type_jour.startswith(
        _PREFIXES_NON_TRAVAILLES
    )


def _demi_journee(entree: Mapping[str, Any]) -> bool:
    """Demi-journée d'absence : l'autre moitié a pu être travaillée."""
    try:
        quotite = float(entree.get("quotite_absence") or 1.0)
    except (TypeError, ValueError):
        return False
    return 0.0 < quotite < 1.0


def _jour_prevu_sans_heures(entree: Mapping[str, Any]) -> bool:
    """Le type prévu interdit toute heure : arrêt ou absence non travaillée,
    pas une demi-journée."""
    return est_absence_non_travaillee(entree.get("type")) and not _demi_journee(entree)


def _entier(valeur: Any) -> int | None:
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _cle(entree: Mapping[str, Any]) -> tuple[int | None, int | None, int] | None:
    jour = _entier(entree.get("jour"))
    if jour is None:
        return None
    return _entier(entree.get("annee")), _entier(entree.get("mois")), jour


def _heures(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _jours_d_arret_valides(
    absences_validees: Iterable[Mapping[str, Any]] | None,
) -> dict[tuple[int, int, int], str]:
    """(année, mois, jour) → type d'arrêt, pour les arrêts validés."""
    jours: dict[tuple[int, int, int], str] = {}
    for absence in absences_validees or []:
        type_absence = str(absence.get("type") or "")
        if not est_un_arret(type_absence):
            continue
        if str(absence.get("status") or _STATUT_VALIDE) != _STATUT_VALIDE:
            continue
        for brut in absence.get("selected_days") or []:
            try:
                d = date.fromisoformat(str(brut)[:10])
            except ValueError:
                continue
            jours[(d.year, d.month, d.day)] = type_absence
    return jours


def jours_sans_heures(
    calendrier_prevu: list[dict],
    absences_validees: list[dict] | None = None,
) -> dict[tuple[int | None, int | None, int], str]:
    """Les jours prévus qui ne peuvent porter aucune heure réelle :
    `(annee, mois, jour)` → type d'absence en cause.

    - Le prévu est un arrêt ou une absence non travaillée (hors demi-journée) :
      son type.
    - Le prévu est un week-end, un repos ou un férié couvert par un **arrêt**
      validé de `absences_validees` (demandes `{type, status, selected_days}`) :
      le type de l'arrêt. La validation d'un arrêt ne retype pas ces jours, et
      les métadonnées qu'elle y pose ne survivent pas à une sauvegarde du
      planning : seule la demande validée dit qu'ils sont couverts. Il faut
      des entrées datées (`annee`, `mois`) pour les rapprocher.
    Les congés payés et les autres absences suivent le seul type prévu.
    """
    arrets = _jours_d_arret_valides(absences_validees)
    interdits: dict[tuple[int | None, int | None, int], str] = {}
    for entree in calendrier_prevu or []:
        cle = _cle(entree)
        if cle is None:
            continue
        if _jour_prevu_sans_heures(entree):
            interdits[cle] = str(entree["type"])
            continue
        annee, mois, jour = cle
        if (
            str(entree.get("type") or "") in TYPES_NON_OUVRES_D_UN_ARRET
            and annee is not None
            and mois is not None
            and (annee, mois, jour) in arrets
        ):
            interdits[cle] = arrets[(annee, mois, jour)]
    return interdits


def jours_en_conflit(
    calendrier_prevu: list[dict],
    calendrier_reel: list[dict],
    absences_validees: list[dict] | None = None,
) -> list[JourEnConflit]:
    """Les jours de `jours_sans_heures` dont le réel porte des heures (> 0),
    triés par date. `type_prevu` est le type d'absence en cause : pour un
    week-end d'arrêt, le type de l'arrêt validé."""
    interdits = jours_sans_heures(calendrier_prevu, absences_validees)

    heures_par_cle: dict[tuple[int | None, int | None, int], float] = {}
    for entree in calendrier_reel or []:
        cle = _cle(entree)
        if cle is not None:
            heures_par_cle[cle] = round(
                heures_par_cle.get(cle, 0.0) + _heures(entree.get("heures_faites")), 2
            )

    conflits = [
        JourEnConflit(cle[2], interdits[cle], heures, annee=cle[0], mois=cle[1])
        for cle, heures in heures_par_cle.items()
        if heures > 0 and cle in interdits
    ]
    return sorted(conflits, key=lambda c: (c.annee or 0, c.mois or 0, c.jour))


# --- Le message du refus ---


def _libelle_jour(jour: int) -> str:
    return "1er" if jour == 1 else str(jour)


def _enumerer(elements: Sequence[str]) -> str:
    if len(elements) <= 1:
        return "".join(elements)
    return f"{', '.join(elements[:-1])} et {elements[-1]}"


def libelle_des_dates(dates: Iterable[tuple[int, int, int]]) -> str:
    """« le 31 août et les 1er et 2 septembre » pour des (année, mois, jour)."""
    par_mois: dict[tuple[int, int], list[int]] = {}
    for annee, mois, jour in sorted(set(dates)):
        par_mois.setdefault((annee, mois), []).append(jour)
    groupes = []
    for (_, mois), jours in par_mois.items():
        nom_mois = _MOIS[mois - 1] if 1 <= mois <= 12 else ""
        article = "le" if len(jours) == 1 else "les"
        texte = f"{article} {_enumerer([_libelle_jour(j) for j in jours])} {nom_mois}"
        groupes.append(texte.strip())
    return _enumerer(groupes)


def libelle_des_jours(conflits: Sequence[JourEnConflit]) -> str:
    """Les jours en conflit, chaque mois nommé."""
    return libelle_des_dates((c.annee or 0, c.mois or 0, c.jour) for c in conflits)


def libelle_absence(type_jour: str) -> str:
    return _LIBELLES.get(type_jour) or type_jour.replace("_", " ")


def message_de_refus(prenom: str, conflits: Sequence[JourEnConflit]) -> str:
    """La phrase du refus de génération : qui, quoi, quels jours."""
    arrets = [c for c in conflits if est_un_arret(c.type_prevu)]
    absences = [c for c in conflits if not est_un_arret(c.type_prevu)]
    phrases = []
    if arrets:
        phrases.append(
            f"{prenom} est en arrêt, mais des heures sont saisies "
            f"{libelle_des_jours(arrets)}."
        )
    if absences:
        types = list(dict.fromkeys(libelle_absence(c.type_prevu) for c in absences))
        phrases.append(
            f"{prenom} a une absence ({', '.join(types)}), mais des heures sont "
            f"saisies {libelle_des_jours(absences)}."
        )
    return " ".join(phrases)


__all__ = [
    "JourEnConflit",
    "TYPES_ABSENCE_NON_TRAVAILLEE",
    "TYPES_NON_OUVRES_D_UN_ARRET",
    "est_absence_non_travaillee",
    "est_un_arret",
    "jours_en_conflit",
    "jours_sans_heures",
    "libelle_absence",
    "libelle_des_dates",
    "libelle_des_jours",
    "message_de_refus",
]
