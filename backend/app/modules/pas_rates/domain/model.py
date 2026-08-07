"""Taux de prélèvement à la source : vocabulaire et règles de statut.

Le taux appliqué sur un bulletin n'est pas une décision de l'employeur : la DGFiP
le renvoie dans le compte rendu métier qui suit le dépôt d'une DSN. Tant qu'elle
n'a rien renvoyé — un nouvel embauché, typiquement — le déclarant applique la
grille par défaut.

La rubrique DSN S21.G00.50.007 porte un type de taux. Le 01 est le taux
personnalisé transmis par la DGFiP ; le 13 et ses variantes territoriales sont
le barème par défaut, recalculé chaque mois sur la rémunération du mois. La
nomenclature et la conséquence sur le calcul sont dans `app.shared.pas_taux`.

Un salarié au barème n'est donc pas « en attente d'un taux périmé » : son taux
est juste le résultat d'une grille, que le moteur recalcule à chaque paie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from app.shared import pas_taux

# S21.G00.50.007 — type du taux de prélèvement à la source. La nomenclature
# complète et la règle de calcul vivent dans `app.shared.pas_taux`, partagées
# avec le moteur de paie ; on n'en réexporte ici que ce que l'écran manipule.
TYPE_PERSONNALISE = pas_taux.TYPE_PERSONNALISE
TYPE_BAREME = pas_taux.TYPE_BAREME_METROPOLE

TYPE_LABELS: Dict[str, str] = dict(pas_taux.LIBELLES)

# Statuts affichés aux RH.
STATUT_A_JOUR = "a_jour"
STATUT_BAREME = "bareme"
STATUT_A_RAFRAICHIR = "a_rafraichir"
STATUT_MANQUANT = "manquant"

STATUT_LABELS: Dict[str, str] = {
    STATUT_A_JOUR: "À jour",
    STATUT_BAREME: "Barème par défaut",
    STATUT_A_RAFRAICHIR: "À rafraîchir",
    STATUT_MANQUANT: "Manquant",
}

# Au-delà, le taux en base a de bonnes chances d'avoir été remplacé par la DGFiP :
# la DSN d'un mois est déposée le mois suivant, un taux de deux mois est donc le
# plus récent qu'on puisse détenir en régime normal.
ANCIENNETE_TOLEREE_MOIS = 2

_PERIODE_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def type_label(type_taux: Optional[str]) -> str:
    """Libellé lisible d'un type de taux, y compris pour un code inattendu."""
    return pas_taux.libelle_type(type_taux)


def periode_valide(periode: Optional[str]) -> bool:
    return bool(periode) and bool(_PERIODE_RE.match(periode or ""))


def periode_courante(today: Optional[date] = None) -> str:
    d = today or date.today()
    return f"{d.year:04d}-{d.month:02d}"


def ecart_mois(periode: str, reference: str) -> Optional[int]:
    """Nombre de mois entre une période et une référence, None si illisible."""
    if not periode_valide(periode) or not periode_valide(reference):
        return None
    ay, am = int(periode[:4]), int(periode[5:7])
    by, bm = int(reference[:4]), int(reference[5:7])
    return (by - ay) * 12 + (bm - am)


def calculer_statut(
    taux: Optional[float],
    type_taux: Optional[str],
    periode: Optional[str],
    reference: str,
) -> str:
    """Statut d'un taux, du plus alarmant au plus rassurant.

    L'absence de taux passe avant tout le reste : c'est le seul cas où le bulletin
    prélève 0 % sans que personne l'ait décidé. Le barème vient ensuite : la paie
    est juste — le moteur recalcule la grille chaque mois — mais la DGFiP n'a pas
    encore renvoyé de taux personnalisé, et l'ancienneté du taux stocké n'a alors
    aucun sens à être reprochée aux RH.
    """
    if taux is None:
        return STATUT_MANQUANT
    if pas_taux.est_taux_bareme(type_taux):
        return STATUT_BAREME
    ecart = ecart_mois(periode or "", reference)
    if ecart is None or ecart > ANCIENNETE_TOLEREE_MOIS:
        return STATUT_A_RAFRAICHIR
    return STATUT_A_JOUR


@dataclass
class TauxSalarie:
    """Le taux courant d'un salarié, tel qu'il sera montré aux RH."""

    employee_id: str
    nom: str
    prenom: str
    matricule: str = ""
    company_id: str = ""
    company_name: str = ""
    taux: Optional[float] = None
    type_taux: Optional[str] = None
    identifiant_taux: Optional[str] = None
    periode: Optional[str] = None
    source: Optional[str] = None
    statut: str = STATUT_MANQUANT

    @property
    def type_libelle(self) -> str:
        return type_label(self.type_taux)

    @property
    def statut_libelle(self) -> str:
        return STATUT_LABELS.get(self.statut, self.statut)


@dataclass
class LigneApercu:
    """Une ligne de l'aperçu : ce que le fichier propose, face à ce qu'on a."""

    employee_id: Optional[str]
    nom: str
    prenom: str
    taux_actuel: Optional[float]
    taux_fichier: Optional[float]
    type_actuel: Optional[str]
    type_fichier: Optional[str]
    identifiant_fichier: Optional[str] = None
    # inchange | nouveau | modifie | hors_effectif | non_rapproche
    nature: str = "inchange"

    @property
    def type_fichier_libelle(self) -> str:
        return type_label(self.type_fichier)


@dataclass
class Apercu:
    """Le résultat d'un dépôt de fichier, avant toute écriture."""

    periode: str
    siren: str
    fichier: str
    source: str
    lignes: List[LigneApercu] = field(default_factory=list)
    avertissements: List[str] = field(default_factory=list)

    def a_appliquer(self) -> List[LigneApercu]:
        return [l for l in self.lignes if l.nature in ("nouveau", "modifie")]

    def compteurs(self) -> Dict[str, int]:
        out = {
            "inchange": 0,
            "nouveau": 0,
            "modifie": 0,
            "hors_effectif": 0,
            "non_rapproche": 0,
        }
        for ligne in self.lignes:
            out[ligne.nature] = out.get(ligne.nature, 0) + 1
        return out
