"""Plan conventionnel des jours d'arrêt : quel jour est maintenu, à quel taux.

Pur, sans base. Les arrêts connus du salarié (lus aux calendriers, de l'année
d'avant jusqu'au mois du bulletin) sont rejoués dans l'ordre, avec le barème de
la société (conception du 24/10/2026) :

- un arrêt est une chaîne de demandes de même nature séparées de 2 jours de
  reprise au plus (`prolongation_arret`) : une prolongation n'est jamais un
  nouvel arrêt ;
- l'ancienneté se lit en mois complets au début de l'arrêt ;
- carence (non-cadres, maladie hors ALD) : 3 jours calendaires, levée pour le
  premier arrêt de l'année civile qui ouvre droit ; si celui-ci a duré moins de
  3 jours, la carence du suivant vaut sa durée ;
- chaque jour indemnisé prend un rang dans l'arrêt ; le rang fixe le palier
  (lecture A : les paliers repartent à chaque arrêt) ;
- un jour n'est indemnisé que si l'arrêt et l'année civile du jour comptent
  moins de jours indemnisés que la limite de la tranche.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Optional

from app.modules.payroll.domain.baremes_maintien import (
    FAMILLE_MALADIE,
    FAMILLE_PARENTALITE,
    Bareme,
    Categorie,
    Tranche,
    famille_du_type,
    mois_complets,
    tranche_pour,
)

from .prolongation_arret import ECART_MAX_PROLONGATION_JOURS, famille_d_arret

#: Pourquoi un arrêt a (ou n'a pas) de carence.
RAISON_CADRE = "cadre"
RAISON_ACCIDENT = "accident"
RAISON_ALD = "ald"
RAISON_PREMIER_ARRET = "premier_arret"
RAISON_RELIQUAT = "reliquat"
RAISON_CARENCE = "carence"


@dataclass(frozen=True)
class ArretDuPlan:
    debut: date
    fin: date
    type_arret: str


@dataclass
class ArretRejoue:
    debut: date
    fin: date
    type_arret: str
    famille: str
    mois_anciennete: int
    tranche: Optional[Tranche]
    carence_jours: int = 0
    raison_carence: str = RAISON_CARENCE
    jours_de_carence: tuple[date, ...] = ()
    #: (premier jour, taux) de chaque palier atteint, dans l'ordre.
    bascules: list[tuple[date, float]] = field(default_factory=list)
    #: Dernier jour indemnisé quand la limite (de l'arrêt ou de l'année) coupe
    #: le maintien alors que l'arrêt continue.
    limite_atteinte: Optional[date] = None
    jours: tuple[date, ...] = ()

    def contient(self, jour: date) -> bool:
        return self.debut <= jour <= self.fin


@dataclass
class PlanConventionnel:
    taux_par_jour: dict[date, float]
    arrets: list[ArretRejoue]

    def arret_du_jour(self, jour: date) -> Optional[ArretRejoue]:
        for arret in self.arrets:
            if arret.contient(jour):
                return arret
        return None


def _date(valeur: Any) -> Optional[date]:
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def _jours(debut: date, fin: date) -> Iterable[date]:
    jour = debut
    while jour <= fin:
        yield jour
        jour += timedelta(days=1)


def arrets_pour_le_plan(
    arrets_connus: Iterable[Mapping[str, Any]] | None,
    debut: date,
    fin: date,
    type_arret: str,
) -> list[ArretDuPlan]:
    """Les arrêts connus, et l'arrêt calculé s'il n'y est pas encore."""
    arrets: list[ArretDuPlan] = []
    for autre in arrets_connus or []:
        d = _date((autre or {}).get("debut"))
        f = _date((autre or {}).get("fin")) or d
        if d is None or f is None:
            continue
        arrets.append(ArretDuPlan(d, f, str(autre.get("type") or "maladie_simple")))
    if not any(a.debut <= fin and debut <= a.fin for a in arrets):
        arrets.append(ArretDuPlan(debut, fin, type_arret))
    return arrets


