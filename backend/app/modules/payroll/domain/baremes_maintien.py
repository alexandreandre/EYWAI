"""Barèmes conventionnels du maintien de salaire : les paliers en données.

Un barème a deux catégories, non-cadres et cadres. Chaque catégorie a ses
tranches d'ancienneté (« à partir de N mois complets ») ; chaque tranche, ses
paliers (taux, jours calendaires). La limite d'une tranche est la somme de ses
paliers : elle vaut par arrêt et par année civile.

Plasturgie (IDCC 0292), textes ouverts sur Légifrance le 24/10/2026 :
- non-cadres : avenant du 15/05/1991, art. 13 ;
- cadres : accord du 17/12/1992, art. 5.
Conception : docs/superpowers/specs/2026-10-24-maintien-paliers-convention-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Optional

CODE_PLASTURGIE = "plasturgie_0292"
CODE_METALLURGIE = "metallurgie_3248"
CLE_BAREME = "bareme_convention"

#: Ce que le barème garantit (`engine/garantie_nette.py`) :
#: - brute : le brut, IJ brutes déduites ;
#: - nette : le net, IJ nettes ramenées au brut (plasturgie) ;
#: - plafond_net : le brut, borné au net qu'aurait perçu le salarié (métallurgie,
#:   art. 91.1.3 : « une indemnisation plus importante que la rémunération nette »).
GARANTIE_BRUTE = "brute"
GARANTIE_NETTE = "nette"
GARANTIE_PLAFOND_NET = "plafond_net"

FAMILLE_MALADIE = "maladie"
FAMILLE_ACCIDENT_TRAVAIL = "accident_travail"  # accident du travail, maladie professionnelle, rechute
FAMILLE_TRAJET = "trajet"
FAMILLE_PARENTALITE = "parentalite"

_TYPES_ACCIDENT_TRAVAIL = frozenset({"accident_travail", "maladie_professionnelle", "rechute_at"})


@dataclass(frozen=True)
class Palier:
    taux: float
    jours: int


@dataclass(frozen=True)
class Tranche:
    des_mois: int
    paliers: tuple[Palier, ...]

    @property
    def limite(self) -> int:
        return sum(p.jours for p in self.paliers)

    def taux_du_rang(self, rang: int) -> float:
        """Le taux du rang-ième jour indemnisé de l'arrêt (1 = le premier)."""
        cumul = 0
        for palier in self.paliers:
            cumul += palier.jours
            if 1 <= rang <= cumul:
                return palier.taux
        return 0.0


@dataclass(frozen=True)
class Categorie:
    titre: str
    tranches: tuple[Tranche, ...]
    carence_jours: int
    #: Accident du travail (hors trajet) et maladie professionnelle : au moins
    #: la tranche de cette ancienneté (cadres : 2 ans).
    minimum_accident_travail_mois: int
    notes: tuple[str, ...]


@dataclass(frozen=True)
class Source:
    titre: str
    url: str


@dataclass(frozen=True)
class Bareme:
    code: str
    libelle: str
    nom_court: str
    #: Ancienneté qui ouvre le droit en maladie (accident : sans condition).
    anciennete_requise_mois: int
    non_cadres: Categorie
    cadres: Categorie
    sources: tuple[Source, ...]
    regles: tuple[str, ...]
    garantie: str = GARANTIE_BRUTE
    #: Ancienneté qui ouvre le droit en accident du travail ou maladie
    #: professionnelle (plasturgie : aucune ; métallurgie : 3 mois).
    anciennete_requise_at_mp_mois: int = 0
    #: True : un accident de trajet demande l'ancienneté de la maladie
    #: (métallurgie) ; False : aucune condition (plasturgie).
    trajet_requiert_anciennete: bool = False
    #: True : l'ancienneté se relit chaque jour de l'arrêt, et le rang d'un jour
    #: (qui fixe son taux) est le plus grand des jours déjà indemnisés pour cet
    #: arrêt et dans l'année civile (métallurgie, art. 91.1.3). False : le rang
    #: repart à chaque arrêt, l'année n'étant qu'un plafond (plasturgie).
    anciennete_et_paliers_par_annee: bool = False

    def categorie(self, est_cadre: bool) -> Categorie:
        return self.cadres if est_cadre else self.non_cadres


