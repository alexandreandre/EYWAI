"""Salaire minimum hiérarchique de la métallurgie, comparé sur l'année (art. 138 à 140).

CCN du 07/02/2022 (IDCC 3248). Le minimum est annuel : l'assiette reprend les sommes
brutes soumises à cotisations, moins les éléments que l'article 140 exclut. Il se réduit
au prorata des suspensions, s'adapte à l'horaire et se majore de 30 % au forfait jours
(art. 139).

Contrôle prudent, pour signaler et non pour calculer :
- un mois suspendu (activité partielle, arrêt, congé sans solde) ou de sortie n'est pas
  comparé, plutôt que de reconstituer un prorata : seul le 13e mois ou un bonus y compte ;
- les heures supplémentaires et leurs majorations sortent des deux côtés ;
- le groupe F (classes 11 et 12) a un barème débutant selon l'expérience, que la fiche
  ne porte pas : pas de contrôle ; le forfait en heures non plus (aucune donnée).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.collective_agreements.domain.classification import (
    normalize_classification_for_payroll,
)
from app.modules.collective_agreements.rules.seeds.metallurgie_3248 import SMH_ANNUEL_PAR_ANNEE

_EXCLUS_ART_140 = (
    "anciennet",
    "astreinte",
    "exceptionnel",
    "equipe",
    "penib",
    "insalubr",
    "dangereu",
    "invention",
    "interessement",
    "participation",
    "abondement",
    "nuit",
    "majo",
    "heures suppl",
    "heures compl",
    "hs structurelles",
)
_SUSPENSIONS = ("act. partiel", "activite partielle", "abs.", "maladie", "maternit", "paternit", "tps.part", "ijss")
_ANNUELS = re.compile(r"13\s*(e|eme|ieme)\s*mois|bonus|prime annuelle|vacances")
_ALTERNANCE = ("apprent", "profession")
_MAJORATION_FORFAIT_JOURS = 1.30
_JOURS_FORFAIT_COMPLET = 218.0
_TOLERANCE = 1.0


@dataclass(frozen=True)
class EcartSmh:
    classe: int
    mois_compares: int
    assiette: float
    minimum: float

    @property
    def manque(self) -> float:
        return round(self.minimum - self.assiette, 2)


def _texte(libelle: Any) -> str:
    decompose = unicodedata.normalize("NFKD", str(libelle or "").lower())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _montant(ligne: Mapping[str, Any]) -> float:
    def lu(cle: str) -> float:
        try:
            return float(ligne.get(cle) or 0)
        except (TypeError, ValueError):
            return 0.0

    return lu("gain") - lu("perte")


def _suspendu(libelle: str) -> bool:
    if "absence" in libelle and "conges payes" not in libelle:
        return True
    return any(mot in libelle for mot in _SUSPENSIONS)


def classe_controlable(classification: Any, type_contrat: Any) -> int | None:
    """La classe d'emploi à contrôler, ou None si ce salarié n'entre pas dans le contrôle."""
    if not isinstance(classification, Mapping):
        return None
    if str(classification.get("idcc") or "").strip().lstrip("0") != "3248":
        return None
    if any(mot in _texte(type_contrat) for mot in _ALTERNANCE):
        return None
    lue = normalize_classification_for_payroll(dict(classification)).get("classe_emploi")
    try:
        classe = int(lue)
    except (TypeError, ValueError):
        return None
    return None if classe in (11, 12) else classe


def _facteur(duree_hebdo: float | None, forfait_jours: bool, jours_forfait: float | None) -> float:
    if forfait_jours:
        reduction = (
            jours_forfait / _JOURS_FORFAIT_COMPLET
            if jours_forfait and jours_forfait < _JOURS_FORFAIT_COMPLET
            else 1.0
        )
        return _MAJORATION_FORFAIT_JOURS * reduction
    if duree_hebdo and 0 < duree_hebdo < 35:
        return duree_hebdo / 35.0
    return 1.0


def mois_pleins(
    bulletins: Iterable[Mapping[str, Any]], annee: int, debut: Any, fin: Any
) -> list[dict[str, Any]]:
    """Les bulletins d'après le mois d'entrée et d'avant le mois de fin de contrat.

    L'entrée en cours de mois ne porte pas de ligne d'absence chez l'ancien logiciel :
    seul le salaire de base est réduit, ce que le contrôle prendrait pour un manque.
    """

    def rang(valeur: Any) -> tuple[int, int] | None:
        match = re.match(r"(\d{4})-(\d{2})", str(valeur or ""))
        return (int(match.group(1)), int(match.group(2))) if match else None

    entree, sortie = rang(debut), rang(fin)
    gardes = []
    for bulletin in bulletins:
        ici = (annee, int(bulletin.get("month") or 0))
        if (entree and ici <= entree) or (sortie and ici >= sortie):
            continue
        gardes.append(dict(bulletin))
    return gardes


def bareme_smh_manque(annee: int) -> bool:
    """L'année est postérieure au dernier barème SMH chargé (pas de contrôle possible)."""
    return annee > max(SMH_ANNUEL_PAR_ANNEE)


def message_smh_absent(annee: int) -> str:
    return (
        f"Barème des salaires minima hiérarchiques {annee} de la métallurgie non chargé : "
        "le minimum annuel n'est pas contrôlé. À signaler au support."
    )


def ecart_smh(
    bulletins: Iterable[Mapping[str, Any]],
    *,
    classe: int,
    annee: int,
    duree_hebdo: float | None = None,
    forfait_jours: bool = False,
    jours_forfait: float | None = None,
) -> EcartSmh | None:
    """Ce qui manque au minimum sur les mois comparables, ou None s'il est atteint."""
    annuel = SMH_ANNUEL_PAR_ANNEE.get(annee, {}).get(classe)
    if annuel is None:
        return None
    assiette = 0.0
    mois = 0
    for bulletin in bulletins:
        lignes = [l for l in bulletin.get("calcul_du_brut") or [] if isinstance(l, Mapping)]
        libelles = [(_texte(l.get("libelle")), _montant(l)) for l in lignes]
        if bulletin.get("is_bulletin_sortie") or any(_suspendu(t) for t, _ in libelles):
            assiette += sum(m for t, m in libelles if _ANNUELS.search(t))
            continue
        try:
            brut = float(bulletin.get("salaire_brut") or 0)
        except (TypeError, ValueError):
            continue
        assiette += brut - sum(m for t, m in libelles if any(x in t for x in _EXCLUS_ART_140))
        mois += 1
    if mois == 0:
        return None
    minimum = annuel / 12 * mois * _facteur(duree_hebdo, forfait_jours, jours_forfait)
    if minimum - assiette <= _TOLERANCE:
        return None
    return EcartSmh(classe=classe, mois_compares=mois, assiette=round(assiette, 2), minimum=round(minimum, 2))


def message_smh(ecart: EcartSmh, annee: int) -> str:
    def euros(valeur: float) -> str:
        return f"{valeur:,.2f}".replace(",", " ").replace(".", ",")

    return (
        f"Minimum de la métallurgie (classe {ecart.classe}, barème {annee}) : "
        f"{euros(ecart.assiette)} € retenus sur {ecart.mois_compares} mois comparés pour "
        f"{euros(ecart.minimum)} € attendus, il manque {euros(ecart.manque)} €. Le minimum "
        "est annuel : les primes de fin d'année comptent, à vérifier à la clôture de décembre."
    )
