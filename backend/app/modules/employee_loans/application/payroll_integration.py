"""Intégration paie partagée — prêts employeur (heures et forfait)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
    #: Le HTML du PDF que le moteur vient d'imprimer et de déposer à
    #: `storage_path` (lot 43) : le même à imprimer, rien n'est réimprimé.
    html_imprime: Optional[str] = None


def inject_loan_benefit_in_kind(
    contrat_json: Dict[str, Any],
    employee_id: str,
    year: int,
    month: int,
) -> Dict[str, Any]:
    """Injecte l'avantage en nature prêt employeur dans contrat.json avant moteur paie.

    Prêts ou taux illisibles : `LectureIndispensable`, le bulletin n'est pas
    calculé (plutôt que calculé sans l'avantage). Un autre échec du calcul
    laisse le brut sans l'avantage, et le bulletin le dit.
    """
    from app.modules.payroll.engine.lectures import LectureIndispensable

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
    except LectureIndispensable:
        raise
    except Exception:
        logger.exception("Avantage en nature du prêt employeur non calculé (%s, %02d/%d)",
                         employee_id, month, year)
        from app.modules.payroll.engine.replis import CODE_REPLI_AVANTAGE_PRET, noter_repli

        noter_repli(CODE_REPLI_AVANTAGE_PRET)
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
    Enrichit le bulletin (saisies/avances + prêts), régénère le PDF et persiste payslip_data.

    Chaque échec se voit sur le bulletin (alerte de repli) : avances ou prêts
    non calculés, PDF non redéposé. Le PDF passe avant l'enregistrement pour
    que son échec soit enregistré avec le bulletin. Si c'est l'enregistrement
    qui échoue, l'alerte part avec la réponse de la génération.
    """
    from app.modules.payroll.engine.replis import (
        CODE_REPLI_AVANCES,
        CODE_REPLI_PRETS,
        CODE_REPLI_RETENUES_A_RECALCULER,
        fusionner_replis,
    )

    def _avec_repli(donnees: Dict[str, Any], code: str) -> Dict[str, Any]:
        donnees = dict(donnees)
        donnees["alertes_baremes"] = fusionner_replis(
            donnees.get("alertes_baremes"), [{"code": code}]
        )
        return donnees

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
        except Exception:
            # Les avances ne sont retenues qu'ici : leur échec se voit sur le
            # bulletin, comme tout repli de la génération.
            logger.exception("Enrichissement saisies/avances du bulletin %s en échec", payslip_id)
            enriched_data = _avec_repli(enriched_data, CODE_REPLI_AVANCES)

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
        except Exception:
            # Les prêts ne sont retenus qu'ici aussi : même règle que les avances.
            logger.exception("Enrichissement prêts employeur du bulletin %s en échec", payslip_id)
            enriched_data = _avec_repli(enriched_data, CODE_REPLI_PRETS)

        if pdf_regen and not _regenerate_and_upload_pdf(enriched_data, pdf_regen):
            enriched_data = _avec_repli(enriched_data, CODE_REPLI_RETENUES_A_RECALCULER)

        try:
            supabase.table("payslips").update({"payslip_data": enriched_data}).eq(
                "id", payslip_id
            ).execute()
        except Exception:
            # En base, le bulletin du moteur, sans ses retenues ; les soldes ont
            # bougé. Le recalcul remet tout d'accord : l'écran le dit.
            logger.exception("Bulletin enrichi %s non enregistré", payslip_id)
            enriched_data = _avec_repli(enriched_data, CODE_REPLI_RETENUES_A_RECALCULER)

    return enriched_data


def _regenerate_and_upload_pdf(
    enriched_data: Dict[str, Any],
    config: PdfRegenConfig,
) -> bool:
    """Réimprime et redépose le PDF s'il a changé ; False si cela a échoué."""
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
            html_deja_imprime=config.html_imprime,
        )
        if enriched_pdf_path is None:
            # L'enrichissement n'a rien changé à imprimer : le PDF du moteur,
            # déjà déposé à ce chemin, est le même document.
            return True

        with open(enriched_pdf_path, "rb") as f:
            supabase.storage.from_("payslips").upload(
                path=config.storage_path,
                file=f.read(),
                file_options={"x-upsert": "true"},
            )

        logger.info("PDF régénéré avec enrichissements: %s", enriched_pdf_path)
        return True
    except Exception:
        # Le PDF déposé reste celui du moteur, sans les retenues.
        logger.exception("PDF enrichi non régénéré ou non déposé (%s)", config.storage_path)
        return False