def _paliers(*couples: tuple[float, int]) -> tuple[Palier, ...]:
    return tuple(Palier(taux, jours) for taux, jours in couples)


PLASTURGIE = Bareme(
    code=CODE_PLASTURGIE,
    libelle="Plasturgie (IDCC 0292)",
    nom_court="Plasturgie",
    anciennete_requise_mois=12,
    non_cadres=Categorie(
        titre="Non-cadres",
        tranches=(
            Tranche(12, _paliers((1.0, 45), (0.75, 60))),
            Tranche(60, _paliers((1.0, 60), (0.75, 75))),
        ),
        carence_jours=3,
        minimum_accident_travail_mois=0,
        notes=(
            "Carence de 3 jours par arrêt de maladie ; aucune pour le premier arrêt "
            "de l'année civile (s'il a duré moins de 3 jours, la carence du suivant "
            "est égale à sa durée) ; aucune en accident du travail, maladie "
            "professionnelle, accident de trajet ou affection de longue durée.",
            "Accident du travail, maladie professionnelle ou accident de trajet : "
            "sans condition d'ancienneté.",
        ),
    ),
    cadres=Categorie(
        titre="Cadres",
        tranches=(
            Tranche(12, _paliers((1.0, 45), (0.5, 45))),
            Tranche(24, _paliers((1.0, 60), (0.5, 60))),
            Tranche(36, _paliers((1.0, 90), (0.5, 90))),
            Tranche(60, _paliers((1.0, 120), (0.5, 120))),
            Tranche(120, _paliers((1.0, 150), (0.5, 150))),
        ),
        carence_jours=0,
        minimum_accident_travail_mois=24,
        notes=(
            "Pas de carence.",
            "Accident du travail ou maladie professionnelle : sans condition "
            "d'ancienneté, au moins la ligne « 2 ans à moins de 3 ans » ; accident "
            "de trajet : sans condition d'ancienneté.",
        ),
    ),
    sources=(
        Source(
            "Avenant du 15/05/1991, article 13 (non-cadres)",
            "https://www.legifrance.gouv.fr/conv_coll/id/KALIARTI000005856705?idConteneur=KALICONT000005635856",
        ),
        Source(
            "Accord du 17/12/1992, article 5 (cadres)",
            "https://www.legifrance.gouv.fr/conv_coll/id/KALIARTI000005856723?idConteneur=KALICONT000005635856",
        ),
    ),
    regles=(
        "Jours calendaires ; l'ancienneté se lit au début de l'arrêt.",
        "La limite vaut par arrêt et par année civile ; les paliers repartent à "
        "chaque nouvel arrêt.",
        "Les IJSS des jours maintenus sont déduites selon le réglage « Arrêt sans "
        "subrogation » ; avec subrogation, toujours.",
        (
            "Le maintien garantit le net (art. 13 e ; accord Cadres, art. 5) : les IJSS "
            "déduites sont comptées nettes de CSG et CRDS, puis ramenées au brut avec le "
            "taux de cotisations salariales du salarié."
        ),
        (
            "Chaque mois, Martine compare avec le maintien légal, calculé sur le brut, et "
            "verse le plus favorable."
        ),
    ),
    garantie=GARANTIE_NETTE,
)

def _tranches_metallurgie(cadre: bool) -> tuple[Tranche, ...]:
    """Groupes A-E (100 %) ou F-I (100 % puis autant à 50 %), art. 91.1.2."""
    durees = ((12, 90), (60, 120), (120, 150), (180, 180))
    return tuple(
        Tranche(des, _paliers((1.0, j), (0.5, j)) if cadre else _paliers((1.0, j)))
        for des, j in durees
    )


