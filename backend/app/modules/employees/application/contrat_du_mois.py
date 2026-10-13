"""Le contrat qui vaut pour un mois de paie, et sa date de sortie.

La clôture d'un départ efface `current_exit_id` de la fiche : la date de sortie
ne se lisait plus que sur la fin de contrat, absente d'un CDI ou d'un
apprentissage. Un départ clôturé avant son bulletin de sortie rendait ce
bulletin impossible (« Ce collaborateur n'est pas actif », relevé du
12/10/2026, [D3]). La sortie d'un salarié parti se lit donc sur le départ de son
contrat en cours : le premier départ daté depuis le début de ce contrat, archivé
ou non, hors départ annulé et hors transfert.

Après « Nouveau contrat », la fiche décrit le nouveau contrat : un mois de
l'ancien se calcule sur la fiche que ce contrat avait, rangée avec lui
(`employee_contract_periods.fiche`) [D4].
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger(__name__)

STATUTS_PARTIS = ("parti", "sorti", "inactif")
_DEPARTS_ANNULES = ("annulee", "annule", "cancelled", "canceled")


def _date(valeur: Any) -> date | None:
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return date.fromisoformat(valeur.strip()[:10])
        except ValueError:
            return None
    return None


def debut_du_contrat(employee: Mapping[str, Any]) -> date | None:
    """Le début du contrat de la fiche, comme la garde de présence de la paie."""
    return _date(employee.get("date_debut_execution") or employee.get("hire_date"))


class LecteurContrats:
    """Ce qui se lit en base (doublé en test)."""

    def sortie_du_contrat(self, employee_id: str, debut: date) -> str | None:
        """Dernier jour travaillé du premier départ daté depuis `debut`."""
        lignes = (
            supabase.table("employee_exits")
            .select("last_working_day, status, exit_type")
            .eq("employee_id", employee_id)
            .gte("last_working_day", debut.isoformat())
            .order("last_working_day")
            .execute()
            .data
        ) or []
        for ligne in lignes:
            if str(ligne.get("status") or "").lower() in _DEPARTS_ANNULES:
                continue
            if ligne.get("exit_type") == "transfert" or not ligne.get("last_working_day"):
                continue
            return str(ligne["last_working_day"])[:10]
        return None

    def contrat_passe_du_mois(self, employee_id: str, year: int, month: int) -> dict | None:
        """Le contrat rangé qui couvre au moins un jour du mois, le plus récent."""
        premier = date(year, month, 1)
        dernier = date(year + (month == 12), month % 12 + 1, 1)
        lignes = (
            supabase.table("employee_contract_periods")
            .select("*")
            .eq("employee_id", employee_id)
            .lt("date_debut", dernier.isoformat())
            .gte("date_fin", premier.isoformat())
            .order("date_fin", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []
        return dict(lignes[0]) if lignes else None


lecteur_contrats = LecteurContrats()


def fiche_du_mois(employee: Mapping[str, Any], year: int, month: int) -> dict[str, Any]:
    """La fiche sur laquelle le mois se calcule.

    Un mois d'avant le contrat en cours appartient à un contrat rangé par
    « Nouveau contrat » : il se calcule sur la fiche que ce contrat avait,
    rangée avec lui, « parti » et sans départ en cours (sa sortie se lit sur son
    départ, archivé). Sans fiche rangée (contrat passé saisi à la main), rien
    ne change : le mois reste refusé plutôt que calculé sur la fiche d'un autre
    contrat [D4].
    """
    debut = debut_du_contrat(employee)
    if debut is None or (year, month) >= (debut.year, debut.month) or not employee.get("id"):
        return dict(employee)
    periode = lecteur_contrats.contrat_passe_du_mois(str(employee["id"]), year, month)
    rangee = (periode or {}).get("fiche")
    if not isinstance(rangee, dict) or not rangee:
        return dict(employee)
    return {
        **employee,
        **rangee,
        "employment_status": "parti",
        "current_exit_id": None,
        "exit_last_working_day": None,
        "exit_type": None,
        "exit_status": None,
    }


def sortie_du_contrat_en_cours(employee: Mapping[str, Any]) -> str | None:
    """Date de sortie d'un salarié parti dont le départ est clôturé, ou None.

    Seulement pour un salarié parti sans départ en cours : un départ en cours se
    lit par `current_exit_id`, un salarié actif n'a pas de sortie à chercher.
    """
    statut = str(employee.get("employment_status") or "actif").lower()
    if statut not in STATUTS_PARTIS or employee.get("current_exit_id"):
        return None
    debut = debut_du_contrat(employee)
    if debut is None or not employee.get("id"):
        return None
    try:
        return lecteur_contrats.sortie_du_contrat(str(employee["id"]), debut)
    except Exception:  # noqa: BLE001 — sans lecture, la fin de contrat de la fiche reste
        logger.warning("Départ du contrat en cours non lu (%s).", employee.get("id"), exc_info=True)
        return None
