"""
Jours de repos « seniors » — convention de la plasturgie (IDCC 292).

Source : accord du 18 avril 2025, non étendu, applicable au 1er juin 2025
(data/_sources/plasturgie/accord-18-04-2025-repos-seniors-lu-23-11-2026.txt).

Article 3 — chaque 1er juin, à partir du 1er juin 2025 :
- 1 jour pour un salarié de 58 ou 59 ans ;
- 2 jours dès 60 ans.
Aucun jour si le salarié a été absent, quel qu'en soit le motif, pendant toute
la période continue de 12 mois du 1er juin N-1 au 31 mai N. Une absence
partielle ne fait rien perdre.

Article 4 — les jours se prennent du 1er juin N au 31 mai N+1 (à défaut de
période fixée par l'entreprise), puis ils sont perdus. Un jour vaut une journée
de travail, quel que soit le rythme : pas de prorata, pas de demi-journée. Pas
de perte de salaire. Pas d'indemnité à la rupture.

Ce sont des jours de REPOS, pas des congés payés : un compteur à part, comme
les JTC. Le type d'absence `repos_senior` n'écrit pas le calendrier, si bien que
la paie ne retire rien.

Décision du client du 23/11/2026 : la règle existe, mais la case de la société
(`repos_seniors_enabled`) est éteinte partout.

Module pur : aucune I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.shared.domain.pluriel import accord, pluriel

#: Type d'absence posé pour prendre un jour de repos senior.
TYPE_REPOS_SENIOR = "repos_senior"

#: Entrée en vigueur de l'accord (article 5) : première attribution.
PREMIERE_ATTRIBUTION = date(2025, 6, 1)

#: Âge (au 1er juin) et jours attribués, du seuil le plus haut au plus bas.
PALIERS_AGE_JOURS: tuple[tuple[int, int], ...] = ((60, 2), (58, 1))

ALERTE_DATE_NAISSANCE = (
    "Repos seniors : date de naissance absente de la fiche, aucun jour "
    "attribué. Renseignez-la pour calculer le droit."
)


@dataclass(frozen=True)
class DroitReposSeniors:
    """Droit d'une période : jours attribués au 1er juin N, à prendre jusqu'au 31 mai N+1."""

    jours: int
    premier_juin: date
    fin_de_prise: date
    age: int | None = None
    #: Pourquoi le droit vaut ce qu'il vaut, en une phrase lisible.
    motif: str = ""
    #: Donnée manquante qui empêche le calcul : à montrer, jamais à taire.
    alerte: str | None = None


def age_au(date_naissance: date, jour: date) -> int:
    """Âge révolu à `jour` (l'anniversaire du jour compte)."""
    age = jour.year - date_naissance.year
    if (jour.month, jour.day) < (date_naissance.month, date_naissance.day):
        age -= 1
    return age


def premier_juin_de_rattachement(jour: date) -> date:
    """Le 1er juin qui ouvre la période de prise contenant `jour`."""
    annee = jour.year if (jour.month, jour.day) >= (6, 1) else jour.year - 1
    return date(annee, 6, 1)


def fin_de_prise(premier_juin: date) -> date:
    """Dernier jour pour prendre les jours attribués au `premier_juin` : 31 mai N+1."""
    return date(premier_juin.year + 1, 5, 31)


def jours_selon_age(age: int) -> int:
    for seuil, jours in PALIERS_AGE_JOURS:
        if age >= seuil:
            return jours
    return 0


def _parse_jour(valeur: Any) -> date | None:
    if isinstance(valeur, date):
        return valeur
    if not valeur:
        return None
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def _jours_entiers_d_absence(absence: Mapping[str, Any]) -> set[date]:
    """Jours où le salarié n'a pas travaillé du tout.

    Une demi-journée ou un repos pris en heures laisse une part de travail :
    ce jour-là, l'absence n'est que partielle."""
    partiels: set[date] = set()
    for cle in ("demi_journees", "heures_par_jour"):
        valeurs = absence.get(cle)
        if isinstance(valeurs, Mapping):
            partiels |= {j for j in (_parse_jour(k) for k in valeurs) if j}
    jours = {j for j in (_parse_jour(v) for v in absence.get("selected_days") or []) if j}
    return jours - partiels


def _feries_par_defaut(debut: date, fin: date) -> set[date]:
    from app.modules.absences.domain.rtt_forfait import french_public_holiday_dates

    feries: set[date] = set()
    for annee in range(debut.year, fin.year + 1):
        feries.update(french_public_holiday_dates(annee))
    return feries


def absent_toute_la_periode(
    absences_validees: Iterable[Mapping[str, Any]],
    debut: date,
    fin: date,
    *,
    jours_feries: Iterable[date] | None = None,
) -> bool:
    """Le salarié a-t-il été absent sans interruption de `debut` à `fin` ?

    Tous les motifs comptent (article 3 : « quelle qu'en soit le motif »).
    Les absences ne couvrent que les jours ouvrés (un congé ne se pose pas le
    dimanche) : la période est jugée sur les lundis à vendredis hors fériés.
    Un seul jour ouvré sans absence entière suffit à rompre la continuité.
    """
    couverts: set[date] = set()
    for absence in absences_validees:
        statut = absence.get("status")
        if statut is not None and statut != "validated":
            continue
        couverts |= _jours_entiers_d_absence(absence)
    feries = set(jours_feries) if jours_feries is not None else _feries_par_defaut(debut, fin)
    jour = debut
    while jour <= fin:
        if jour.weekday() < 5 and jour not in feries and jour not in couverts:
            return False
        jour += timedelta(days=1)
    return True


def droit_repos_seniors(
    date_naissance: date | None,
    premier_juin: date,
    absences_validees: Iterable[Mapping[str, Any]],
    *,
    date_embauche: date | None = None,
    jours_feries: Iterable[date] | None = None,
) -> DroitReposSeniors:
    """Jours de repos seniors attribués au `premier_juin` (article 3).

    - âge lu au 1er juin, sur la date de naissance ;
    - date de naissance absente : 0 jour et une alerte ;
    - absence continue du 1er juin N-1 au 31 mai N : 0 jour ;
    - salarié entré après le 1er juin : rien pour cette période, l'attribution
      a eu lieu avant son arrivée.
    """
    fin = fin_de_prise(premier_juin)
    if (premier_juin.month, premier_juin.day) != (6, 1):
        raise ValueError("Les repos seniors s'attribuent le 1er juin.")
    if premier_juin < PREMIERE_ATTRIBUTION:
        return DroitReposSeniors(
            jours=0,
            premier_juin=premier_juin,
            fin_de_prise=fin,
            motif="L'accord du 18 avril 2025 s'applique à partir du 1er juin 2025.",
        )
    if date_naissance is None:
        return DroitReposSeniors(
            jours=0,
            premier_juin=premier_juin,
            fin_de_prise=fin,
            alerte=ALERTE_DATE_NAISSANCE,
        )
    age = age_au(date_naissance, premier_juin)
    if date_embauche is not None and date_embauche > premier_juin:
        return DroitReposSeniors(
            jours=0,
            premier_juin=premier_juin,
            fin_de_prise=fin,
            age=age,
            motif=(
                f"Entré après le 1er juin {premier_juin.year} : premier droit "
                f"au 1er juin {premier_juin.year + 1}."
            ),
        )
    jours = jours_selon_age(age)
    if jours == 0:
        return DroitReposSeniors(
            jours=0,
            premier_juin=premier_juin,
            fin_de_prise=fin,
            age=age,
            motif=f"{age} ans au 1er juin {premier_juin.year} : le droit s'ouvre à 58 ans.",
        )
    debut_reference = date(premier_juin.year - 1, 6, 1)
    fin_reference = date(premier_juin.year, 5, 31)
    if absent_toute_la_periode(
        absences_validees, debut_reference, fin_reference, jours_feries=jours_feries
    ):
        return DroitReposSeniors(
            jours=0,
            premier_juin=premier_juin,
            fin_de_prise=fin,
            age=age,
            motif=(
                f"Absent sans interruption du 1er juin {debut_reference.year} au "
                f"31 mai {fin_reference.year} : aucun jour (accord du 18 avril 2025, art. 3)."
            ),
        )
    return DroitReposSeniors(
        jours=jours,
        premier_juin=premier_juin,
        fin_de_prise=fin,
        age=age,
        motif=(
            f"{age} ans au 1er juin {premier_juin.year} : "
            f"{pluriel(jours, 'jour')} à prendre jusqu'au 31 mai {fin.year}."
        ),
    )


def jours_repos_seniors_poses(
    absences_validees: Iterable[Mapping[str, Any]], debut: date, fin: date
) -> float:
    """Jours `repos_senior` validés entre `debut` et `fin` inclus."""
    total = 0.0
    for absence in absences_validees:
        if absence.get("type") != TYPE_REPOS_SENIOR:
            continue
        statut = absence.get("status")
        if statut is not None and statut != "validated":
            continue
        for valeur in absence.get("selected_days") or []:
            jour = _parse_jour(valeur)
            if jour is not None and debut <= jour <= fin:
                total += 1
    return total


def solde_repos_seniors(
    absences_validees: list[Mapping[str, Any]],
    ref_date: date,
    *,
    enabled: bool,
    date_naissance: date | None,
    date_embauche: date | None = None,
) -> dict[str, Any]:
    """Compteur du jour : droit de la période en cours, jours pris, restant.

    La période change le 1er juin : les jours de la période close ne sont
    plus comptés (perdus, article 4). Case éteinte : compteur à zéro, sans
    alerte, et l'écran ne l'affiche pas."""
    if not enabled:
        return {"acquis": 0.0, "pris": 0.0, "solde": 0.0}
    premier_juin = premier_juin_de_rattachement(ref_date)
    droit = droit_repos_seniors(
        date_naissance, premier_juin, absences_validees, date_embauche=date_embauche
    )
    pris = jours_repos_seniors_poses(
        absences_validees, premier_juin, min(ref_date, droit.fin_de_prise)
    )
    acquis = float(droit.jours)
    solde: dict[str, Any] = {
        "acquis": acquis,
        "pris": round(pris, 2),
        "solde": round(max(0.0, acquis - pris), 2),
    }
    if droit.alerte:
        solde["alerte"] = droit.alerte
    return solde


def refus_pose_repos_seniors(
    *,
    enabled: bool,
    jours_demandes: Iterable[date],
    demi_journees: bool,
    droit_par_periode: Mapping[date, DroitReposSeniors],
    deja_poses_par_periode: Mapping[date, float],
) -> str | None:
    """La phrase qui refuse une pose de repos senior, ou `None`.

    Chaque jour demandé est rattaché à la période (1er juin) qui le contient ;
    les jours d'une période ne peuvent dépasser le droit de cette période."""
    if not enabled:
        return "Les repos seniors ne sont pas activés pour cette société."
    if demi_journees:
        return (
            "Un repos senior se prend à la journée entière (accord du 18 avril "
            "2025, art. 4 : une journée de travail, sans prorata)."
        )
    demandes_par_periode: dict[date, int] = {}
    for jour in jours_demandes:
        cle = premier_juin_de_rattachement(jour)
        demandes_par_periode[cle] = demandes_par_periode.get(cle, 0) + 1
    for premier_juin in sorted(demandes_par_periode):
        droit = droit_par_periode.get(premier_juin)
        if droit is None:
            return f"Droit aux repos seniors inconnu pour la période du 1er juin {premier_juin.year}."
        if droit.alerte:
            return droit.alerte
        demandes = demandes_par_periode[premier_juin]
        deja = float(deja_poses_par_periode.get(premier_juin, 0.0))
        restant = max(0.0, droit.jours - deja)
        if demandes > restant:
            restant_txt = int(restant) if float(restant).is_integer() else restant
            return (
                f"Repos seniors insuffisants : {pluriel(restant_txt, 'jour')} "
                f"{accord(restant, 'restant')} sur la période du "
                f"1er juin {premier_juin.year} au 31 mai {premier_juin.year + 1}, "
                f"pour {pluriel(demandes, 'jour')} {accord(demandes, 'demandé')}."
            )
    return None
