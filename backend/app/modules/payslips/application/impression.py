"""Réimprimer le PDF d'un bulletin depuis ses données enregistrées, avec sa note.

Le générateur imprime le bulletin du moteur, qui ne connaît pas la note ajoutée
depuis l'écran : une régénération la faisait disparaître du PDF (audit du
28/09). La note vit dans sa colonne et survit à la régénération ; il suffit de
réimprimer le PDF après coup. Même chemin quand seule la note change.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

_COLONNES = "id, employee_id, company_id, year, month, payslip_data, pdf_notes, pdf_storage_path"


def _lire(payslip_id: str) -> dict[str, Any] | None:
    r = (
        supabase.table("payslips")
        .select(_COLONNES)
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


def _dossier_du_salarie(employee_id: str) -> str | None:
    r = (
        supabase.table("employees")
        .select("employee_folder_name")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    return (r.data or {}).get("employee_folder_name") if r else None


def reimprimer_bulletin(payslip_id: str) -> str | None:
    """Refait le PDF, le dépose à sa place et rend son nouveau lien signé.

    Rend None si le bulletin n'a pas de PDF enregistré : il n'y a rien à refaire.
    """
    from app.modules.payroll.documents.payslip_editor import regenerate_pdf_from_data

    bulletin = _lire(payslip_id)
    if not bulletin or not bulletin.get("pdf_storage_path"):
        return None
    dossier = _dossier_du_salarie(str(bulletin["employee_id"]))
    if not dossier:
        return None

    chemin = regenerate_pdf_from_data(
        payslip_data=bulletin.get("payslip_data") or {},
        employee_id=str(bulletin["employee_id"]),
        employee_folder_name=dossier,
        company_id=str(bulletin["company_id"]),
        month=int(bulletin["month"]),
        year=int(bulletin["year"]),
        pdf_notes=bulletin.get("pdf_notes") or None,
        pdf_name_suffix="_impression",
    )
    try:
        stockage = supabase.storage.from_("payslips")
        stockage.upload(
            path=bulletin["pdf_storage_path"],
            file=chemin.read_bytes(),
            file_options={"x-upsert": "true"},
        )
        lien = stockage.create_signed_url(
            bulletin["pdf_storage_path"], 3600, options={"download": True}
        )["signedURL"]
    finally:
        try:
            chemin.unlink()
        except OSError:
            logger.warning("PDF temporaire non supprimé : %s", chemin)
    supabase.table("payslips").update({"url": lien}).eq("id", payslip_id).execute()
    return lien