_NOTES_METALLURGIE = (
    "Pas de carence.",
    "Accident du travail ou maladie professionnelle survenu dans l'entreprise : "
    "au moins trois mois d'ancienneté, indemnisé dès le premier jour d'absence.",
    "L'ancienneté se lit chaque jour : un changement de tranche en cours d'arrêt "
    "ouvre aussitôt le crédit de la nouvelle tranche (art. 91.1.1).",
)

METALLURGIE = Bareme(
    code=CODE_METALLURGIE,
    libelle="Métallurgie (IDCC 3248)",
    nom_court="Métallurgie",
    anciennete_requise_mois=12,
    non_cadres=Categorie(
        titre="Non-cadres",
        tranches=_tranches_metallurgie(cadre=False),
        carence_jours=0,
        minimum_accident_travail_mois=0,
        notes=_NOTES_METALLURGIE,
    ),
    cadres=Categorie(
        titre="Cadres",
        tranches=_tranches_metallurgie(cadre=True),
        carence_jours=0,
        minimum_accident_travail_mois=0,
        notes=_NOTES_METALLURGIE,
    ),
    sources=(
        Source(
            "Art. 91.1.1 à 91.1.3 de la convention du 7 février 2022",
            "https://www.legifrance.gouv.fr/conv_coll/id/KALIARTI000050144115?idConteneur=KALICONT000046993250",
        ),
    ),
    regles=(
        "Groupes d'emplois A à E : non-cadres ; F à I : cadres. Jours calendaires ; "
        "100 % du 1er jour entièrement non travaillé (art. 91.1.2).",
        "Un an d'ancienneté en maladie ou accident de trajet ; trois mois en accident "
        "du travail ou maladie professionnelle, indemnisé dès le premier jour.",
        "L'ancienneté se lit chaque jour ; les durées d'indemnisation se comptent sur "
        "l'année civile, plusieurs arrêts compris (art. 91.1.3).",
        "Les IJSS des jours maintenus sont déduites selon le réglage « Arrêt sans "
        "subrogation » ; avec subrogation, toujours.",
        "Le maintien est plafonné au net : il ne peut dépasser la rémunération nette "
        "qu'aurait perçue le salarié (art. 91.1.3).",
        "Chaque mois, Martine compare avec le maintien légal et verse le plus favorable.",
    ),
    garantie=GARANTIE_PLAFOND_NET,
    anciennete_requise_at_mp_mois=3,
    trajet_requiert_anciennete=True,
    anciennete_et_paliers_par_annee=True,
)

BAREMES: dict[str, Bareme] = {PLASTURGIE.code: PLASTURGIE, METALLURGIE.code: METALLURGIE}


def bareme_par_code(code: Any) -> Optional[Bareme]:
    return BAREMES.get(str(code)) if code else None


def bareme_des_reglages(settings: Mapping[str, Any]) -> Optional[Bareme]:
    """Le barème choisi par la société ; None sans barème (le calcul d'avant)."""
    return bareme_par_code(settings.get(CLE_BAREME)) if isinstance(settings, Mapping) else None


def famille_du_type(arret_type: Any) -> str:
    t = str(arret_type or "").strip().lower()
    if t in _TYPES_ACCIDENT_TRAVAIL:
        return FAMILLE_ACCIDENT_TRAVAIL
    if t == "accident_trajet":
        return FAMILLE_TRAJET
    if "matern" in t or "patern" in t or "adoption" in t or "naissance" in t:
        return FAMILLE_PARENTALITE
    return FAMILLE_MALADIE


def mois_complets(debut: date, jour: date) -> int:
    """Mois d'ancienneté révolus au `jour` (l'anniversaire du mois compte)."""
    mois = (jour.year - debut.year) * 12 + (jour.month - debut.month)
    if jour.day < debut.day:
        mois -= 1
    return max(0, mois)


