"""Activité partielle : l'indemnité d'une heure chômée et les deux lignes du mois.

Règle légale (service-public F23503 et F13898, vérifiées le 13/08/2026 et le
16/10/2026) : l'employeur verse 60 % du salaire brut par heure chômée, sans
descendre sous 9,74 € ni monter au-dessus de 33,24 € par heure. Un accord ou
une décision de l'employeur peut prévoir plus : le taux est un réglage de la
société. L'indemnité ne dépasse jamais le salaire horaire lui-même (un salarié
ne gagne pas plus à être chômé).

Les deux lignes posées dans les variables du mois sont celles que le moteur
paie déjà (payslip_run_heures) : la retenue des heures chômées, avec leur
nombre, et l'indemnité, revenu de remplacement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LIBELLE_RETENUE = "Heures chômées (act. part.)"
LIBELLE_INDEMNITE = "Indemnité activité partielle"
LIBELLES = (LIBELLE_RETENUE, LIBELLE_INDEMNITE)

TAUX_LEGAL = 60.0
PLANCHER_LEGAL = 9.74
PLAFOND_LEGAL = 33.24


@dataclass(frozen=True)
class CalculActivitePartielle:
    heures_chomees: float
    taux_horaire: float
    indemnite_horaire: float
    retenue: float
    indemnite: float
    regle: str


def _r2(x: float) -> float:
    return round(x + 1e-9, 2)


def taux_horaire_du_contrat(
    salaire_de_base: Any, duree_hebdomadaire: Any
) -> float | None:
    """Salaire mensuel ÷ heures mensuelles du contrat (durée hebdo × 52 ÷ 12)."""
    valeur = (
        salaire_de_base.get("valeur")
        if isinstance(salaire_de_base, dict)
        else salaire_de_base
    )
    try:
        mensuel = float(valeur)
        hebdo = float(duree_hebdomadaire or 35)
    except (TypeError, ValueError):
        return None
    if mensuel <= 0 or hebdo <= 0:
        return None
    return round(mensuel / (hebdo * 52 / 12), 4)


def taux_horaire_forfait_jours(
    salaire_de_base: Any, jours_forfait: float | None
) -> float | None:
    """Forfait annuel en jours : la journée vaut le salaire mensuel ÷ (22 × jours ÷ 218),
    l'heure la journée ÷ 7 (fiche « forfaits jours » du ministère du Travail, 11/2024 :
    3 500 € pour 218 jours = 22,73 € de l'heure ; 2 000 € pour 109 jours = 25,97 €).
    """
    valeur = (
        salaire_de_base.get("valeur")
        if isinstance(salaire_de_base, dict)
        else salaire_de_base
    )
    try:
        mensuel = float(valeur)
    except (TypeError, ValueError):
        return None
    jours = float(jours_forfait or 218)
    if mensuel <= 0 or jours <= 0:
        return None
    return round(mensuel / (22 * jours / 218) / 7, 4)


def calculer(
    heures_chomees: float,
    taux_horaire: float,
    *,
    taux_indemnite: float = TAUX_LEGAL,
    plancher: float = PLANCHER_LEGAL,
    plafond: float = PLAFOND_LEGAL,
    heures_du_mois: float | None = None,
    salaire_du_mois: float | None = None,
) -> CalculActivitePartielle:
    """`heures_du_mois` : plafond des heures chômées d'un mois (R5122-19 : un
    mois entier vaut la durée mensuelle du contrat) ; atteint, la retenue est
    le salaire du mois, sans les centimes d'arrondi du taux horaire."""
    heures = round(max(0.0, float(heures_chomees)), 2)
    mois_entier = bool(heures_du_mois) and heures >= float(heures_du_mois)
    if mois_entier:
        heures = round(float(heures_du_mois), 2)
    horaire = float(taux_horaire)
    brute = horaire * float(taux_indemnite) / 100
    regle = f"{float(taux_indemnite):g} % du salaire horaire"
    indemnite_horaire = brute
    if indemnite_horaire < plancher:
        indemnite_horaire = plancher
        regle = f"plancher de {plancher:.2f} € par heure".replace(".", ",")
    if indemnite_horaire > plafond:
        indemnite_horaire = plafond
        regle = f"plafond de {plafond:.2f} € par heure".replace(".", ",")
    if indemnite_horaire > horaire:
        indemnite_horaire = horaire
        regle = "salaire horaire (l'indemnité ne le dépasse pas)"
    indemnite_horaire = round(indemnite_horaire, 4)
    return CalculActivitePartielle(
        heures_chomees=heures,
        taux_horaire=round(horaire, 4),
        indemnite_horaire=indemnite_horaire,
        retenue=_r2(float(salaire_du_mois))
        if mois_entier and salaire_du_mois
        else _r2(heures * horaire),
        indemnite=_r2(heures * indemnite_horaire),
        regle=regle,
    )


def refus_periode(reglage: dict[str, Any], annee: int, mois: int) -> str | None:
    """Le mois doit tomber dans la période d'activité partielle de la société."""
    if not reglage.get("active"):
        return "L'activité partielle n'est pas activée pour cette société (Paramètres, Paie)."
    premier = f"{annee:04d}-{mois:02d}-01"
    dernier = f"{annee:04d}-{mois:02d}-31"
    debut = str(reglage.get("date_debut") or "")[:10]
    fin = str(reglage.get("date_fin") or "")[:10]
    if debut and dernier < debut:
        return f"Ce mois est avant le début de l'activité partielle ({debut[8:10]}/{debut[5:7]}/{debut[:4]})."
    if fin and premier > fin:
        return f"Ce mois est après la fin de l'activité partielle ({fin[8:10]}/{fin[5:7]}/{fin[:4]})."
    return None
