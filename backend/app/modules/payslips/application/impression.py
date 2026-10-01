"""Réimprimer le PDF d'un bulletin depuis ses données enregistrées, avec sa note.

Le générateur imprime le bulletin du moteur, qui ne connaît pas la note ajoutée
depuis l'écran : une régénération la faisait disparaître du PDF (audit du
28/09). La note vit dans sa colonne et survit à la régénération ; il suffit de
réimprimer le PDF après coup. Même chose quand seule la note change.
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
    """Refait le PDF, le dépose à un nouveau chemin et rend son nouveau lien signé.

    Nouveau chemin et non le même : voir `pdf_du_bulletin`. L'ancien fichier
    est retiré une fois la ligne du bulletin à jour.

    Rend None si le bulletin n'a pas de PDF enregistré : il n'y a rien à refaire.
    """
    from app.modules.payroll.documents.payslip_editor import regenerate_pdf_from_data
    from app.modules.payroll.documents.pdf_du_bulletin import (
        nom_affiche,
        rehorodater,
        retirer_pdf_remplace,
    )

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
    ancien = str(bulletin["pdf_storage_path"])
    nouveau = rehorodater(ancien)
    try:
        stockage = supabase.storage.from_("payslips")
        stockage.upload(
            path=nouveau,
            file=chemin.read_bytes(),
            file_options={"x-upsert": "true"},
        )
        lien = stockage.create_signed_url(
            nouveau, 3600, options={"download": nom_affiche(nouveau)}
        )["signedURL"]
    finally:
        try:
            chemin.unlink()
        except OSError:
            logger.warning("PDF temporaire non supprimé : %s", chemin)
    supabase.table("payslips").update({"pdf_storage_path": nouveau, "url": lien}).eq(
        "id", payslip_id
    ).execute()
    retirer_pdf_remplace(supabase, ancien, nouveau)
    return lien


def archiver_pdf(pdf_storage_path: str | None, destination: str) -> str | None:
    """Copie le PDF courant sous le chemin de sa version ; None si impossible.

    Le PDF d'un bulletin est écrasé à chaque régénération, et l'historique ne
    gardait qu'un lien signé d'une heure : passé ce délai, l'ancienne version
    n'avait plus de PDF (audit du 28/09). Jamais bloquant.
    """
    if not pdf_storage_path:
        return None
    stockage = supabase.storage.from_("payslips")
    try:
        try:
            stockage.remove([destination])
        except Exception:  # noqa: BLE001 — rien à retirer
            pass
        stockage.copy(pdf_storage_path, destination)
    except Exception:  # noqa: BLE001
        logger.warning("PDF de version non archivé : %s", destination, exc_info=True)
        return None
    return destination


def supprimer_pdfs(chemins: list[str]) -> None:
    """Retire les PDF des versions sorties de l'historique. Jamais bloquant."""
    if not chemins:
        return
    try:
        supabase.storage.from_("payslips").remove(chemins)
    except Exception:  # noqa: BLE001
        logger.warning("PDF de versions anciennes non retirés : %s", chemins, exc_info=True)
