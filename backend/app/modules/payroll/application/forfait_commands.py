"""
Commandes applicatives : forfait jour (période de paie, analyse des jours).
forfait_jour.py et schedules appellent ce module, pas backend_calculs ni engine directement.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.modules.payroll.engine import ContextePaie, definir_periode_de_paie
from app.modules.payroll.engine.analyser_jours_forfait import (
    analyser_jours_forfait_du_mois as _analyser_jours_forfait_impl,
)


def definir_periode_de_paie_forfait(
    parametres_paie: Dict[str, Any],
    employee_statut: Optional[str],
    year: int,
    month: int,
) -> Tuple[Optional[date], Optional[date]]:
    """
    Retourne (date_debut_periode, date_fin_periode) pour le forfait jour.
    Crée un ContextePaie minimal puis appelle engine.definir_periode_de_paie.
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        temp_contrat = temp_dir / "contrat.json"
        temp_entreprise = temp_dir / "entreprise.json"
        temp_cumuls = temp_dir / "cumuls.json"

        contrat_minimal = {
            "contrat": {"statut": employee_statut or "Non-Cadre"},
            "remuneration": {"salaire_de_base": {"valeur": 0.0}},
        }
        temp_contrat.write_text(json.dumps(contrat_minimal), encoding="utf-8")

        entreprise_minimal = {
            "entreprise": {
                "parametres_paie": {
                    "periode_de_paie": parametres_paie.get(
                        "periode_de_paie",
                        {"jour_de_fin": 4, "occurrence": -2},
                    )
                }
            }
        }
        temp_entreprise.write_text(json.dumps(entreprise_minimal), encoding="utf-8")
        temp_cumuls.write_text(json.dumps({"cumuls": {}}), encoding="utf-8")

        contexte_temp = ContextePaie(
            chemin_contrat=str(temp_contrat),
            chemin_entreprise=str(temp_entreprise),
            chemin_cumuls=str(temp_cumuls),
            chemin_data_dir=str(temp_dir),
        )
        date_debut, date_fin = definir_periode_de_paie(contexte_temp, year, month)
        return date_debut, date_fin
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def analyser_jours_forfait_du_mois(
    planned_data_all_months: List[Dict[str, Any]],
    actual_data_all_months: List[Dict[str, Any]],
    annee: int,
    mois: int,
    employee_name: str,
    date_debut_periode: Optional[date] = None,
    date_fin_periode: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Analyse des jours forfait. Délègue à engine.analyser_jours_forfait."""
    return _analyser_jours_forfait_impl(
        planned_data_all_months=planned_data_all_months,
        actual_data_all_months=actual_data_all_months,
        annee=annee,
        mois=mois,
        employee_name=employee_name,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
    )
