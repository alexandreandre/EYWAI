"""
PDF d'attestations de portabilité (mutuelle / prévoyance) — ReportLab.
Utilisé lorsque aucun template client n'est disponible pour la sortie.
"""

from __future__ import annotations

import io
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


EXIT_TYPE_LIBELLES: Dict[str, str] = {
    "licenciement": "licenciement",
    "fin_cdd": "fin de contrat à durée déterminée",
    "rupture_conventionnelle": "rupture conventionnelle",
}


class PortabilityDocumentGenerator:
    """Génère des attestations de portabilité au format PDF."""

    def _company_header(self, company: Dict[str, Any]) -> str:
        name = (
            company.get("company_name")
            or company.get("raison_sociale")
            or company.get("name")
            or "Entreprise"
        )
        siret = company.get("siret") or ""
        return f"<b>{name}</b><br/>SIRET : {siret}"

    def _employee_block(self, employee: Dict[str, Any]) -> tuple[str, str]:
        prenom = employee.get("first_name") or ""
        nom = employee.get("last_name") or ""
        poste = employee.get("job_title") or "—"
        prenom_nom = f"{prenom} {nom}".strip() or "—"
        return prenom_nom, poste

    def _build_pdf(
        self,
        title: str,
        body_intro: str,
        employee: Dict[str, Any],
        company: Dict[str, Any],
        exit_date: str,
        exit_type: str,
    ) -> bytes:
        prenom_nom, poste = self._employee_block(employee)
        motif = EXIT_TYPE_LIBELLES.get(
            exit_type, exit_type.replace("_", " ") if exit_type else "—"
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
        story.append(Paragraph(self._company_header(company), styles["Normal"]))
        story.append(Spacer(1, 0.8 * cm))
        story.append(Paragraph(title, styles["TitrePorta"]))
        story.append(Spacer(1, 0.6 * cm))

        corps = f"""
        {body_intro}
        <br/><br/>
        Nous attestons que M./Mme <b>{prenom_nom}</b>, employé(e) en qualité de <b>{poste}</b>,
        dont le contrat de travail a pris fin le <b>{exit_date}</b> pour motif de <b>{motif}</b>,
        bénéficie du maintien de ses droits concernés conformément à l'article L.911-8 du Code
        de la Sécurité Sociale.
        <br/><br/>
        <b>Durée :</b> La durée du maintien est égale à la durée du dernier contrat de travail,
        dans la limite de 12 mois.
        <br/><br/>
        <b>Démarches :</b> Le bénéficiaire doit signaler sa situation à l'organisme assureur
        dans les 10 jours suivant la fin du contrat.
        """
        story.append(Paragraph(corps, styles["CorpsPorta"]))
        story.append(Spacer(1, 1.2 * cm))
        story.append(
            Paragraph(
                "Fait pour servir et valoir ce que de droit.<br/><br/>"
                "Lieu : _________________ &nbsp;&nbsp;&nbsp; Date : _________________<br/><br/>"
                "Signature et cachet (RH)",
                styles["Normal"],
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
    ) -> bytes:
        title = (
            "Attestation de portabilité des droits "
            "à la complémentaire santé (Mutuelle)"
        )
        intro = (
            "Le présent document atteste des droits à la portabilité de la complémentaire santé."
        )
        return self._build_pdf(title, intro, employee, company, exit_date, exit_type)

    def generate_portabilite_prevoyance(
        self,
        employee: Dict[str, Any],
        company: Dict[str, Any],
        exit_date: str,
        exit_type: str,
    ) -> bytes:
        title = "Attestation de portabilité des droits à la prévoyance"
        intro = "Le présent document atteste des droits à la portabilité en prévoyance."
        return self._build_pdf(title, intro, employee, company, exit_date, exit_type)


portability_generator = PortabilityDocumentGenerator()
