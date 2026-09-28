# app/modules/payroll/documents/payslip_editor.py
# Migré depuis services/payslip_editor.py. Comportement identique.
# Templates et chemins : app.core.paths ; BDD : app.core.database.

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.core.database import supabase
from app.core.paths import payroll_engine_templates, payroll_engine_employee_bulletins

logger = logging.getLogger(__name__)


def cumuls_pour_le_rendu(
    payslip_data: Dict[str, Any], cumuls_en_base: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Les cumuls à imprimer sont ceux du bulletin rendu.

    Le générateur appelle ce rendu juste après l'insertion du bulletin et
    avant d'écrire les cumuls du mois dans employee_schedules : la base porte
    alors encore ceux de la génération précédente (salarié 068, juillet 2026 : corps
    à jour, cumuls d'une génération en retard). Seuls les bulletins sans bloc
    cumuls — les mois importés à la reprise — se lisent en base.
    """
    du_bulletin = payslip_data.get("cumuls")
    if isinstance(du_bulletin, dict) and (du_bulletin.get("cumuls") or {}):
        return du_bulletin
    return cumuls_en_base


def regenerate_pdf_from_data(
    payslip_data: Dict[str, Any],
    employee_id: str,
    employee_folder_name: str,
    company_id: str,
    month: int,
    year: int,
    pdf_notes: Optional[str] = None,
    manually_edited: bool = False,
    edited_at: Optional[datetime] = None,
    pdf_name_suffix: str = "",
) -> Path:
    """
    Régénère un PDF de bulletin à partir de données JSON modifiées.

    Args:
        payslip_data: Données complètes du bulletin
        employee_id: ID de l'employé
        employee_folder_name: Nom du dossier de l'employé
        company_id: ID de l'entreprise
        month: Mois du bulletin
        year: Année du bulletin
        pdf_notes: Notes à afficher sur le PDF
        manually_edited: Indicateur de modification manuelle
        edited_at: Date de la dernière modification

    Returns:
        Path: Chemin vers le PDF généré
    """
    try:
        template_dir = payroll_engine_templates()
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("template_bulletin.html")

        cumuls_data = None
        try:
            cumuls_res = (
                supabase.table("employee_schedules")
                .select("cumuls")
                .match({"employee_id": employee_id, "year": year, "month": month})
                .maybe_single()
                .execute()
            )

            if cumuls_res and cumuls_res.data:
                cumuls_data = cumuls_res.data.get("cumuls")
        except Exception as e:
            logger.warning(f"Impossible de récupérer les cumuls: {str(e)}")

        from app.modules.payroll.engine.bulletin import build_solde_conges_pied_de_page

        pied_de_page = dict(payslip_data.get("pied_de_page") or {})
        solde_conges = build_solde_conges_pied_de_page(
            employee_id,
            year,
            month,
            (payslip_data.get("en_tete") or {}).get("date_fin_variables"),
        )
        if solde_conges:
            pied_de_page["solde_conges"] = solde_conges

        template_data = {
            **payslip_data,
            "pied_de_page": pied_de_page,
            "pdf_notes": pdf_notes,
            "manually_edited": manually_edited,
            "edited_at": edited_at.strftime("%d/%m/%Y à %H:%M") if edited_at else None,
            "cumuls": cumuls_pour_le_rendu(payslip_data, cumuls_data),
        }

        from app.modules.payroll.documents.bulletin_view import (
            construire_vue_bulletin,
        )

        html_content = template.render(vue=construire_vue_bulletin(template_data))

        employee_path = payroll_engine_employee_bulletins(employee_folder_name)
        employee_path.mkdir(parents=True, exist_ok=True)

        pdf_name = f"Bulletin_{employee_folder_name}_{month:02d}-{year}{pdf_name_suffix}.pdf"
        pdf_path = employee_path / pdf_name

        HTML(string=html_content).write_pdf(pdf_path)

        logger.info(f"PDF régénéré avec succès: {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"Erreur lors de la régénération du PDF: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de la génération du PDF: {str(e)}"
        )
