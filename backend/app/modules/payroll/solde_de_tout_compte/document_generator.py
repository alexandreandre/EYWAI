"""
Service de génération automatique de documents PDF pour les sorties de salariés
Génère : certificat de travail, attestation Pôle Emploi, solde de tout compte
"""

import io
from datetime import datetime
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

# Import shared helpers
from app.modules.payroll.solde_de_tout_compte.common.pdf_helpers import (
    setup_custom_styles,
    format_date,
    format_currency,
    safe_float,
    safe_str,
)

# Import case modules
from app.modules.payroll.solde_de_tout_compte.cases.demission import (
    generate_demission_solde,
)
from app.modules.payroll.solde_de_tout_compte.cases.rupture_conventionnelle import (
    generate_rupture_conventionnelle_solde,
)
from app.modules.payroll.solde_de_tout_compte.cases.licenciement import (
    generate_licenciement_solde,
)
from app.modules.payroll.solde_de_tout_compte.cases.retraite import (
    generate_retraite_solde,
)
from app.modules.payroll.solde_de_tout_compte.cases.fin_periode_essai import (
    generate_fin_periode_essai_solde,
)
from app.modules.payroll.solde_de_tout_compte.cases.generic import (
    generate_generic_solde,
)


class EmployeeExitDocumentGenerator:
    """Générateur de documents PDF pour les sorties de salariés"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.styles = setup_custom_styles(self.styles)

    def _format_date(self, date_value: Any) -> str:
        """Formate une date en français (méthode wrapper pour compatibilité)"""
        return format_date(date_value)

    def _format_currency(self, amount: float) -> str:
        """Formate un montant en euros (méthode wrapper pour compatibilité)"""
        return format_currency(amount)

    def generate_certificat_travail(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
    ) -> bytes:
        """
        Génère un certificat de travail conforme à l'Article L1234-19 du Code du travail

        Contenu obligatoire :
        - Nom et adresse de l'entreprise
        - Nom, prénom, date de naissance du salarié
        - Dates d'embauche et de sortie
        - Nature de l'emploi
        - Mention "libre de tout engagement"
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm
        )
        story = []

        # En-tête entreprise
        story.append(
            Paragraph(
                f"<b>{company_data.get('name', company_data.get('raison_sociale', 'Entreprise'))}</b>",
                self.styles["EntrepriseHeader"],
            )
        )

        if company_data.get("address"):
            story.append(
                Paragraph(company_data["address"], self.styles["EntrepriseHeader"])
            )

        if company_data.get("siret"):
            story.append(
                Paragraph(
                    f"SIRET : {company_data['siret']}", self.styles["EntrepriseHeader"]
                )
            )

        story.append(Spacer(1, 1 * cm))

        # Titre
        story.append(Paragraph("CERTIFICAT DE TRAVAIL", self.styles["TitrePrincipal"]))
        story.append(Spacer(1, 0.8 * cm))

        # Informations du salarié
        nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
        date_naissance = self._format_date(employee_data.get("date_naissance", ""))
        date_embauche = self._format_date(employee_data.get("hire_date", ""))
        date_sortie = self._format_date(exit_data.get("last_working_day", ""))
        poste = employee_data.get("job_title", "Employé")

        company_name = (
            company_data.get("name")
            or company_data.get("raison_sociale")
            or "l'entreprise"
        )
        texte_certif = f"""
        Je soussigné(e), représentant(e) de <b>{company_name}</b>,
        certifie avoir employé :
        """
        story.append(Paragraph(texte_certif, self.styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))

        # Informations du salarié en tableau
        data_salarie = [
            ["Nom et Prénom :", nom_complet],
            ["Né(e) le :", date_naissance],
            ["Poste occupé :", poste],
            ["Date d'entrée :", date_embauche],
            ["Date de sortie :", date_sortie],
        ]

        table = Table(data_salarie, colWidths=[5 * cm, 10 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        story.append(table)
        story.append(Spacer(1, 0.8 * cm))

        # Mention légale obligatoire
        texte_mention = """
        Le présent certificat est délivré pour servir et valoir ce que de droit,
        notamment auprès de Pôle Emploi.
        """
        story.append(Paragraph(texte_mention, self.styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))

        texte_libre = f"""
        <b>{nom_complet}</b> est libre de tout engagement à l'égard de notre société.
        """
        story.append(Paragraph(texte_libre, self.styles["Important"]))
        story.append(Spacer(1, 1.5 * cm))

        # Date et signature
        date_aujourd_hui = self._format_date(datetime.now().date())
        story.append(
            Paragraph(
                f"Fait à {company_data.get('city', '___________')}, le {date_aujourd_hui}",
                self.styles["Signature"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph("Signature et cachet de l'entreprise :", self.styles["Signature"])
        )
        story.append(Spacer(1, 2 * cm))

        # Pied de page avec mention légale
        story.append(Spacer(1, 1 * cm))
        story.append(
            Paragraph(
                "<i>Article L1234-19 du Code du travail</i>",
                ParagraphStyle(
                    name="MentionLegale",
                    parent=self.styles["Normal"],
                    fontSize=8,
                    textColor=colors.HexColor("#9ca3af"),
                    alignment=TA_CENTER,
                ),
            )
        )

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Convertit une valeur en float de manière sécurisée (méthode wrapper pour compatibilité)"""
        return safe_float(value, default)

    def _safe_str(self, value: Any, default: str = "") -> str:
        """Convertit une valeur en string de manière sécurisée (méthode wrapper pour compatibilité)"""
        return safe_str(value, default)

    def _get_salary_prorata(
        self, employee_data: Dict[str, Any], exit_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calcule le prorata du salaire du dernier mois (méthode wrapper pour compatibilité)"""
        from app.modules.payroll.solde_de_tout_compte.common.socle_commun import (
            get_salary_prorata,
        )

        return get_salary_prorata(employee_data, exit_data)

    def generate_solde_tout_compte(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
        indemnities: Dict[str, Any],
        supabase_client=None,
    ) -> bytes:
        """
        Génère un reçu pour solde de tout compte conforme au droit du travail français

        Dispatches to case-specific modules based on exit_type.
        TOUTES les lignes sont affichées, même si les données sont manquantes
        """
        exit_type = exit_data.get("exit_type", "demission")

        # Dispatch to case-specific modules
        if exit_type == "demission":
            return generate_demission_solde(
                self.styles,
                employee_data,
                company_data,
                exit_data,
                indemnities,
                supabase_client,
            )
        elif exit_type == "rupture_conventionnelle":
            return generate_rupture_conventionnelle_solde(
                self.styles,
                employee_data,
                company_data,
                exit_data,
                indemnities,
                supabase_client,
            )
        elif exit_type == "licenciement":
            return generate_licenciement_solde(
                self.styles,
                employee_data,
                company_data,
                exit_data,
                indemnities,
                supabase_client,
            )
        elif exit_type == "depart_retraite":
            return generate_retraite_solde(
                self.styles,
                employee_data,
                company_data,
                exit_data,
                indemnities,
                supabase_client,
            )
        elif exit_type == "fin_periode_essai":
            return generate_fin_periode_essai_solde(
                self.styles,
                employee_data,
                company_data,
                exit_data,
                indemnities,
                supabase_client,
            )
        else:
            return generate_generic_solde(
                self.styles, employee_data, company_data, exit_data, indemnities
            )

    def generate_attestation_pole_emploi(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        exit_data: Dict[str, Any],
    ) -> bytes:
        """
        Génère une attestation Pôle Emploi simplifiée

        Note: En production, il faudrait utiliser le formulaire officiel Pôle Emploi
        ou l'API DSN (Déclaration Sociale Nominative)
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm
        )
        story = []

        # En-tête
        story.append(
            Paragraph(
                "<b>ATTESTATION DESTINÉE À PÔLE EMPLOI</b>",
                self.styles["TitrePrincipal"],
            )
        )
        story.append(Spacer(1, 0.5 * cm))

        # Avertissement
        story.append(
            Paragraph(
                "<i>Ce document est une attestation simplifiée. "
                "L'employeur doit obligatoirement transmettre l'attestation officielle via la DSN "
                "(Déclaration Sociale Nominative) ou le formulaire Pôle Emploi.</i>",
                ParagraphStyle(
                    name="Avertissement",
                    parent=self.styles["Normal"],
                    fontSize=9,
                    textColor=colors.HexColor("#dc2626"),
                    spaceAfter=20,
                    alignment=TA_CENTER,
                    borderPadding=10,
                    borderColor=colors.HexColor("#fee2e2"),
                    borderWidth=1,
                    backColor=colors.HexColor("#fef2f2"),
                ),
            )
        )
        story.append(Spacer(1, 1 * cm))

        # Section employeur
        story.append(
            Paragraph("<b>INFORMATIONS EMPLOYEUR</b>", self.styles["Important"])
        )
        story.append(Spacer(1, 0.3 * cm))

        data_employeur = [
            [
                "Raison sociale :",
                company_data.get("name", company_data.get("raison_sociale", "")),
            ],
            ["SIRET :", company_data.get("siret", "")],
            ["Adresse :", company_data.get("address", "")],
        ]

        table_employeur = Table(data_employeur, colWidths=[5 * cm, 11 * cm])
        table_employeur.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table_employeur)
        story.append(Spacer(1, 0.8 * cm))

        # Section salarié
        story.append(Paragraph("<b>INFORMATIONS SALARIÉ</b>", self.styles["Important"]))
        story.append(Spacer(1, 0.3 * cm))

        nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
        data_salarie = [
            ["Nom et prénom :", nom_complet],
            [
                "Date de naissance :",
                self._format_date(employee_data.get("date_naissance", "")),
            ],
            ["N° de Sécurité Sociale :", employee_data.get("nir", "")],
            ["Emploi occupé :", employee_data.get("job_title", "")],
            [
                "Date d'embauche :",
                self._format_date(employee_data.get("hire_date", "")),
            ],
            [
                "Date de fin de contrat :",
                self._format_date(exit_data.get("last_working_day", "")),
            ],
        ]

        table_salarie = Table(data_salarie, colWidths=[5 * cm, 11 * cm])
        table_salarie.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table_salarie)
        story.append(Spacer(1, 0.8 * cm))

        # Motif de fin de contrat
        story.append(
            Paragraph("<b>MOTIF DE FIN DE CONTRAT</b>", self.styles["Important"])
        )
        story.append(Spacer(1, 0.3 * cm))

        motif_map = {
            "demission": "Démission",
            "rupture_conventionnelle": "Rupture conventionnelle",
            "licenciement": "Licenciement",
        }

        motif = motif_map.get(exit_data.get("exit_type", ""), "Non spécifié")
        story.append(Paragraph(f"Motif : <b>{motif}</b>", self.styles["CorpsTexte"]))

        if exit_data.get("exit_reason"):
            story.append(
                Paragraph(
                    f"Détails : {exit_data['exit_reason']}", self.styles["CorpsTexte"]
                )
            )

        story.append(Spacer(1, 1.5 * cm))

        # Signature
        date_aujourd_hui = self._format_date(datetime.now().date())
        story.append(
            Paragraph(
                f"Fait à {company_data.get('city', '___________')}, le {date_aujourd_hui}",
                self.styles["Signature"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph("Signature et cachet de l'employeur", self.styles["Signature"])
        )

        story.append(Spacer(1, 2 * cm))

        # Pied de page avec rappel DSN
        story.append(
            Paragraph(
                "<b>RAPPEL IMPORTANT :</b> Cette attestation ne remplace pas l'attestation officielle "
                "qui doit être transmise obligatoirement par DSN ou via le site de Pôle Emploi.",
                ParagraphStyle(
                    name="RappelDSN",
                    parent=self.styles["Normal"],
                    fontSize=9,
                    textColor=colors.HexColor("#1e3a8a"),
                    alignment=TA_CENTER,
                    borderPadding=10,
                    borderColor=colors.HexColor("#dbeafe"),
                    borderWidth=1,
                    backColor=colors.HexColor("#eff6ff"),
                ),
            )
        )

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes
