"""
Wrapper partagé vers le forfait jour (app.modules.payroll).

Seul point d'appel du forfait jour depuis app/*. Les modules (ex. schedules) passent
par ce wrapper sans importer le moteur payroll directement.
Délègue à app.modules.payroll.application.forfait_commands et engine.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.modules.payroll.application.forfait_commands import (
    analyser_jours_forfait_du_mois as _analyser_impl,
    definir_periode_de_paie_forfait,
)


def definir_periode_de_paie(
    parametres_paie: Dict[str, Any],
    employee_statut: Optional[str],
    year: int,
    month: int,
) -> Tuple[Optional[date], Optional[date]]:
    """
    Retourne (date_debut_periode, date_fin_periode) pour le forfait jour.
    Délègue à app.modules.payroll.application.forfait_commands.
    """
    return definir_periode_de_paie_forfait(
        parametres_paie=parametres_paie,
        employee_statut=employee_statut,
        year=year,
        month=month,
    )


def analyser_jours_forfait_du_mois(
    planned_data_all_months: List[Dict[str, Any]],
    actual_data_all_months: List[Dict[str, Any]],
    annee: int,
    mois: int,
    employee_name: str,
    date_debut_periode: Optional[date] = None,
    date_fin_periode: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Délègue à app.modules.payroll.application.forfait_commands (engine)."""
    return _analyser_impl(
        planned_data_all_months=planned_data_all_months,
        actual_data_all_months=actual_data_all_months,
        annee=annee,
        mois=mois,
        employee_name=employee_name,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
    )
