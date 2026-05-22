"""
Export CSV de la vue Mon Entreprise (pilotage + overview).
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict


def build_company_export_csv(
    company_data: Dict[str, Any],
    kpis: Dict[str, Any],
    overview_demographics: Dict[str, Any],
    overview_movements: Dict[str, Any],
) -> str:
    """Génère un CSV texte (UTF-8) pour téléchargement."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")

    writer.writerow(["Section", "Indicateur", "Valeur"])
    writer.writerow(["Entreprise", "Nom", company_data.get("company_name", "")])
    writer.writerow(["Entreprise", "SIRET", company_data.get("siret", "")])

    writer.writerow([])
    writer.writerow(["Pilotage paie", "Effectif", kpis.get("total_employees", 0)])
    writer.writerow(
        ["Pilotage paie", "Masse salariale brute M-1", kpis.get("last_month_gross_salary", 0)]
    )
    writer.writerow(
        ["Pilotage paie", "Coût total employeur M-1", kpis.get("last_month_total_cost", 0)]
    )
    writer.writerow(
        ["Pilotage paie", "Taux de charges %", kpis.get("payroll_tax_rate", 0)]
    )
    writer.writerow(
        ["Pilotage paie", "Masse salariale 12 mois", kpis.get("annual_gross_salary", 0)]
    )

    writer.writerow([])
    writer.writerow(["Effectifs", "ETP", overview_demographics.get("total_etp", 0)])
    writer.writerow(
        ["Effectifs", "Ancienneté moyenne (ans)", overview_demographics.get("average_tenure_years", 0)]
    )
    writer.writerow(
        ["Effectifs", "% cadres", overview_demographics.get("cadre_percent", 0)]
    )
    writer.writerow(
        ["Mouvements", "Embauches 30j", overview_movements.get("new_hires_30_days", 0)]
    )
    writer.writerow(
        ["Mouvements", "Embauches 12 mois", overview_movements.get("new_hires_12_months", 0)]
    )
    writer.writerow(
        ["Mouvements", "Turn-over 12 mois %", overview_movements.get("turnover_rate_12_months", 0)]
    )

    evolution = kpis.get("evolution_12_months") or []
    if evolution:
        writer.writerow([])
        writer.writerow(["Évolution mensuelle", "Mois", "Masse brute", "Coût employeur"])
        for row in evolution:
            writer.writerow(
                [
                    "Évolution",
                    row.get("month", ""),
                    row.get("masse_salariale_brute", 0),
                    row.get("cout_total_employeur", 0),
                ]
            )

    return buffer.getvalue()
