"""Tableau des charges, au format de celui de Quadra.

Une ligne par cotisation et par taux (base, taux et montant : total, salarial, patronal),
un sous-total par caisse, l'impôt à la source par taux sous « DGFIP », le total général
et l'effectif payé (femmes, hommes). Demande d'Elsa du 03/11/2026 : l'export doit
ressembler, voire être identique, au « Tableau des charges » de Quadra.

Un bulletin copié de Quadra n'a pas toujours ses taux : le taux se retrouve alors sur
la ligne (montant / base). Deux lignes au même libellé mais à des taux différents
(maladie à 7 % et complément à 6 %) restent deux lignes, comme chez Quadra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.modules.exports.domain.accounting_plan import (
    ORGANISME_IJSS,
    ORGANISME_INCONNU,
    ORGANISME_MUTUELLE,
    ORGANISME_PREVOYANCE,
    ORGANISME_RETRAITE,
    ORGANISME_RETRAITE_SUP,
    ORGANISME_URSSAF,
    ORGANISMES,
    resolve_organisme_from_coti_id,
)

ORGANISME_DGFIP = "DGFIP"
LIBELLE_DGFIP = "DGFIP — prélèvement à la source"
#: L'ordre des caisses du tableau de Quadra ; une caisse absente n'a pas de section.
ORDRE_DES_CAISSES = (
    ORGANISME_URSSAF,
    ORGANISME_RETRAITE,
    ORGANISME_DGFIP,
    ORGANISME_MUTUELLE,
    ORGANISME_PREVOYANCE,
    ORGANISME_RETRAITE_SUP,
    ORGANISME_IJSS,
    ORGANISME_INCONNU,
)


@dataclass
class LigneDeCharge:
    code: str
    libelle: str
    base: float = 0.0
    montant_salarial: float = 0.0
    montant_patronal: float = 0.0
    taux_salarial: Optional[float] = None
    taux_patronal: Optional[float] = None

    @property
    def montant_total(self) -> float:
        return round(self.montant_salarial + self.montant_patronal, 2)

    @property
    def taux_total(self) -> Optional[float]:
        if self.taux_salarial is None and self.taux_patronal is None:
            return None
        return round((self.taux_salarial or 0.0) + (self.taux_patronal or 0.0), 4)


@dataclass
class SectionDeCaisse:
    organisme: str
    libelle: str
    lignes: List[LigneDeCharge] = field(default_factory=list)

    @property
    def salarial(self) -> float:
        return round(sum(l.montant_salarial for l in self.lignes), 2)

    @property
    def patronal(self) -> float:
        return round(sum(l.montant_patronal for l in self.lignes), 2)

    @property
    def total(self) -> float:
        return round(self.salarial + self.patronal, 2)


@dataclass
class TableauDesCharges:
    sections: List[SectionDeCaisse]
    payes: int
    femmes: int
    hommes: int

    @property
    def salarial(self) -> float:
        return round(sum(s.salarial for s in self.sections), 2)

    @property
    def patronal(self) -> float:
        return round(sum(s.patronal for s in self.sections), 2)

    @property
    def total(self) -> float:
        return round(self.salarial + self.patronal, 2)


def _nombre(valeur: Any) -> float:
    try:
        return float(valeur or 0.0)
    except (TypeError, ValueError):
        return 0.0


#: Réductions : Quadra imprime la base en positif et le taux à −100 %.
REDUCTIONS = frozenset({"reduction_generale", "reduction_generale_retraite"})
#: Lignes sans taux : forfait (mutuelle) ou base en heures (déduction patronale, 1,50 €/h).
SANS_TAUX = frozenset({"mutuelle", "deduction_hs_patronale"})


def _taux_imprime(valeur: Any, *, en_fraction: bool = True) -> Optional[float]:
    """Un taux du bulletin, en pourcentage. Les cotisations le rangent en fraction
    (0,0315 pour 3,15 %) ; l'impôt à la source, déjà en pourcentage (4,5)."""
    if valeur is None or valeur == "":
        return None
    try:
        taux = float(valeur)
    except (TypeError, ValueError):
        return None
    return round(taux * 100.0 if en_fraction else taux, 4)


def _taux_retrouve(montant: float, base: float) -> Optional[float]:
    if not montant or not base:
        return None
    return montant / base * 100.0


def _taux_affiche(montant: float, base: float, nb_lignes: int) -> Optional[float]:
    """Le taux retrouvé d'une ligne agrégée : à 2 décimales s'il redonne le montant à un
    demi-centime près par bulletin (6 % et non 5,9999 %), sinon à 4 (0,016 %)."""
    retrouve = _taux_retrouve(montant, base)
    if retrouve is None:
        return None
    court = round(retrouve, 2)
    if abs(court * base / 100.0 - montant) <= 0.005 * max(nb_lignes, 1) + 1e-9:
        return court
    return round(retrouve, 4)


def _cle_de_taux(imprime: Optional[float], montant: float, base: float) -> Optional[float]:
    """Le taux qui distingue deux lignes : imprimé, sinon retrouvé (arrondi à 2 décimales,
    pour absorber l'arrondi au centime de chaque bulletin)."""
    if imprime is not None:
        return imprime
    retrouve = _taux_retrouve(montant, base)
    return None if retrouve is None else round(retrouve, 2)


