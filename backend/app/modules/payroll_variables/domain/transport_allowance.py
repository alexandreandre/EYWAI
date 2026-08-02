"""Indemnité trajet domicile-travail — calcul mensuel (domaine pur).

Le montant est contractuel (avenant signé) et stable d'un mois sur l'autre. Il
est retiré si le salarié est absent sur tout le mois, et proratisé à l'entrée
comme à la sortie.

La base de prorata reprend celle du moteur de paie
(app/modules/payroll/engine/calcul_brut.py::_facteur_prorata_entree_sortie) :
jours ouvrés sous contrat rapportés aux jours ouvrés du mois. Ne pas en inventer
une autre — le moteur en a déjà une et elle fait autorité.
"""

from __future__ import annotations

from datetime import date, timedelta


def jours_ouvres(debut: date, fin: date) -> int:
    """Nombre de jours du lundi au vendredi entre deux dates incluses."""
    if fin < debut:
        return 0
    return sum(
        1
        for offset in range((fin - debut).days + 1)
        if (debut + timedelta(days=offset)).weekday() < 5
    )


def est_absent_tout_le_mois(
    jours_absence: set[date],
    debut_mois: date,
    fin_mois: date,
) -> bool:
    """True si tous les jours ouvrés du mois sont couverts par une absence."""
    ouvres = [
        debut_mois + timedelta(days=offset)
        for offset in range((fin_mois - debut_mois).days + 1)
        if (debut_mois + timedelta(days=offset)).weekday() < 5
    ]
    if not ouvres:
        return False
    return all(jour in jours_absence for jour in ouvres)


def montant_transport_mensuel(
    montant_contractuel: float,
    *,
    debut_mois: date,
    fin_mois: date,
    date_entree: date | None = None,
    date_sortie: date | None = None,
    date_effet: date | None = None,
    absent_tout_le_mois: bool = False,
) -> float:
    """Montant à verser pour le mois, arrondi au centime.

    Renvoie 0 si le montant contractuel est nul, si le salarié est absent sur
    tout le mois, ou si le droit ne couvre aucun jour ouvré du mois.
    """
    if montant_contractuel <= 0 or absent_tout_le_mois:
        return 0.0

    debuts = [d for d in (date_entree, date_effet) if d is not None]
    debut_droit = max([debut_mois, *debuts])
    fin_droit = min(fin_mois, date_sortie) if date_sortie else fin_mois

    total_mois = jours_ouvres(debut_mois, fin_mois)
    if total_mois <= 0:
        return 0.0

    jours_droit = jours_ouvres(debut_droit, fin_droit)
    if jours_droit <= 0:
        return 0.0
    if jours_droit >= total_mois:
        return round(montant_contractuel, 2)
    return round(montant_contractuel * jours_droit / total_mois, 2)
