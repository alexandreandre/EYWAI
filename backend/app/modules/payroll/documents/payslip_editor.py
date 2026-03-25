# app/modules/payroll/documents/payslip_editor.py
# Migré depuis services/payslip_editor.py. Comportement identique.
# Templates et chemins : app.core.paths ; BDD : app.core.database.

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.core.database import supabase
from app.core.paths import payroll_engine_templates, payroll_engine_employee_bulletins

logger = logging.getLogger(__name__)


def regenerate_pdf_from_data(
    payslip_data: Dict[str, Any],
    employee_id: str,
    employee_folder_name: str,
    company_id: str,
    month: int,
    year: int,
    pdf_notes: Optional[str] = None,
    manually_edited: bool = False,
    edited_at: Optional[datetime] = None
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
            cumuls_res = supabase.table('employee_schedules') \
                .select("cumuls") \
                .match({'employee_id': employee_id, 'year': year, 'month': month}) \
                .maybe_single() \
                .execute()

            if cumuls_res and cumuls_res.data:
                cumuls_data = cumuls_res.data.get('cumuls')
        except Exception as e:
            logger.warning(f"Impossible de récupérer les cumuls: {str(e)}")

        template_data = {
            **payslip_data,
            "pdf_notes": pdf_notes,
            "manually_edited": manually_edited,
            "edited_at": edited_at.strftime("%d/%m/%Y à %H:%M") if edited_at else None,
            "cumuls": cumuls_data
        }

        html_content = template.render(**template_data)

        employee_path = payroll_engine_employee_bulletins(employee_folder_name)
        employee_path.mkdir(parents=True, exist_ok=True)

        pdf_name = f"Bulletin_{employee_folder_name}_{month:02d}-{year}.pdf"
        pdf_path = employee_path / pdf_name

        HTML(string=html_content).write_pdf(pdf_path)

        logger.info(f"PDF régénéré avec succès: {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"Erreur lors de la régénération du PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du PDF: {str(e)}")


def save_edited_payslip(
    payslip_id: str,
    new_payslip_data: Dict[str, Any],
    changes_summary: str,
    current_user_id: str,
    current_user_name: str,
    pdf_notes: Optional[str] = None,
    internal_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sauvegarde les modifications d'un bulletin de paie.

    Args:
        payslip_id: ID du bulletin à modifier
        new_payslip_data: Nouvelles données du bulletin
        changes_summary: Résumé des modifications
        current_user_id: ID de l'utilisateur effectuant la modification
        current_user_name: Nom de l'utilisateur
        pdf_notes: Notes visibles sur le PDF
        internal_note: Note interne (non visible sur PDF)

    Returns:
        Dict contenant les informations du bulletin modifié et l'URL du nouveau PDF
    """
    try:
        payslip = supabase.table('payslips').select("*").eq('id', payslip_id).single().execute().data

        if not payslip:
            raise HTTPException(status_code=404, detail="Bulletin non trouvé")

        employee = supabase.table('employees').select("employee_folder_name").eq('id', payslip['employee_id']).single().execute().data

        if not employee:
            raise HTTPException(status_code=404, detail="Employé non trouvé")

        edit_history = payslip.get('edit_history') or []
        if not isinstance(edit_history, list):
            edit_history = []

        new_version = len(edit_history) + 1

        history_entry = {
            "version": new_version,
            "edited_at": datetime.now().isoformat(),
            "edited_by": current_user_id,
            "edited_by_name": current_user_name,
            "changes_summary": changes_summary,
            "previous_payslip_data": payslip.get('payslip_data', {}),
            "previous_pdf_url": payslip.get('url')
        }

        edit_history.append(history_entry)

        internal_notes = payslip.get('internal_notes') or []
        if not isinstance(internal_notes, list):
            internal_notes = []

        if internal_note:
            note_entry = {
                "id": str(uuid.uuid4()),
                "author_id": current_user_id,
                "author_name": current_user_name,
                "timestamp": datetime.now().isoformat(),
                "content": internal_note
            }
            internal_notes.append(note_entry)

        old_pdf_path = payslip.get('pdf_storage_path')
        if old_pdf_path and new_version == 1:
            company_id = payslip['company_id']
            employee_id = payslip['employee_id']
            month = payslip['month']
            year = payslip['year']
            employee_folder_name = employee['employee_folder_name']

            original_storage_path = f"{company_id}/{employee_id}/bulletins/Bulletin_{employee_folder_name}_{month:02d}-{year}_v0.pdf"

            try:
                old_pdf_data = supabase.storage.from_("payslips").download(old_pdf_path)
                supabase.storage.from_("payslips").upload(
                    path=original_storage_path,
                    file=old_pdf_data,
                    file_options={"x-upsert": "true"}
                )
            except Exception as e:
                logger.warning(f"Impossible de sauvegarder l'ancienne version du PDF: {str(e)}")

        edited_at = datetime.now()
        pdf_path = regenerate_pdf_from_data(
            payslip_data=new_payslip_data,
            employee_id=payslip['employee_id'],
            employee_folder_name=employee['employee_folder_name'],
            company_id=payslip['company_id'],
            month=payslip['month'],
            year=payslip['year'],
            pdf_notes=pdf_notes,
            manually_edited=True,
            edited_at=edited_at
        )

        storage_path = payslip['pdf_storage_path']
        with open(pdf_path, 'rb') as f:
            supabase.storage.from_("payslips").upload(
                path=storage_path,
                file=f.read(),
                file_options={"x-upsert": "true"}
            )

        signed_url_response = supabase.storage.from_("payslips").create_signed_url(
            storage_path,
            3600,
            options={'download': True}
        )
        new_pdf_url = signed_url_response['signedURL']

        updated_payslip = supabase.table('payslips').update({
            "payslip_data": new_payslip_data,
            "manually_edited": True,
            "edited_at": edited_at.isoformat(),
            "edited_by": current_user_id,
            "internal_notes": internal_notes,
            "pdf_notes": pdf_notes,
            "edit_history": edit_history,
            "url": new_pdf_url
        }).eq('id', payslip_id).execute().data[0]

        try:
            from app.modules.repos_compensateur.application.service import (
                recalculer_credits_repos_employe,
            )
            recalculer_credits_repos_employe(
                payslip['employee_id'],
                payslip['company_id'],
                payslip['year'],
            )
        except Exception as cor_err:
            logger.warning(f"Recalc COR après modification bulletin: {cor_err}")

        try:
            pdf_path.unlink()
        except Exception as e:
            logger.warning(f"Impossible de supprimer le fichier temporaire: {str(e)}")

        return {
            "payslip": updated_payslip,
            "new_pdf_url": new_pdf_url
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du bulletin modifié: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde: {str(e)}")


def restore_payslip_version(
    payslip_id: str,
    version: int,
    current_user_id: str,
    current_user_name: str
) -> Dict[str, Any]:
    """
    Restaure une version précédente d'un bulletin.

    Args:
        payslip_id: ID du bulletin
        version: Numéro de version à restaurer
        current_user_id: ID de l'utilisateur
        current_user_name: Nom de l'utilisateur

    Returns:
        Dict contenant les informations du bulletin restauré
    """
    try:
        payslip = supabase.table('payslips').select("*").eq('id', payslip_id).single().execute().data

        if not payslip:
            raise HTTPException(status_code=404, detail="Bulletin non trouvé")

        edit_history = payslip.get('edit_history') or []

        if version < 1 or version > len(edit_history):
            raise HTTPException(status_code=400, detail=f"Version invalide. Versions disponibles: 1-{len(edit_history)}")

        history_entry = edit_history[version - 1]
        previous_data = history_entry.get('previous_payslip_data')

        if not previous_data:
            raise HTTPException(status_code=400, detail="Données de la version introuvables")

        return save_edited_payslip(
            payslip_id=payslip_id,
            new_payslip_data=previous_data,
            changes_summary=f"Restauration de la version {version}",
            current_user_id=current_user_id,
            current_user_name=current_user_name,
            pdf_notes=payslip.get('pdf_notes'),
            internal_note=f"Version {version} restaurée"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la restauration de la version: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la restauration: {str(e)}")
