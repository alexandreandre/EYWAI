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
from app.modules.payroll.solde_de_tout_compte.common import pdf_helpers
from app.modules.payroll.solde_de_tout_compte.common.pdf_helpers import (
    setup_custom_styles,
    format_date,
    format_currency,
    safe_float,
    safe_str,
)

from app.shared.infrastructure.pdf.helpers import (
    format_salary_euros,
    get_company_address,
    get_company_city,
    get_company_signatory,
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

EXIT_TYPE_LABELS = {
    "demission": "Démission",
    "rupture_conventionnelle": "Rupture conventionnelle",
    "licenciement": "Licenciement",
    "depart_retraite": "Départ à la retraite",
    "fin_periode_essai": "Fin de période d'essai",
    "fin_cdd": "Fin de contrat à durée déterminée",
    "fin_mission": "Fin de mission (intérim)",
    "deces": "Décès du salarié",
}


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
        Génère un certificat de travail conforme à l'article L1234-19 du Code du travail.

        Mentions obligatoires :
        - Identité employeur et salarié
        - Dates d'embauche et de cessation
        - Nature de l'emploi (ou emplois successivement occupés)
        - Durée et exécution du préavis le cas échéant
        - Mention « libre de tout engagement »
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm
        )
        story = []

        pdf_helpers.build_company_header(story, self.styles, company_data)

        story.append(Paragraph("CERTIFICAT DE TRAVAIL", self.styles["TitrePrincipal"]))
        story.append(Spacer(1, 0.5 * cm))

        nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
        date_naissance = self._format_date(employee_data.get("date_naissance", ""))
        date_embauche = self._format_date(employee_data.get("hire_date", ""))
        date_sortie = self._format_date(exit_data.get("last_working_day", ""))
        poste = employee_data.get("job_title", "Employé")
        contract_type = employee_data.get("contract_type", "CDI")

        company_name = (
            company_data.get("name")
            or company_data.get("raison_sociale")
            or company_data.get("company_name")
            or "l'entreprise"
        )

        texte_certif = f"""
        Je soussigné(e), représentant(e) légal(e) de <b>{company_name}</b>,
        certifie que :
        """
        story.append(Paragraph(texte_certif, self.styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))

        data_salarie = [
            ["Nom et prénom :", nom_complet],
            ["Né(e) le :", date_naissance or "Non renseigné"],
            ["Emploi occupé :", poste],
            ["Nature du contrat :", contract_type],
            ["Date d'entrée :", date_embauche or "Non renseigné"],
            ["Date de cessation :", date_sortie or "Non renseigné"],
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
        story.append(Spacer(1, 0.6 * cm))

        # Préavis (mention L1234-19 al. c)
        notice_days = exit_data.get("notice_period_days") or 0
        notice_end = exit_data.get("notice_end_date")
        notice_indemnity_type = exit_data.get("notice_indemnity_type", "not_applicable")
        preavis_lines = []
        if notice_days and int(notice_days) > 0:
            preavis_lines.append(
                f"Durée du préavis : <b>{notice_days} jours</b>."
            )
            if notice_end:
                preavis_lines.append(
                    f"Fin de préavis : <b>{self._format_date(notice_end)}</b>."
                )
            if notice_indemnity_type == "waived":
                preavis_lines.append("Préavis non exécuté (dispense accordée).")
            elif notice_indemnity_type == "paid":
                indemnities = exit_data.get("calculated_indemnities") or {}
                montant_preavis = safe_float(
                    (indemnities.get("indemnite_preavis") or {}).get("montant", 0)
                )
                if montant_preavis > 0:
                    from app.shared.infrastructure.pdf.helpers import format_currency

                    preavis_lines.append(
                        f"Indemnité compensatrice de préavis : "
                        f"<b>{format_currency(montant_preavis)}</b>."
                    )
                else:
                    preavis_lines.append(
                        "Préavis non exécuté — indemnité compensatrice de préavis due."
                    )
            else:
                preavis_lines.append("Préavis exécuté ou en cours d'exécution.")
        else:
            preavis_lines.append(
                "Aucun préavis applicable ou durée de préavis non renseignée."
            )

        emplois_text = (
            f"Le salarié a occupé le poste de <b>{poste}</b> "
            f"depuis le {date_embauche or '…'} jusqu'au {date_sortie or '…'}."
        )
        story.append(Paragraph(emplois_text, self.styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                "<b>Préavis :</b> " + " ".join(preavis_lines),
                self.styles["CorpsTexte"],
            )
        )
        story.append(Spacer(1, 0.6 * cm))

        texte_mention = """
        Le présent certificat est délivré à la demande de l'intéressé(e)
        pour servir et valoir ce que de droit, notamment auprès de France Travail
        (ex-Pôle Emploi) et des organismes de protection sociale.
        """
        story.append(Paragraph(texte_mention, self.styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))

        texte_libre = f"""
        <b>{nom_complet}</b> est, à ce jour, <b>libre de tout engagement</b>
        à l'égard de notre société.
        """
        story.append(Paragraph(texte_libre, self.styles["Important"]))
        story.append(Spacer(1, 1.2 * cm))

        company_city = get_company_city(company_data) or "…………………"
        date_aujourd_hui = self._format_date(datetime.now().date())
        story.append(
            Paragraph(
                f"Fait à {company_city}, le {date_aujourd_hui}",
                self.styles["Signature"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        signatory, signatory_title = get_company_signatory(company_data)
        sig = f"<b>{signatory}</b>"
        if signatory_title:
            sig += f"<br/><i>{signatory_title}</i>"
        sig += "<br/>Signature et cachet de l'entreprise"
        story.append(Paragraph(sig, self.styles["Signature"]))
        story.append(Spacer(1, 1.5 * cm))

        story.append(
            Paragraph(
                "<i>Article L1234-19 du Code du travail — Certificat de travail</i>",
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
        Attestation employeur simplifiée pour France Travail.

        Complète le certificat de travail ; l'attestation officielle doit
        impérativement être transmise via la DSN (événement fin de contrat).
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm
        )
        story = []

        pdf_helpers.build_company_header(story, self.styles, company_data)

        story.append(
            Paragraph(
                "<b>ATTESTATION EMPLOYEUR</b><br/>"
                "<i>Document d'accompagnement — France Travail</i>",
                self.styles["TitrePrincipal"],
            )
        )
        story.append(Spacer(1, 0.4 * cm))

        story.append(
            Paragraph(
                "<i>Ce document reprend les informations essentielles transmises au salarié. "
                "L'employeur doit obligatoirement déclarer la fin de contrat via la DSN "
                "(Déclaration Sociale Nominative) dans les délais légaux. "
                "Seule l'attestation transmise par DSN fait foi auprès de France Travail.</i>",
                ParagraphStyle(
                    name="Avertissement",
                    parent=self.styles["Normal"],
                    fontSize=9,
                    textColor=colors.HexColor("#92400e"),
                    spaceAfter=16,
                    alignment=TA_CENTER,
                    borderPadding=8,
                    borderColor=colors.HexColor("#fde68a"),
                    borderWidth=1,
                    backColor=colors.HexColor("#fffbeb"),
                ),
            )
        )
        story.append(Spacer(1, 0.6 * cm))

        story.append(
            Paragraph("<b>1. EMPLOYEUR</b>", self.styles["Important"])
        )
        story.append(Spacer(1, 0.2 * cm))

        company_name = (
            company_data.get("name")
            or company_data.get("raison_sociale")
            or company_data.get("company_name")
            or ""
        )
        data_employeur = [
            ["Raison sociale :", company_name],
            ["SIRET :", company_data.get("siret", "")],
            ["Adresse :", get_company_address(company_data)],
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
        story.append(Spacer(1, 0.6 * cm))

        story.append(Paragraph("<b>2. SALARIÉ</b>", self.styles["Important"]))
        story.append(Spacer(1, 0.2 * cm))

        nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
        data_salarie = [
            ["Nom et prénom :", nom_complet],
            [
                "Date de naissance :",
                self._format_date(employee_data.get("date_naissance", "")),
            ],
            ["N° de Sécurité Sociale :", employee_data.get("nir", "") or "Non renseigné"],
            ["Emploi occupé :", employee_data.get("job_title", "")],
            ["Type de contrat :", employee_data.get("contract_type", "CDI")],
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
        story.append(Spacer(1, 0.6 * cm))

        story.append(
            Paragraph("<b>3. FIN DE CONTRAT</b>", self.styles["Important"])
        )
        story.append(Spacer(1, 0.2 * cm))

        exit_type = exit_data.get("exit_type", "")
        motif = EXIT_TYPE_LABELS.get(exit_type, exit_type.replace("_", " ").title() if exit_type else "Non spécifié")
        story.append(Paragraph(f"Motif de rupture : <b>{motif}</b>", self.styles["CorpsTexte"]))

        if exit_data.get("exit_reason"):
            story.append(
                Paragraph(
                    f"Précisions : {exit_data['exit_reason']}", self.styles["CorpsTexte"]
                )
            )

        notice_days = exit_data.get("notice_period_days") or 0
        if notice_days and int(notice_days) > 0:
            story.append(
                Paragraph(
                    f"Durée du préavis : <b>{notice_days} jours</b>.",
                    self.styles["CorpsTexte"],
                )
            )

        story.append(Spacer(1, 0.5 * cm))

        # Rémunération de référence
        salaire_ref = format_salary_euros(employee_data)
        story.append(
            Paragraph("<b>4. RÉMUNÉRATION DE RÉFÉRENCE</b>", self.styles["Important"])
        )
        story.append(Spacer(1, 0.2 * cm))
        story.append(
            Paragraph(
                f"Dernier salaire brut mensuel connu : <b>{salaire_ref}</b>. "
                "Les indemnités et droits acquis sont détaillés dans le reçu pour solde de tout compte.",
                self.styles["CorpsTexte"],
            )
        )
        story.append(Spacer(1, 1 * cm))

        company_city = get_company_city(company_data) or "…………………"
        date_aujourd_hui = self._format_date(datetime.now().date())
        story.append(
            Paragraph(
                f"Fait à {company_city}, le {date_aujourd_hui}",
                self.styles["Signature"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph("Signature et cachet de l'employeur", self.styles["Signature"])
        )
        story.append(Spacer(1, 1.5 * cm))

        story.append(
            Paragraph(
                "<b>Rappel :</b> la déclaration DSN de fin de contrat est obligatoire. "
                "Ce document ne se substitue pas à l'attestation officielle transmise "
                "électroniquement à France Travail.",
                ParagraphStyle(
                    name="RappelDSN",
                    parent=self.styles["Normal"],
                    fontSize=9,
                    textColor=colors.HexColor("#1e3a8a"),
                    alignment=TA_CENTER,
                    borderPadding=8,
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
