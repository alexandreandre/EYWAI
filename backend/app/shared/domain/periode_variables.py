"""
La fenêtre des variables d'un bulletin — heures supplémentaires et paniers.

Le bulletin porte le mois civil. Les variables, elles, sont comptées sur des
semaines complètes décalées : la gestionnaire de paie arrête les compteurs
quand elle boucle la paie, et le mois suivant reprend au lundi qui suit. La
règle société (`paie_jour_de_fin` / `paie_occurrence`) fournit la proposition ;
une surcharge mensuelle peut la corriger, jamais rompre la continuité.

Module PUR : aucune I/O, aucune dépendance au moteur. L'appelant fournit les
bornes déjà calculées par la règle.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

#: Origine d'une fenêtre : issue de la règle société, ou corrigée à la main.
ORIGINE_REGLE = "regle"
ORIGINE_MANUEL = "manuel"


@dataclass(frozen=True)
class FenetreVariables:
    """Bornes incluses de la fenêtre, et d'où elles viennent."""

    debut: date
    fin: date
    origine: str


def normaliser_fin_semaine(jour: date) -> date:
    """Dimanche de la semaine qui contient `jour`.

    Une semaine entamée est comptée en entier : la gestionnaire arrête au
    samedi, la semaine va jusqu'au dimanche. C'est la règle du moteur
    (`period_forfait.bornes_periode_de_paie`), reprise ici à l'identique pour
    qu'une saisie manuelle ne puisse pas créer un demi-week-end orphelin.
    """
    return jour + timedelta(days=6 - jour.weekday())


def bornes_mois_civil(annee: int, mois: int) -> tuple[date, date]:
    """Premier et dernier jour du mois."""
    dernier = calendar.monthrange(annee, mois)[1]
    return date(annee, mois, 1), date(annee, mois, dernier)


def semaines_iso(debut: date, fin: date) -> list[int]:
    """Numéros de semaine ISO couverts par la fenêtre, dans l'ordre."""
    numeros: list[int] = []
    jour = debut
    while jour <= fin:
        semaine = jour.isocalendar()[1]
        if semaine not in numeros:
            numeros.append(semaine)
        jour += timedelta(days=7)
    return numeros


def resoudre_fenetre(
    bornes_regle: tuple[date, date],
    fin_mois_precedent: date | None,
    surcharge: date | None,
) -> FenetreVariables:
    """Fenêtre effective d'un mois.

    `bornes_regle` : ce que la règle société produit pour ce mois.
    `fin_mois_precedent` : la fin réellement retenue le mois d'avant (surcharge
    comprise) ; c'est elle qui fixe le début, pas la règle.
    `surcharge` : la date d'arrêt choisie à la main, ou None.
    """
    debut_regle, fin_regle = bornes_regle
    debut = (
        fin_mois_precedent + timedelta(days=1)
        if fin_mois_precedent is not None
        else debut_regle
    )
    fin = normaliser_fin_semaine(surcharge) if surcharge is not None else fin_regle
    if fin < debut:
        raise ValueError(
            f"Fin de fenêtre ({fin:%d/%m/%Y}) antérieure à son début "
            f"({debut:%d/%m/%Y}) : la paie du mois précédent est allée plus loin."
        )
    return FenetreVariables(
        debut=debut,
        fin=fin,
        origine=ORIGINE_MANUEL if surcharge is not None else ORIGINE_REGLE,
    )


__all__ = [
    "FenetreVariables",
    "ORIGINE_MANUEL",
    "ORIGINE_REGLE",
    "bornes_mois_civil",
    "normaliser_fin_semaine",
    "resoudre_fenetre",
    "semaines_iso",
]