def tranche_pour(
    bareme: Bareme, *, est_cadre: bool, mois_anciennete: int, famille: str
) -> Optional[Tranche]:
    """La tranche d'un arrêt, ou None s'il n'ouvre aucun droit."""
    if famille == FAMILLE_PARENTALITE:
        return None
    categorie = bareme.categorie(est_cadre)
    mois = mois_anciennete
    if famille == FAMILLE_ACCIDENT_TRAVAIL:
        if mois < bareme.anciennete_requise_at_mp_mois:
            return None
        mois = max(mois, categorie.minimum_accident_travail_mois)
    elif famille == FAMILLE_TRAJET:
        if bareme.trajet_requiert_anciennete and mois < bareme.anciennete_requise_mois:
            return None
    elif famille == FAMILLE_MALADIE and mois < bareme.anciennete_requise_mois:
        return None
    applicable = categorie.tranches[0]
    for tranche in categorie.tranches:
        if mois >= tranche.des_mois:
            applicable = tranche
    return applicable


def pourcent(taux: float) -> str:
    valeur = round(float(taux) * 100, 2)
    if float(valeur).is_integer():
        return f"{int(valeur)} %"
    return f"{valeur:.2f}".replace(".", ",") + " %"


def _ans(mois: int) -> str:
    ans = mois // 12
    return "1 an" if ans == 1 else f"{ans} ans"


def libelle_tranche(categorie: Categorie, tranche: Tranche) -> str:
    """« 1 an à moins de 5 ans », « 5 ans et plus »."""
    suivantes = [t.des_mois for t in categorie.tranches if t.des_mois > tranche.des_mois]
    if not suivantes:
        return f"{_ans(tranche.des_mois)} et plus"
    return f"{_ans(tranche.des_mois)} à moins de {_ans(min(suivantes))}"


def texte_paliers(tranche: Tranche) -> str:
    """« 45 jours à 100 %, puis 60 jours à 75 % »."""
    return ", puis ".join(f"{p.jours} jours à {pourcent(p.taux)}" for p in tranche.paliers)


def description_lisible(bareme: Bareme) -> dict[str, Any]:
    """Le barème tel que l'écran le montre : la même source que le moteur."""
    categories = []
    for categorie in (bareme.non_cadres, bareme.cadres):
        categories.append(
            {
                "titre": categorie.titre,
                "lignes": [
                    {
                        "anciennete": libelle_tranche(categorie, tranche),
                        "paliers": texte_paliers(tranche),
                        "limite": f"{tranche.limite} jours",
                    }
                    for tranche in categorie.tranches
                ],
                "notes": list(categorie.notes),
            }
        )
    return {
        "code": bareme.code,
        "libelle": bareme.libelle,
        "sources": [{"titre": s.titre, "url": s.url} for s in bareme.sources],
        "categories": categories,
        "regles": list(bareme.regles),
    }


__all__ = [
    "BAREMES",
    "CLE_BAREME",
    "CODE_METALLURGIE",
    "CODE_PLASTURGIE",
    "FAMILLE_ACCIDENT_TRAVAIL",
    "FAMILLE_MALADIE",
    "FAMILLE_PARENTALITE",
    "FAMILLE_TRAJET",
    "GARANTIE_BRUTE",
    "GARANTIE_NETTE",
    "GARANTIE_PLAFOND_NET",
    "METALLURGIE",
    "PLASTURGIE",
    "Bareme",
    "Categorie",
    "Palier",
    "Source",
    "Tranche",
    "bareme_des_reglages",
    "bareme_par_code",
    "description_lisible",
    "famille_du_type",
    "libelle_tranche",
    "mois_complets",
    "pourcent",
    "texte_paliers",
    "tranche_pour",
]
