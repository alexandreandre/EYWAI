"""Intégration paie partagée — prêts employeur (heures et forfait)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.database import supabase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PdfRegenConfig:
    employee_id: str
    employee_folder_name: str
    company_id: str
    month: int
    year: int
    storage_path: str
    pdf_name_suffix: str = ""


def inject_loan_benefit_in_kind(
    contrat_json: Dict[str, Any],
    employee_id: str,
    year: int,
    month: int,
) -> Dict[str, Any]:
    """Injecte l'avantage en nature prêt employeur dans contrat.json avant moteur paie."""
    try:
        from app.modules.employee_loans.infrastructure.payroll_queries import (
            compute_total_loan_benefit_in_kind,
        )

        loan_an = compute_total_loan_benefit_in_kind(employee_id, year, month)
        if loan_an > 0:
            remuneration = contrat_json.setdefault("remuneration", {})
            aen = remuneration.get("avantages_en_nature")
            if not isinstance(aen, dict):
                aen = {}
            aen["pret_employeur"] = {"montant_mensuel": loan_an}
            remuneration["avantages_en_nature"] = aen
            logger.debug("Avantage en nature prêt employeur: %s€", loan_an)
    except Exception as exc:
        logger.warning("Erreur calcul AN prêt employeur: %s", exc)
    return contrat_json


def enrich_payslip_after_upsert(
    payslip_data: Dict[str, Any],
    employee_id: str,
    year: int,
    month: int,
    payslip_id: Optional[str],
    *,
    pdf_regen: Optional[PdfRegenConfig] = None,
) -> Dict[str, Any]:
    """
    Enrichit le bulletin (saisies/avances + prêts), persiste payslip_data et régénère le PDF.
    """
    enriched_data = payslip_data

    if payslip_id:
        try:
            from app.modules.saisies_avances.application.service import enrich_payslip

            enriched_data = enrich_payslip(
                payslip_data.copy(),
                employee_id,
                year,
                month,
                payslip_id=payslip_id,
            )
        except Exception as exc:
            logger.warning("Erreur enrichissement saisies/avances: %s", exc)

        try:
            from app.modules.employee_loans.application.enrichment import (
                enrich_payslip_loans,
            )

            enriched_data = enrich_payslip_loans(
                enriched_data,
                employee_id,
                year,
                month,
                payslip_id=payslip_id,
            )
        except Exception as exc:
            logger.warning("Erreur enrichissement prêts employeur: %s", exc)

        try:
            supabase.table("payslips").update({"payslip_data": enriched_data}).eq(
                "id", payslip_id
            ).execute()
        except Exception as exc:
            logger.warning("Erreur mise à jour payslip_data enrichi: %s", exc)

        if pdf_regen:
            _regenerate_and_upload_pdf(enriched_data, pdf_regen)

    return enriched_data


def _regenerate_and_upload_pdf(
    enriched_data: Dict[str, Any],
    config: PdfRegenConfig,
) -> None:
    try:
        from app.modules.payroll.documents.payslip_editor import regenerate_pdf_from_data

        enriched_pdf_path = regenerate_pdf_from_data(
            enriched_data,
            config.employee_id,
            config.employee_folder_name,
            config.company_id,
            config.month,
            config.year,
            pdf_name_suffix=config.pdf_name_suffix,
        )

        with open(enriched_pdf_path, "rb") as f:
            supabase.storage.from_("payslips").upload(
                path=config.storage_path,
                file=f.read(),
                file_options={"x-upsert": "true"},
            )

        logger.info("PDF régénéré avec enrichissements: %s", enriched_pdf_path)
    except Exception as exc:
        logger.warning("Régénération PDF enrichi échouée: %s", exc)
