"""
Wrapper partagé vers l'analyse des horaires (événements de paie).

Délègue à app.modules.payroll.application.analyzer (source de vérité unique).
"""
from typing import Any, Dict, List


def analyser_horaires_du_mois(
    planned_data_all_months: List[Dict[str, Any]],
    actual_data_all_months: List[Dict[str, Any]],
    duree_hebdo_contrat: float,
    annee: int,
    mois: int,
    employee_name: str,
) -> List[Dict[str, Any]]:
    """Délègue à app.modules.payroll.application.analyzer.analyser_horaires_du_mois."""
    from app.modules.payroll.application.analyzer import analyser_horaires_du_mois as _analyser

    return _analyser(
        planned_data_all_months=planned_data_all_months,
        actual_data_all_months=actual_data_all_months,
        duree_hebdo_contrat=duree_hebdo_contrat,
        annee=annee,
        mois=mois,
        employee_name=employee_name,
    )
