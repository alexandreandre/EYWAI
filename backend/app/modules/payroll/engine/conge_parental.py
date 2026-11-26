"""Retenue du congé parental d'éducation : une ligne par période, pas par jour.

Le congé parental d'éducation à temps plein suspend le contrat sans salaire
(C. trav. L1225-47 ; service-public.fr F2280 : « le salarié n'est pas rémunéré
par son employeur »). Il se retient exactement comme un congé sans solde : même
journée, même taux, même arrondi au jour. Seul le libellé change, et les jours
d'un même congé se regroupent sur une ligne « Absence congé parental du … au … »
bornée au mois, comme le cabinet déclare la suspension (DSN 65 de l'ancien
logiciel : une période par mois, du premier au dernier jour du mois couvert).

Le montant d'une ligne est la somme des retenues du jour déjà arrondies : le
bulletin d'un congé parental est, au centime, celui d'un congé sans solde.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Mapping, Optional

from app.shared.domain.conge_parental import (
    MOTIF_DSN_CONGE_PARENTAL,
    bornes_du_jour,
    est_jour_de_conge_parental,
)

PREFIXE_LIBELLE = "Absence congé parental"

#: Clé de la ligne qui porte la suspension à déclarer en DSN (motif, bornes).
CLE_SUSPENSION_DSN = "suspension_dsn"


@dataclass
class _Periode:
    bornes: Optional[tuple[date, date]]
    jours: List[date] = field(default_factory=list)
    quantite: float = 0.0
    perte: float = 0.0
    taux: Optional[float] = None


@dataclass
class RetenuesDuCongeParental:
    """Les jours de congé parental retenus pendant le calcul, puis leurs lignes."""

    periodes: Dict[tuple, _Periode] = field(default_factory=dict)

    def retient(self, evenement: Mapping[str, Any]) -> bool:
        """Vrai si ce jour d'absence non rémunérée va sur une ligne de période.

        Une régularisation d'un mois antérieur aussi : sur sa propre ligne,
        datée de son mois (elle ne se mêle pas aux jours du mois courant)."""
        return est_jour_de_conge_parental(evenement)

    def ajouter(
        self, evenement: Mapping[str, Any], *, quantite: float, taux: float, perte: float
    ) -> None:
        jour = date.fromisoformat(str(evenement["date_complete"])[:10])
        bornes = bornes_du_jour(evenement)
        cle = (bornes, jour.year, jour.month, bool(evenement.get("is_regularisation_anterieure")))
        periode = self.periodes.setdefault(cle, _Periode(bornes=bornes))
        periode.jours.append(jour)
        periode.quantite += float(quantite)
        periode.perte += float(perte)
        if periode.taux is None:
            periode.taux = taux

    def lignes(
        self,
        debut_periode: date,
        fin_periode: date,
        *,
        suffixe: Callable[[float], str] | None = None,
    ) -> List[Dict[str, Any]]:
        """Une ligne par congé et par mois, bornée au mois et à la période de paie."""
        lignes: List[Dict[str, Any]] = []
        for periode in sorted(self.periodes.values(), key=lambda p: min(p.jours)):
            premier, dernier = min(periode.jours), max(periode.jours)
            debut, fin = libelle_bornes(periode.bornes, premier, dernier, debut_periode, fin_periode)
            quantite = round(periode.quantite, 2)
            libelle = libelle_conge_parental(debut, fin)
            if suffixe is not None:
                libelle = f"{libelle} ({suffixe(quantite)})"
            ligne: Dict[str, Any] = {
                "libelle": libelle,
                "quantite": quantite,
                "taux": round(float(periode.taux or 0.0), 4),
                "gain": None,
                "perte": round(periode.perte, 2),
            }
            if periode.bornes is not None:
                # La DSN déclare la suspension entière (cahier technique 2026,
                # S21.G00.65.002 « premier jour de la suspension », 65.003
                # « date de fin prévisionnelle »), pas la part du mois.
                ligne[CLE_SUSPENSION_DSN] = {
                    "motif": MOTIF_DSN_CONGE_PARENTAL,
                    "debut": periode.bornes[0].isoformat(),
                    "fin": periode.bornes[1].isoformat(),
                }
            lignes.append(ligne)
        return lignes


def libelle_bornes(
    bornes: Optional[tuple[date, date]],
    premier: date,
    dernier: date,
    debut_periode: date,
    fin_periode: date,
) -> tuple[date, date]:
    """Les dates de la ligne : le congé, borné au mois du jour et à la période
    de paie ; jamais plus court que les jours retenus."""
    debut_mois = premier.replace(day=1)
    fin_mois = premier.replace(day=calendar.monthrange(premier.year, premier.month)[1])
    if bornes is None:
        return premier, dernier
    debut = max(bornes[0], debut_mois, debut_periode)
    fin = min(bornes[1], fin_mois, fin_periode)
    return min(debut, premier), max(fin, dernier)


def libelle_conge_parental(debut: date, fin: date) -> str:
    if debut == fin:
        return f"{PREFIXE_LIBELLE} du {debut:%d/%m/%y}"
    return f"{PREFIXE_LIBELLE} du {debut:%d/%m/%y} au {fin:%d/%m/%y}"