def _chaines(arrets: Iterable[ArretDuPlan]) -> list[list[ArretDuPlan]]:
    tries = sorted(
        {a for a in arrets if a.fin >= a.debut and famille_du_type(a.type_arret) != FAMILLE_PARENTALITE},
        key=lambda a: (a.debut, a.fin),
    )
    chaines: list[list[ArretDuPlan]] = []
    for arret in tries:
        if chaines:
            derniere = chaines[-1]
            fin = max(a.fin for a in derniere)
            if (
                famille_d_arret(derniere[0].type_arret) == famille_d_arret(arret.type_arret)
                and (arret.debut - fin).days <= ECART_MAX_PROLONGATION_JOURS
            ):
                derniere.append(arret)
                continue
        chaines.append([arret])
    return chaines


def _carence(
    categorie: Categorie,
    famille: str,
    type_arret: str,
    annee: int,
    duree: int,
    premiers: set[int],
    reliquats: dict[int, int],
) -> tuple[int, str]:
    if categorie.carence_jours <= 0:
        return 0, RAISON_CADRE
    if famille != FAMILLE_MALADIE:
        return 0, RAISON_ACCIDENT
    if str(type_arret or "").strip().lower() == "ald":
        return 0, RAISON_ALD
    if annee not in premiers:
        premiers.add(annee)
        if duree < categorie.carence_jours:
            reliquats[annee] = duree
        return 0, RAISON_PREMIER_ARRET
    if annee in reliquats:
        return reliquats.pop(annee), RAISON_RELIQUAT
    return categorie.carence_jours, RAISON_CARENCE


def plan_conventionnel(
    arrets: Iterable[ArretDuPlan],
    *,
    bareme: Bareme,
    est_cadre: bool,
    date_anciennete: Optional[date],
) -> PlanConventionnel:
    """Rejoue les arrêts : le taux de chaque jour indemnisé, et chaque arrêt."""
    categorie = bareme.categorie(est_cadre)
    taux_par_jour: dict[date, float] = {}
    rejoues: list[ArretRejoue] = []
    premiers: set[int] = set()
    reliquats: dict[int, int] = {}
    indemnises_par_an: dict[int, int] = {}
    dernier_par_an: dict[int, date] = {}
    for chaine in _chaines(arrets):
        debut = chaine[0].debut
        type_arret = chaine[0].type_arret
        famille = famille_du_type(type_arret)
        mois = mois_complets(date_anciennete, debut) if date_anciennete else 0
        jours = tuple(sorted({j for a in chaine for j in _jours(a.debut, a.fin)}))
        tranche = tranche_pour(bareme, est_cadre=est_cadre, mois_anciennete=mois, famille=famille)
        rejoue = ArretRejoue(
            debut=debut, fin=jours[-1], type_arret=type_arret, famille=famille,
            mois_anciennete=mois, tranche=tranche, jours=jours,
        )
        rejoues.append(rejoue)
        if tranche is None:
            continue
        carence, raison = _carence(
            categorie, famille, type_arret, debut.year, len(jours), premiers, reliquats
        )
        rejoue.carence_jours = carence
        rejoue.raison_carence = raison
        rejoue.jours_de_carence = jours[:carence]
        rang = 0
        taux_precedent: Optional[float] = None
        refus: Optional[date] = None
        for jour in jours[carence:]:
            if rang >= tranche.limite or indemnises_par_an.get(jour.year, 0) >= tranche.limite:
                refus = refus or jour
                if rang >= tranche.limite:
                    break
                continue
            rang += 1
            indemnises_par_an[jour.year] = indemnises_par_an.get(jour.year, 0) + 1
            dernier_par_an[jour.year] = jour
            taux = tranche.taux_du_rang(rang)
            taux_par_jour[jour] = taux
            if taux != taux_precedent:
                rejoue.bascules.append((jour, taux))
                taux_precedent = taux
        if refus is not None:
            avant = [j for j in jours if j < refus and j in taux_par_jour]
            rejoue.limite_atteinte = avant[-1] if avant else dernier_par_an.get(refus.year)
    return PlanConventionnel(taux_par_jour=taux_par_jour, arrets=rejoues)


__all__ = [
    "ArretDuPlan",
    "ArretRejoue",
    "PlanConventionnel",
    "RAISON_ACCIDENT",
    "RAISON_ALD",
    "RAISON_CADRE",
    "RAISON_CARENCE",
    "RAISON_PREMIER_ARRET",
    "RAISON_RELIQUAT",
    "arrets_pour_le_plan",
    "plan_conventionnel",
]
