"""Le contrat qui vaut pour un mois de paie, et sa date de sortie.

La clôture d'un départ efface `current_exit_id` de la fiche : la date de sortie
ne se lisait plus que sur la fin de contrat, absente d'un CDI ou d'un
apprentissage. Un départ clôturé avant son bulletin de sortie rendait ce
bulletin impossible (« Ce collaborateur n'est pas actif », relevé du
12/10/2026, [D3]). La sortie d'un salarié parti se lit donc sur le départ de son
contrat en cours : le premier départ daté depuis le début de ce contrat, archivé
ou non, hors départ annulé et hors transfert.
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


lecteur_contrats = LecteurContrats()


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