def construire_tableau(bulletins: Iterable[Dict[str, Any]]) -> TableauDesCharges:
    """`bulletins` : {employee_id, cotisations_detail, pas: {base, taux, montant}, sexe}."""
    lignes: Dict[Tuple[Any, ...], LigneDeCharge] = {}
    imprimes: Dict[Tuple[Any, ...], Tuple[bool, bool]] = {}
    nombres: Dict[Tuple[Any, ...], int] = {}
    sexes: Dict[str, Optional[str]] = {}

    for bulletin in bulletins:
        sexes[str(bulletin.get("employee_id"))] = bulletin.get("sexe")
        for coti in bulletin.get("cotisations_detail") or []:
            if not isinstance(coti, dict):
                continue
            sal, pat = _nombre(coti.get("montant_salarial")), _nombre(coti.get("montant_patronal"))
            if not sal and not pat:
                continue
            coti_id = str(coti.get("coti_id") or "")
            base = _nombre(coti.get("base"))
            if coti_id in REDUCTIONS:
                # La base de la ligne ventilée est son montant (la base imprimée est
                # celle de la réduction entière, en négatif sur un bulletin repris).
                base = -(sal + pat)
            libelle = str(coti.get("libelle") or "Cotisation")
            organisme = resolve_organisme_from_coti_id(coti.get("coti_id"), libelle)
            ts, tp = _taux_imprime(coti.get("taux_salarial")), _taux_imprime(coti.get("taux_patronal"))
            if coti_id in SANS_TAUX or coti_id in REDUCTIONS:
                # Forfait, base en heures ou réduction (dont le « taux » imprimé est le
                # coefficient du salarié) : une seule ligne ; la réduction se relit à −100 %.
                ts = tp = None
                cle = (organisme, coti_id, libelle, None, None)
            elif ts is not None or tp is not None:
                # Un taux imprimé distingue seul la ligne : l'autre part, retrouvée,
                # porte l'arrondi au centime de chaque bulletin.
                cle = (organisme, coti_id, libelle, ts, tp)
            else:
                cle = (organisme, coti_id, libelle, _cle_de_taux(ts, sal, base), _cle_de_taux(tp, pat, base))
            ligne = lignes.setdefault(cle, LigneDeCharge(code=str(coti.get("code") or ""), libelle=libelle))
            nombres[cle] = nombres.get(cle, 0) + 1
            ligne.base += base
            ligne.montant_salarial += sal
            ligne.montant_patronal += pat
            if ts is not None:
                ligne.taux_salarial = ts
            if tp is not None:
                ligne.taux_patronal = tp
            deja = imprimes.get(cle, (False, False))
            imprimes[cle] = (deja[0] or ts is not None, deja[1] or tp is not None)

        pas = bulletin.get("pas") or {}
        montant_pas = _nombre(pas.get("montant"))
        if montant_pas:
            taux = _taux_imprime(pas.get("taux"), en_fraction=False)
            cle = (ORGANISME_DGFIP, "pas", "Prélèvement à la source", taux, None)
            ligne = lignes.setdefault(cle, LigneDeCharge(code="", libelle="Prélèvement à la source", taux_salarial=taux))
            ligne.base += _nombre(pas.get("base"))
            ligne.montant_salarial += montant_pas
            imprimes[cle] = (True, False)

    sections: Dict[str, SectionDeCaisse] = {}
    for cle, ligne in lignes.items():
        organisme = cle[0]
        ligne.base = round(ligne.base, 2)
        ligne.montant_salarial = round(ligne.montant_salarial, 2)
        ligne.montant_patronal = round(ligne.montant_patronal, 2)
        sal_imprime, pat_imprime = imprimes.get(cle, (False, False))
        sans_taux = cle[1] in SANS_TAUX
        if not sal_imprime:
            ligne.taux_salarial = None if sans_taux else _taux_affiche(ligne.montant_salarial, ligne.base, nombres.get(cle, 1))
        if not pat_imprime:
            ligne.taux_patronal = None if sans_taux else _taux_affiche(ligne.montant_patronal, ligne.base, nombres.get(cle, 1))
        libelle = LIBELLE_DGFIP if organisme == ORGANISME_DGFIP else ORGANISMES.get(organisme, organisme)
        sections.setdefault(organisme, SectionDeCaisse(organisme=organisme, libelle=libelle)).lignes.append(ligne)

    rang = {o: i for i, o in enumerate(ORDRE_DES_CAISSES)}
    ordonnees = sorted(sections.values(), key=lambda s: (rang.get(s.organisme, len(rang)), s.organisme))
    for section in ordonnees:
        if section.organisme == ORGANISME_DGFIP:
            section.lignes.sort(key=lambda l: l.taux_salarial or 0.0)
    valeurs = [str(s or "").upper()[:1] for s in sexes.values()]
    return TableauDesCharges(sections=ordonnees, payes=len(sexes),
                             femmes=valeurs.count("F"), hommes=valeurs.count("M"))
