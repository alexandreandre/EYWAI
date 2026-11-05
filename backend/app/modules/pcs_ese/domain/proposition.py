"""Martine trouve le code PCS-ESE d'un salarié.

Dans l'ordre (spécification du 05/11/2026, § 3.2) :
a) les collègues de la société, au même poste et au même statut, qui ont un vrai code ;
b) personne dans la société : les mêmes collègues dans les autres sociétés du groupe ;
c) personne dans le groupe : l'intitulé cherché dans les métiers de l'Insee.

Sûre quand les collègues ont tous le même code (au moins 2 pour un code ECAP, qui baisse la
contribution OETH) et, s'ils sont d'une autre société, que l'Insee confirme : un mot du poste figure
dans la rubrique du code ; ou quand l'intitulé est exactement un métier Insee sans secteur et qu'il
ne reste qu'un code. Sinon, 3 codes probables. Le statut écarte les mauvais codes : « La
qualification de cadre ou d'ingénieur est définie par les conventions collectives » et les non
cadres sont exclus de la catégorie 37 ; « les cadres au sens des conventions collectives » sont
« toujours exclus » de la catégorie 46 (Insee, PCS-ESE 2017, 19/12/2025).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.modules.pcs_ese.domain.normalisation import (
    est_cadre,
    mots_metier,
    normaliser_poste,
    tete,
)
from app.modules.pcs_ese.domain.referentiel import Rubrique, charger_referentiel

#: Un code ECAP n'est posé que si au moins 2 collègues l'ont (décision du 05/11/2026).
SEUIL_ECAP = 2
MAX_CANDIDATS = 3
#: Métiers des employeurs publics : jamais proposés à une société privée.
_PUBLIC = re.compile(r"\b(etat|coll\. ?loc|fonction publique)", re.I)
#: Une parenthèse qui n'est pas une exclusion (« (sauf Etat, …) ») précise un secteur.
_SECTEUR = re.compile(r"\((?!sauf)", re.I)
#: Quadra coupe l'intitulé à 30 caractères : le dernier mot peut être tronqué.
_LONGUEUR_COUPEE = 30
#: Mots qui ne disent pas le métier à eux seuls (« Opérateur (informatique) » n'est pas un
#: opérateur de production) : un métier proche doit partager un autre mot avec l'intitulé.
_GENERIQUES = frozenset(
    "agent operateur responsable technicien chef assistant employe ouvrier aide charge "
    "directeur cadre conducteur preparateur animateur adjoint coordinateur".split()
)


@dataclass(frozen=True)
class FicheCollegue:
    employee_id: str
    company_id: str
    societe: str
    poste: str
    statut: str
    code: str


@dataclass(frozen=True)
class Candidat:
    code: str
    libelle: str
    raison: str
    ecap: bool


@dataclass(frozen=True)
class Proposition:
    code: Optional[str]
    sur: bool
    raison: str
    regle: Optional[str]
    nb_collegues: int
    candidats: Tuple[Candidat, ...]
    ecap: bool


def collegues_de(
    fiches: Iterable[FicheCollegue],
    *,
    company_id: str,
    poste: str,
    statut: str,
    exclure_id: Optional[str] = None,
) -> Tuple[List[FicheCollegue], List[FicheCollegue]]:
    """Les fiches au même poste et au même statut : celles de la société, puis les autres."""
    cle = normaliser_poste(poste)
    if not cle:
        return [], []
    cadre = est_cadre(statut)
    societe: List[FicheCollegue] = []
    groupe: List[FicheCollegue] = []
    for fiche in fiches:
        if exclure_id and fiche.employee_id == exclure_id:
            continue
        if normaliser_poste(fiche.poste) != cle or est_cadre(fiche.statut) != cadre:
            continue
        (societe if fiche.company_id == company_id else groupe).append(fiche)
    return societe, groupe


def proposer(
    *,
    poste: str,
    statut: str,
    collegues_societe: Sequence[FicheCollegue],
    collegues_groupe: Sequence[FicheCollegue],
    referentiel: Optional[Dict[str, Rubrique]] = None,
) -> Proposition:
    ref = referentiel or charger_referentiel()
    cadre = est_cadre(statut)

    def vrais(fiches: Sequence[FicheCollegue]) -> List[FicheCollegue]:
        return [f for f in fiches if f.code in ref and f.code != "9999"]

    for regle, fiches in (("a", vrais(collegues_societe)), ("b", vrais(collegues_groupe))):
        # Un code de cadre (groupe 3) ne vaut pas pour un non-cadre, ni l'inverse (R3) : il
        # ne se propose pas, mais à côté d'un bon code il compte comme un désaccord.
        bons = [f for f in fiches if _compatible(f.code, cadre)]
        if not bons:
            continue
        if regle == "a":
            ou = f"de {bons[0].societe}"
        else:
            ou = "du groupe (" + ", ".join(sorted({f.societe for f in bons})) + ")"
        return _par_collegues(bons, regle, ou, poste, cadre, ref, desaccord=len(bons) < len(fiches))
    return _par_metiers(poste, cadre, ref)


def _compatible(code: str, cadre: bool) -> bool:
    return code[0] not in "456" if cadre else code[0] != "3"


def _completer(candidats: List[Candidat], autres: Iterable[Candidat]) -> Tuple[Candidat, ...]:
    vus = {c.code for c in candidats}
    for c in autres:
        if len(candidats) >= MAX_CANDIDATS:
            break
        if c.code not in vus:
            candidats.append(c)
            vus.add(c.code)
    return tuple(candidats[:MAX_CANDIDATS])


def _par_collegues(
    fiches: List[FicheCollegue],
    regle: str,
    ou: str,
    poste: str,
    cadre: bool,
    ref: Dict[str, Rubrique],
    desaccord: bool = False,
) -> Proposition:
    compte = Counter(f.code for f in fiches)
    n = len(fiches)
    if len(compte) == 1 and not desaccord:
        code = fiches[0].code
        rubrique = ref[code]
        if n == 1:
            raison = f"Même poste et même statut qu'1 collègue {ou}, en {code}."
        else:
            raison = f"Même poste et même statut que {n} collègues {ou}, tous en {code}."
        if rubrique.ecap and n < SEUIL_ECAP:
            candidat = Candidat(
                code,
                rubrique.libelle,
                raison + " Code ECAP : il réduit la contribution OETH ; Martine ne le pose "
                "pas sur l'avis d'un seul collègue.",
                True,
            )
            return Proposition(
                code=None,
                sur=False,
                raison="Code ECAP trouvé chez un seul collègue : à confirmer.",
                regle=regle,
                nb_collegues=n,
                candidats=_completer([candidat], _candidats_metiers(poste, cadre, ref)),
                ecap=True,
            )
        if regle == "b" and not _insee_confirme(poste, rubrique):
            # Le 05/11/2026, un collègue d'une autre société a donné « Soudeurs manuels » à des
            # opérateurs de pliage et « méthodes » à des responsables qualité.
            insee = _par_metiers(poste, cadre, ref)
            if insee.sur:
                return insee
            return Proposition(
                code=None,
                sur=False,
                raison=f"{raison} L'Insee ne range pas ce poste dans ce code : à confirmer.",
                regle=regle,
                nb_collegues=n,
                candidats=_completer(
                    [Candidat(code, rubrique.libelle, raison, rubrique.ecap)],
                    _candidats_metiers(poste, cadre, ref),
                ),
                ecap=rubrique.ecap,
            )
        return Proposition(
            code=code,
            sur=True,
            raison=raison,
            regle=regle,
            nb_collegues=n,
            candidats=(Candidat(code, rubrique.libelle, raison, rubrique.ecap),),
            ecap=rubrique.ecap,
        )
    candidats = [
        Candidat(
            code,
            ref[code].libelle,
            f"{k} collègue{'s' if k > 1 else ''} sur {n} {ou}, au même poste, en {code}.",
            ref[code].ecap,
        )
        for code, k in compte.most_common()
    ]
    return Proposition(
        code=None,
        sur=False,
        raison=f"Les collègues {ou} au même poste n'ont pas tous le même code.",
        regle=regle,
        nb_collegues=n,
        candidats=_completer(candidats[:MAX_CANDIDATS], _candidats_metiers(poste, cadre, ref)),
        ecap=False,
    )


# --- c) métiers Insee ------------------------------------------------------------------


@dataclass(frozen=True)
class _Metier:
    code: str
    metier: str
    #: 0 profession typique, 1 assimilée, 2 exclue (son code « voir »).
    rang: int
    mots: Tuple[str, ...]
    secteur: bool
    #: Tous les mots du métier, précisions comprises : départagent les métiers proches.
    mots_complets: Tuple[str, ...] = ()


_INDEX: Dict[int, List[_Metier]] = {}


def _proposable(code: str, ref: Dict[str, Rubrique]) -> bool:
    rubrique = ref.get(code)
    return bool(rubrique) and code != "9999" and rubrique.groupe in "3456" and not rubrique.public


def _index(ref: Dict[str, Rubrique]) -> List[_Metier]:
    if id(ref) not in _INDEX:
        metiers: List[_Metier] = []

        def ajouter(code: str, metier: str, rang: int) -> None:
            if not _proposable(code, ref):
                return
            if _PUBLIC.search(metier) and "sauf" not in metier.lower():
                return
            mots = tuple(mots_metier(tete(metier)))
            if mots:
                metiers.append(
                    _Metier(
                        code,
                        metier,
                        rang,
                        mots,
                        bool(_SECTEUR.search(metier)),
                        tuple(mots_metier(metier)),
                    )
                )

        for code, rubrique in ref.items():
            for metier in rubrique.typiques:
                ajouter(code, metier, 0)
            for metier in rubrique.assimilees:
                ajouter(code, metier, 1)
            for exclusion in rubrique.exclues:
                for voir in exclusion.voir:
                    ajouter(voir, exclusion.libelle, 2)
        _INDEX[id(ref)] = metiers
    return _INDEX[id(ref)]


def _meme_mot(titre: str, metier: str, prefixe: bool) -> bool:
    return titre == metier or (prefixe and len(titre) >= 3 and metier.startswith(titre))


def _meme_racine(a: str, b: str) -> bool:
    """« industriel » et « industrie » : les six premières lettres suffisent."""
    return a == b or (len(a) >= 6 and len(b) >= 6 and a[:6] == b[:6])


def _bonus(titre: List[str], m: _Metier) -> int:
    return sum(1 for t in titre if any(_meme_racine(t, x) for x in m.mots_complets))


def _chercher(
    poste: str, cadre: bool, ref: Dict[str, Rubrique]
) -> Tuple[List[_Metier], List[_Metier]]:
    """Les métiers égaux à l'intitulé, puis les métiers proches, du plus proche au moins proche."""
    titre = mots_metier(poste)
    if not titre:
        return [], []
    coupe = len(str(poste or "").strip()) >= _LONGUEUR_COUPEE
    dernier = len(titre) - 1
    groupes = "3" if cadre else "456"
    exacts: List[_Metier] = []
    proches: List[Tuple[int, _Metier]] = []
    for m in _index(ref):
        if m.code[0] not in groupes:
            continue
        if len(m.mots) == len(titre) and all(
            _meme_mot(titre[i], m.mots[i], coupe and i == dernier) for i in range(len(titre))
        ):
            exacts.append(m)
            continue
        dans_titre = [
            any(_meme_mot(t, w, coupe and i == dernier) for i, t in enumerate(titre)) for w in m.mots
        ]
        titre_dedans = [
            any(_meme_mot(t, w, coupe and i == dernier) for w in m.mots) for i, t in enumerate(titre)
        ]
        if not (all(dans_titre) or all(titre_dedans)):
            continue
        communs = [t for t, ok in zip(titre, titre_dedans) if ok]
        # Un métier plus long que l'intitulé n'a qu'un mot de plus : « Agent de maîtrise de
        # production » reste proche d'« agent de production », « Agent de production
        # informatique de la Poste » ne l'est plus.
        if not all(dans_titre) and len(m.mots) - len(communs) > 1:
            continue
        if len(communs) >= 2 or (len(communs) == 1 and communs[0] not in _GENERIQUES):
            proches.append((len(communs), m))
    exacts.sort(key=lambda m: (-_bonus(titre, m), m.secteur, m.rang))
    proches.sort(key=lambda p: (-p[0], -_bonus(titre, p[1]), p[1].secteur, p[1].rang))
    return exacts, [m for _, m in proches]


