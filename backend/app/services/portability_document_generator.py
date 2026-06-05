"""
PDF d'attestations de portabilité (mutuelle / prévoyance) — ReportLab.
Utilisé lorsque aucun template client n'est disponible pour la sortie.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_reportlab,
    get_company_city,
    get_company_signatory,
    setup_custom_styles,
)


EXIT_TYPE_LIBELLES: Dict[str, str] = {
    "licenciement": "licenciement",
    "fin_cdd": "fin de contrat à durée déterminée",
    "rupture_conventionnelle": "rupture conventionnelle",
    "demission": "démission",
    "depart_retraite": "départ à la retraite",
    "fin_periode_essai": "fin de période d'essai",
    "fin_mission": "fin de mission (intérim)",
}


class PortabilityDocumentGenerator:
    """Génère des attestations de portabilité au format PDF."""

    def _employee_block(self, employee: Dict[str, Any]) -> tuple[str, str, str]:
        prenom = employee.get("first_name") or ""
        nom = employee.get("last_name") or ""
        poste = employee.get("job_title") or "—"
        nir = employee.get("nir") or ""
        prenom_nom = f"{prenom} {nom}".strip() or "—"
        return prenom_nom, poste, nir

    def _build_pdf(
        self,
        title: str,
        body_intro: str,
        employee: Dict[str, Any],
        company: Dict[str, Any],
        exit_date: str,
        exit_type: str,
        regime_label: str,
        insurer_name: Optional[str] = None,
    ) -> bytes:
        prenom_nom, poste, nir = self._employee_block(employee)
        motif = EXIT_TYPE_LIBELLES.get(
            exit_type, exit_type.replace("_", " ") if exit_type else "—"
        )
        company_city = get_company_city(company) or "…………………"
        today = date.today().strftime("%d/%m/%Y")
        signatory, signatory_title = get_company_signatory(company)
        org = (
            insurer_name
            or company.get("organisme_assureur")
            or company.get("mutuelle_nom")
            or "l'organisme assureur désigné par l'employeur"
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        styles = setup_custom_styles(styles)
        styles.add(
            ParagraphStyle(
                name="TitrePorta",
                parent=styles["Heading1"],
                fontSize=14,
                alignment=TA_CENTER,
                spaceAfter=16,
                textColor=colors.HexColor("#1e3a8a"),
            )
        )
        styles.add(
            ParagraphStyle(
                name="CorpsPorta",
                parent=styles["Normal"],
                fontSize=11,
                alignment=TA_JUSTIFY,
                leading=15,
            )
        )
        story = []
        build_branding_header_reportlab(story, styles, company)
        story.append(Paragraph(title, styles["TitrePorta"]))
        story.append(Spacer(1, 0.6 * cm))

        nir_line = (
            f", immatriculé(e) sous le n° {nir},"
            if nir
            else ","
        )

        corps = f"""
        {body_intro}
        <br/><br/>
        Nous attestons que M./Mme <b>{prenom_nom}</b>{nir_line}
        employé(e) en qualité de <b>{poste}</b>, dont le contrat de travail a pris fin
        le <b>{exit_date}</b> pour motif de <b>{motif}</b>,
        bénéficie du maintien provisoire de ses droits en <b>{regime_label}</b>
        auprès de <b>{org}</b>,
        conformément à l'article L.911-8 du Code de la sécurité sociale.
        <br/><br/>
        <b>Durée du maintien :</b> égale à la durée du dernier contrat de travail,
        dans la limite de douze mois à compter de la fin du contrat.
        <br/><br/>
        <b>Conditions :</b> le maintien des garanties est subordonné au paiement
        des cotisations par le bénéficiaire, dans les conditions fixées par
        l'organisme assureur et la réglementation en vigueur.
        <br/><br/>
        <b>Démarches :</b> le bénéficiaire doit informer <b>{org}</b>
        de sa situation dans un délai de dix jours à compter de la fin du contrat
        de travail, et produire les justificatifs demandés.
        """
        story.append(Paragraph(corps, styles["CorpsPorta"]))
        story.append(Spacer(1, 1 * cm))
        story.append(
            Paragraph(
                f"Fait à {company_city}, le {today}, pour servir et valoir ce que de droit.",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 1.2 * cm))
        sig = f"<b>{signatory}</b>"
        if signatory_title:
            sig += f"<br/><i>{signatory_title}</i>"
        sig += "<br/>Signature et cachet de l'employeur"
        story.append(Paragraph(sig, styles["Normal"]))
        story.append(Spacer(1, 0.8 * cm))
        story.append(
            Paragraph(
                "<i>Article L.911-8 du Code de la sécurité sociale — Portabilité des droits</i>",
                ParagraphStyle(
                    name="PiedPorta",
                    parent=styles["Normal"],
                    fontSize=8,
                    textColor=colors.HexColor("#9ca3af"),
                    alignment=TA_CENTER,
                ),
            )
        )
        doc.build(story)
        out = buffer.getvalue()
        buffer.close()
        return out

    def generate_portabilite_mutuelle(
        self,
        employee: Dict[str, Any],
        company: Dict[str, Any],
        exit_date: str,
        exit_type: str,
        insurer_name: Optional[str] = None,
    ) -> bytes:
        title = (
            "Attestation de portabilité des droits "
            "à la complémentaire santé (mutuelle)"
        )
        intro = (
            "Le présent document atteste du droit à la portabilité de la "
            "complémentaire santé collective."
        )
        return self._build_pdf(
            title,
            intro,
            employee,
            company,
            exit_date,
            exit_type,
            "complémentaire santé",
            insurer_name=insurer_name,
        )

    def generate_portabilite_prevoyance(
        self,
        employee: Dict[str, Any],
        company: Dict[str, Any],
        exit_date: str,
        exit_type: str,
        insurer_name: Optional[str] = None,
    ) -> bytes:
        title = "Attestation de portabilité des droits à la prévoyance"
        intro = (
            "Le présent document atteste du droit à la portabilité en prévoyance "
            "collective (décès, incapacité, invalidité)."
        )
        return self._build_pdf(
            title,
            intro,
            employee,
            company,
            exit_date,
            exit_type,
            "prévoyance",
            insurer_name=insurer_name,
        )


portability_generator = PortabilityDocumentGenerator()
