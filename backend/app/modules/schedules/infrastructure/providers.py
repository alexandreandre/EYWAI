"""
Fournisseurs externes du module schedules : analyse de paie, forfait jour, fichiers calendriers.

Implémentations des ports IPayrollAnalyzerProvider, IForfaitJourProvider, IFileCalendarProvider.
Délèguent à app.shared.infrastructure.payroll_analyzer / forfait_jour et aux chemins runtime ``app.core.paths``.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.paths import payroll_engine_employee_folder
from app.modules.schedules.domain.interfaces import (
    IFileCalendarProvider,
    IForfaitJourProvider,
    IPayrollAnalyzerProvider,
)
from app.shared.infrastructure import forfait_jour as forfait_jour_impl
from app.shared.infrastructure import payroll_analyzer as payroll_analyzer_impl


class PayrollAnalyzerProvider(IPayrollAnalyzerProvider):
    """Délègue à app.shared.infrastructure.payroll_analyzer → app.modules.payroll.application.analyzer."""

    def analyser_horaires(
        self,
        planned_data_all_months: List[Dict[str, Any]],
        actual_data_all_months: List[Dict[str, Any]],
        duree_hebdo_contrat: float,
        annee: int,
        mois: int,
        employee_name: str,
    ) -> List[Dict[str, Any]]:
        return payroll_analyzer_impl.analyser_horaires_du_mois(
            planned_data_all_months=planned_data_all_months,
            actual_data_all_months=actual_data_all_months,
            duree_hebdo_contrat=duree_hebdo_contrat,
            annee=annee,
            mois=mois,
            employee_name=employee_name,
        )


class ForfaitJourProvider(IForfaitJourProvider):
    """Délègue à app.shared.infrastructure.forfait_jour → app.modules.payroll.application."""

    def definir_periode_de_paie(
        self,
        parametres_paie: Dict[str, Any],
        employee_statut: Optional[str],
        year: int,
        month: int,
    ) -> Tuple[Optional[date], Optional[date]]:
        return forfait_jour_impl.definir_periode_de_paie(
            parametres_paie, employee_statut, year, month
        )

    def analyser_jours_forfait_du_mois(
        self,
        planned_data_all_months: List[Dict[str, Any]],
        actual_data_all_months: List[Dict[str, Any]],
        annee: int,
        mois: int,
        employee_name: str,
        date_debut_periode: Optional[date] = None,
        date_fin_periode: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        return forfait_jour_impl.analyser_jours_forfait_du_mois(
            planned_data_all_months=planned_data_all_months,
            actual_data_all_months=actual_data_all_months,
            annee=annee,
            mois=mois,
            employee_name=employee_name,
            date_debut_periode=date_debut_periode,
            date_fin_periode=date_fin_periode,
        )


class FileCalendarProvider(IFileCalendarProvider):
    """Lecture des fichiers calendriers / horaires via app.core.paths (data/employes/<folder>)."""

    def __init__(self, base_path: Optional[Path] = None):
        self._base_path = base_path

    def _employee_path(self, employee_folder_name: str) -> Path:
        if self._base_path is not None:
            return self._base_path / "data" / "employes" / employee_folder_name
        return payroll_engine_employee_folder(employee_folder_name)

    def read_planned_calendar(
        self, employee_folder_name: str, year: int, month: int
    ) -> List[Dict[str, Any]]:
        path = (
            self._employee_path(employee_folder_name)
            / "calendriers"
            / f"{month:02d}.json"
        )
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("calendrier_prevu", [])

    def read_actual_hours(
        self, employee_folder_name: str, year: int, month: int
    ) -> List[Dict[str, Any]]:
        path = (
            self._employee_path(employee_folder_name) / "horaires" / f"{month:02d}.json"
        )
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("calendrier_reel", [])


# Instances pour l'application
payroll_analyzer_provider = PayrollAnalyzerProvider()
forfait_jour_provider = ForfaitJourProvider()
file_calendar_provider = FileCalendarProvider()