def _insee_confirme(poste: str, rubrique: Rubrique) -> bool:
    """Un mot du poste, hors mots génériques, figure dans l'intitulé de la rubrique ou ses métiers."""
    mots = [m for m in mots_metier(poste) if m not in _GENERIQUES]
    connus = {
        w for texte in (rubrique.libelle, *rubrique.typiques, *rubrique.assimilees)
        for w in mots_metier(texte)
    }
    return any(_meme_racine(m, w) for m in mots for w in connus)


def _candidat(m: _Metier, ref: Dict[str, Rubrique], proche: bool) -> Candidat:
    debut = "Métier Insee proche" if proche else "Métier Insee"
    return Candidat(m.code, ref[m.code].libelle, f"{debut} : « {m.metier} ».", ref[m.code].ecap)


def _candidats_metiers(poste: str, cadre: bool, ref: Dict[str, Rubrique]) -> List[Candidat]:
    exacts, proches = _chercher(poste, cadre, ref)
    return [_candidat(m, ref, False) for m in exacts] + [_candidat(m, ref, True) for m in proches]


def _precision_lisible(metier: str) -> bool:
    """Après la virgule, l'Insee précise le niveau (« ouvrier qualifié », « employé »…), que
    l'intitulé du poste ne dit pas ; seul « cadre » ou « non cadre » se lit dans le statut."""
    if "," not in metier:
        return True
    return metier.split(",", 1)[1].strip().lower() in ("cadre", "non cadre")


