"""Activité partielle posée en masse : quels jours passent, lesquels sont laissés.

Règle pure, sans lecture ni écriture. Un jour qui passe est écrit comme la pose
d'activité partielle au calendrier d'un salarié (`saisieGroupeeDuJour` côté
écran) : le prévu est retypé « Activité partielle » et garde ses heures
prévues (ce sont les heures chômées) ; le réel est retypé avec 0 heure faite
(« Non travaillé » au forfait jours). Le calcul du bulletin reste celui du
calendrier unitaire (`activite_partielle.domain.calendrier.jours_chomes`).

Un jour n'est jamais écrasé : hors contrat, bulletin du mois validé, déjà en
activité partielle, absence (arrêt, congé, école…), repos, week-end ou férié,
heures faites déjà saisies. Il est laissé, avec sa raison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping

from app.modules.schedules.domain.rules import coerce_jour

TYPE_AP = "activite_partielle"

RAISON_HORS_CONTRAT = "hors_contrat"
RAISON_BULLETIN_VALIDE = "bulletin_valide"
RAISON_DEJA_AP = "deja_ap"
RAISON_ABSENCE = "absence"
RAISON_REPOS = "repos"
RAISON_HEURES_SAISIES = "heures_saisies"
#: Posée à l'enregistrement seulement : le calendrier n'a pas pu être écrit.
RAISON_ECHEC = "echec"

#: Ordre d'affichage des raisons, et leur phrase.
LIBELLES_RAISONS: dict[str, str] = {
    RAISON_ABSENCE: "jour d'arrêt, de congé ou d'une autre absence",
    RAISON_REPOS: "repos, week-end ou jour férié",
    RAISON_BULLETIN_VALIDE: "bulletin du mois déjà validé",
    RAISON_HORS_CONTRAT: "hors contrat (avant l'entrée ou après la sortie)",
    RAISON_DEJA_AP: "déjà en activité partielle",
    RAISON_HEURES_SAISIES: "des heures faites sont déjà saisies ce jour-là",
    RAISON_ECHEC: "calendrier non enregistré (erreur)",
}

#: Types d'un jour que l'activité partielle peut remplacer : un jour de travail.
TYPES_DE_TRAVAIL = frozenset({"travail", "work", ""})
#: Jours non travaillés prévus : jamais chômés au titre de l'activité partielle.
TYPES_DE_REPOS = frozenset({"weekend", "repos", "rest", "ferie"})


@dataclass(frozen=True)
class ContexteSalarie:
    """Ce qu'il faut savoir d'un salarié pour juger ses jours."""

    forfait_jours: bool = False
    entree: date | None = None
    sortie: date | None = None
    #: (année, mois) dont le bulletin est validé, ou repris de l'ancien logiciel.
    mois_figes: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    #: Jours couverts par un arrêt validé (ses week-ends gardent leur type au planning).
    jours_d_arret: frozenset[date] = field(default_factory=frozenset)
    #: Jours fériés observés par la société.
    feries: frozenset[date] = field(default_factory=frozenset)


def _nombre(valeur: Any) -> float:
    try:
        return float(valeur or 0)
    except (TypeError, ValueError):
        return 0.0


def raison_de_laisser(
    quand: date,
    prevu: Mapping[str, Any] | None,
    reel: Mapping[str, Any] | None,
    ctx: ContexteSalarie,
) -> str | None:
    """La raison de laisser ce jour tel quel ; None s'il passe en activité partielle."""
    if (ctx.entree and quand < ctx.entree) or (ctx.sortie and quand > ctx.sortie):
        return RAISON_HORS_CONTRAT
    if (quand.year, quand.month) in ctx.mois_figes:
        return RAISON_BULLETIN_VALIDE
    type_jour = str((prevu or {}).get("type") or "")
    if type_jour == TYPE_AP:
        return RAISON_DEJA_AP
    if quand in ctx.jours_d_arret:
        return RAISON_ABSENCE
    if prevu is None:
        # Jour sans planning : l'écran le montre « Week-end », « Férié » ou
        # « Travail » ; seul ce dernier peut chômer.
        if quand.weekday() >= 5 or quand in ctx.feries:
            return RAISON_REPOS
    else:
        if (prevu.get("origine") or "") == "absence":
            return RAISON_ABSENCE
        if type_jour in TYPES_DE_REPOS:
            return RAISON_REPOS
        if type_jour not in TYPES_DE_TRAVAIL:
            return RAISON_ABSENCE
        if quand in ctx.feries:
            return RAISON_REPOS
        heures = prevu.get("heures_prevues")
        # 0 h prévue (temps partiel, jour non prévu au forfait) : rien à chômer.
        if heures is not None and _nombre(heures) <= 0:
            return RAISON_REPOS
    if _nombre((reel or {}).get("heures_faites")) > 0:
        return RAISON_HEURES_SAISIES
    return None



