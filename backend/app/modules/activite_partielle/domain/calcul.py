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
    #: Heures ramenées au maximum de la période (R5122-19).
    plafonne: bool = False


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


def heures_retenues(
    heures_chomees: float,
    *,
    heures_max: float | None = None,
    heures_si_tout_chome: float | None = None,
    tout_chome: bool = False,
    sans_travail: bool = False,
    **_autres: Any,
) -> float:
    """Les heures chômées que le bulletin paie, bornes de la période comprises
    (voir `calculer`) ; l'écran et la DSN comptent les mêmes."""
    heures = round(max(0.0, float(heures_chomees)), 2)
    if (tout_chome or sans_travail) and heures_si_tout_chome is not None:
        return round(max(0.0, float(heures_si_tout_chome)), 2)
    if heures_max is not None and heures > round(float(heures_max), 2):
        return round(max(0.0, float(heures_max)), 2)
    return heures


def _retenue(brute: float, salaire: float | None, tout_chome: bool) -> float:
    if salaire and salaire > 0:
        if tout_chome:
            return _r2(salaire)
        return _r2(min(brute, salaire))
    return _r2(brute)


def calculer(
    heures_chomees: float,
    taux_horaire: float,
    *,
    taux_indemnite: float = TAUX_LEGAL,
    plancher: float = PLANCHER_LEGAL,
    plafond: float = PLAFOND_LEGAL,
    heures_max: float | None = None,
    heures_si_tout_chome: float | None = None,
    salaire: float | None = None,
    tout_chome: bool = False,
    sans_travail: bool = False,
) -> CalculActivitePartielle:
    """Bornes de la période (R5122-19), toutes facultatives :
    - `heures_max` : heures chômées au plus (durée de référence moins les
      heures non chômées) ;
    - `tout_chome` : rien d'autre n'est dû sur la période ; les heures valent
      alors `heures_si_tout_chome` (la durée d'un mois civil entier), s'il est
      donné, et la retenue vaut le salaire ;
    - `sans_travail` : aucune heure travaillée, mais des jours payés (férié,
      congé) ; les heures valent `heures_si_tout_chome` (la durée du mois
      moins ces jours) et la retenue reste bornée au salaire ;
    - `salaire` : la retenue ne le dépasse jamais (salarié mensualisé sous
      contrat toute la période : le bulletin ne paie pas plus que lui).
    """
    heures = heures_retenues(
        heures_chomees,
        heures_max=heures_max,
        heures_si_tout_chome=heures_si_tout_chome,
        tout_chome=tout_chome,
        sans_travail=sans_travail,
    )
    plafonne = not (tout_chome or sans_travail) and heures < round(max(0.0, float(heures_chomees)), 2)
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
        retenue=_retenue(heures * horaire, salaire, tout_chome),
        indemnite=_r2(heures * indemnite_horaire),
        regle=regle,
        plafonne=plafonne,
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