def _par_metiers(poste: str, cadre: bool, ref: Dict[str, Rubrique]) -> Proposition:
    exacts, proches = _chercher(poste, cadre, ref)
    codes_exacts = {m.code for m in exacts}
    # Sûre seulement pour un métier exact, sans secteur ni niveau à deviner, à un seul code,
    # hors apprenti (l'Insee le range à part) et hors code ECAP (il baisse la contribution
    # OETH : jamais posé sans collègues).
    if (
        len(codes_exacts) == 1
        and "apprenti" not in mots_metier(poste)
        and not any(m.secteur or not _precision_lisible(m.metier) for m in exacts)
        and not ref[exacts[0].code].ecap
    ):
        m = exacts[0]
        raison = f"Métier Insee : « {m.metier} » (rubrique {m.code})."
        rubrique = ref[m.code]
        return Proposition(
            code=m.code,
            sur=True,
            raison=raison,
            regle="c",
            nb_collegues=0,
            candidats=(Candidat(m.code, rubrique.libelle, raison, rubrique.ecap),),
            ecap=rubrique.ecap,
        )
    candidats = _completer(
        [], [_candidat(m, ref, False) for m in exacts] + [_candidat(m, ref, True) for m in proches]
    )
    if not candidats:
        return Proposition(
            code=None,
            sur=False,
            raison="Aucun collègue au même poste, aucun métier Insee proche : choisissez le "
            "code dans la liste.",
            regle=None,
            nb_collegues=0,
            candidats=(),
            ecap=False,
        )
    return Proposition(
        code=None,
        sur=False,
        raison="Aucun collègue au même poste : codes proches d'après les métiers de l'Insee.",
        regle="c",
        nb_collegues=0,
        candidats=candidats,
        ecap=False,
    )