def jour_en_activite_partielle(
    jour: int, prevu: Mapping[str, Any] | None, *, forfait_jours: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Le prévu et le réel d'un jour passé en activité partielle, comme au
    calendrier du salarié : les heures prévues restent (un jour sans planning
    vaut ce que l'écran affiche : rien en heures, une journée au forfait), le
    réel passe à 0."""
    if prevu is None:
        heures = 1.0 if forfait_jours else None
    else:
        heures = prevu.get("heures_prevues")
    return (
        {"jour": jour, "type": TYPE_AP, "heures_prevues": heures},
        {"jour": jour, "type": TYPE_AP, "heures_faites": 0},
    )


def _par_jour(entrees: Iterable[Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for e in entrees or []:
        if not isinstance(e, dict):
            continue
        jour = coerce_jour(e.get("jour"))
        if jour is not None:
            out[jour] = e
    return out


@dataclass
class ResultatDuMois:
    """Jours d'un salarié pour un mois : ceux qui passent, ceux laissés, et ce
    qu'il faut envoyer à l'enregistrement du calendrier."""

    passes: list[date] = field(default_factory=list)
    laisses: list[tuple[date, str]] = field(default_factory=list)
    #: Seulement les jours qui passent : la fusion du prévu garde les autres.
    prevu_a_ecrire: list[dict[str, Any]] = field(default_factory=list)
    #: Le réel du mois entier : l'enregistrement du réel remplace le mois.
    reel_a_ecrire: list[dict[str, Any]] = field(default_factory=list)


def juger_le_mois(
    annee: int,
    mois: int,
    dates: Iterable[date],
    prevu: Iterable[Any],
    reel: Iterable[Any],
    ctx: ContexteSalarie,
) -> ResultatDuMois:
    """Juge les dates du mois `annee/mois` et prépare l'écriture des jours qui passent."""
    prevu_par_jour = _par_jour(prevu)
    reel_par_jour = _par_jour(reel)
    res = ResultatDuMois()
    nouveaux_reels: dict[int, dict[str, Any]] = {}
    for quand in sorted({d for d in dates if d.year == annee and d.month == mois}):
        jour_prevu = prevu_par_jour.get(quand.day)
        raison = raison_de_laisser(quand, jour_prevu, reel_par_jour.get(quand.day), ctx)
        if raison:
            res.laisses.append((quand, raison))
            continue
        res.passes.append(quand)
        entree_prevue, entree_reelle = jour_en_activite_partielle(
            quand.day, jour_prevu, forfait_jours=ctx.forfait_jours
        )
        res.prevu_a_ecrire.append(entree_prevue)
        nouveaux_reels[quand.day] = entree_reelle
    if nouveaux_reels:
        reel_complet = {**reel_par_jour, **nouveaux_reels}
        res.reel_a_ecrire = [reel_complet[j] for j in sorted(reel_complet)]
    return res


def decompte(laisses: Iterable[tuple[date, str]]) -> dict[str, int]:
    """Nombre de jours laissés par raison, dans l'ordre d'affichage."""
    compte = {raison: 0 for raison in LIBELLES_RAISONS}
    for _, raison in laisses:
        compte[raison] = compte.get(raison, 0) + 1
    return {raison: n for raison, n in compte.items() if n}
