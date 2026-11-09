"""Congés d'un salarié qui reprend après un arrêt : ce que la loi demande.

Code du travail, ouvert le 09/11/2026 sur code.travail.gouv.fr :
- L3141-19-3 : « au terme d'une période d'arrêt de travail pour cause de maladie
  ou d'accident », l'employeur porte à la connaissance du salarié, « dans le mois
  qui suit la reprise du travail », le nombre de jours dont il dispose et la date
  jusqu'à laquelle ils peuvent être pris, « notamment au moyen du bulletin de paie ».
- L3141-19-1 : report de quinze mois, à compter de la réception de ces informations.
- L3141-19-2 : arrêt d'au moins un an à la fin de la période de référence, le
  report part de la fin de cette période.

Martine ne fait pas expirer ces jours : le compteur reste ouvert, rien ne se perd
en silence. Elle signale la reprise, pour que l'information soit donnée. Le seuil
de 30 jours est un choix : sous ce seuil, le salarié a pu poser ses congés.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, Optional

CODE_ALERTE_REPORT_CONGES = "conges_a_informer_apres_arret"
DUREE_MINIMALE_JOURS = 30

#: Maladie ou accident (L3141-19-1). Pas le mi-temps thérapeutique : le salarié
#: travaille, son contrat n'est pas suspendu ; pas la maternité.
TYPES_CONCERNES = frozenset(
    {
        "maladie_simple",
        "ald",
        "arret_exceptionnel",
        "accident_travail",
        "accident_trajet",
        "rechute_at",
        "maladie_professionnelle",
    }
)


def _date(valeur: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def _jours_fr(valeur: float) -> str:
    texte = f"{valeur:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{texte} jour{'s' if valeur >= 2 else ''}"


def alerte_report_conges_apres_arret(
    arret: Optional[Dict[str, Any]],
    solde_conges: Optional[Dict[str, Any]],
    annee: int,
    mois: int,
) -> Optional[Dict[str, Any]]:
    """L'alerte du bulletin du mois où un arrêt long se termine, s'il reste des congés."""
    if not isinstance(arret, dict) or not isinstance(solde_conges, dict):
        return None
    compteur = solde_conges.get("conges_payes")
    solde = float(compteur.get("solde") or 0.0) if isinstance(compteur, dict) else 0.0
    if solde <= 0:
        return None
    debut_mois = date(annee, mois, 1)
    fin_mois = date(annee, mois, calendar.monthrange(annee, mois)[1])
    arrets = arret.get("arrets_du_mois")
    candidats = [a for a in arrets if isinstance(a, dict)] if isinstance(arrets, list) else [arret]
    for candidat in sorted(candidats, key=lambda a: str(a.get("date_fin") or ""), reverse=True):
        if str(candidat.get("arret_type") or "") not in TYPES_CONCERNES:
            continue
        debut = _date(candidat.get("date_debut"))
        fin = _date(candidat.get("date_fin"))
        if debut is None or fin is None or not debut_mois <= fin <= fin_mois:
            continue
        if (fin - debut).days + 1 < DUREE_MINIMALE_JOURS:
            continue
        return {
            "code": CODE_ALERTE_REPORT_CONGES,
            "severity": "warning",
            "critique": False,
            "message": (
                f"Reprise après un arrêt finissant le {fin.strftime('%d/%m/%Y')} : il reste "
                f"{_jours_fr(solde)} de congés. Dans le mois qui suit la reprise, indiquez "
                "au salarié ce nombre de jours et la date limite pour les prendre, le "
                "bulletin peut servir (C. trav. L3141-19-3). Le report dure 15 mois à compter "
                "de cette information (L3141-19-1). Martine ne fait pas expirer ces jours."
            ),
        }
    return None
