"""
Génération d'attestations de salaire pour les arrêts de travail (Cerfa 11135*04).

Logique migrée depuis services/salary_certificate_generator.py pour autonomie du module.
Utilise app.core.database et app.shared.infrastructure.pdf.helpers (aucun import legacy).
"""
import io
from calendar import monthrange
from datetime import date, datetime
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.database import supabase
from app.shared.infrastructure.pdf.helpers import (
    format_currency,
    format_date,
    safe_float,
    safe_str,
    setup_custom_styles,
)


class SalaryCertificateGenerator:
    """Générateur d'attestations de salaire pour arrêts de travail."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.styles = setup_custom_styles(self.styles)

    def _format_date(self, date_value: Any) -> str:
        return format_date(date_value)

    def _format_currency(self, amount: float) -> str:
        return format_currency(amount)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        return safe_float(value, default)

    def _safe_str(self, value: Any, default: str = "") -> str:
        return safe_str(value, default)

    def get_reference_salary(
        self,
        employee_id: str,
        absence_start_date: date,
    ) -> Dict[str, Any]:
        """Récupère la rémunération de référence (3 derniers mois complets avant l'arrêt)."""
        if absence_start_date.month == 1:
            ref_month_end = 12
            ref_year_end = absence_start_date.year - 1
        else:
            ref_month_end = absence_start_date.month - 1
            ref_year_end = absence_start_date.year

        reference_months = []
        for i in range(3):
            month = ref_month_end - i
            year = ref_year_end
            if month <= 0:
                month += 12
                year -= 1
            reference_months.append({
                "year": year,
                "month": month,
                "month_name": self._get_month_name(month),
            })
        reference_months.reverse()

        total_brut = 0.0
        total_primes = 0.0
        for month_info in reference_months:
            payslip = (
                supabase.table("payslips")
                .select("id, month, year, payslip_data")
                .match({
                    "employee_id": employee_id,
                    "year": month_info["year"],
                    "month": month_info["month"],
                })
                .maybe_single()
                .execute()
            )
            if payslip and payslip.data:
                payslip_data = payslip.data.get("payslip_data", {})
                brut = self._safe_float(payslip_data.get("salaire_brut", 0))
                primes = self._safe_float(payslip_data.get("total_primes", 0))
                month_info["brut"] = brut
                month_info["primes"] = primes
                month_info["total"] = brut + primes
                month_info["has_payslip"] = True
                total_brut += brut
                total_primes += primes
            else:
                employee = (
                    supabase.table("employees")
                    .select("salaire_de_base")
                    .eq("id", employee_id)
                    .maybe_single()
                    .execute()
                )
                if employee and employee.data:
                    salaire_base = employee.data.get("salaire_de_base", {})
                    brut = self._safe_float(salaire_base.get("valeur", 0))
                    month_info["brut"] = brut
                    month_info["primes"] = 0.0
                    month_info["total"] = brut
                    month_info["has_payslip"] = False
                    total_brut += brut
                else:
                    month_info["brut"] = 0.0
                    month_info["primes"] = 0.0
                    month_info["total"] = 0.0
                    month_info["has_payslip"] = False

        months_with_data = sum(
            1 for m in reference_months if m.get("total", 0) > 0
        )
        average_monthly_brut = (
            total_brut / max(months_with_data, 1) if months_with_data > 0 else 0.0
        )
        first_month = reference_months[0]
        last_month = reference_months[-1]
        period_start = date(first_month["year"], first_month["month"], 1)
        last_day = monthrange(last_month["year"], last_month["month"])[1]
        period_end = date(
            last_month["year"], last_month["month"], last_day
        )
        return {
            "reference_months": reference_months,
            "total_brut": total_brut,
            "average_monthly_brut": average_monthly_brut,
            "total_primes": total_primes,
            "total_remuneration": total_brut + total_primes,
            "period_start": period_start,
            "period_end": period_end,
            "months_count": months_with_data,
        }

    def _get_month_name(self, month: int) -> str:
        months = [
            "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
        ]
        return months[month] if 1 <= month <= 12 else ""

    def _get_absence_type_label(self, absence_type: str) -> str:
        labels = {
            "arret_maladie": "Arrêt maladie",
            "arret_at": "Accident du travail",
            "arret_paternite": "Congé paternité",
            "arret_maternite": "Congé maternité",
            "arret_maladie_pro": "Maladie professionnelle",
        }
        return labels.get(absence_type, "Arrêt de travail")

    def generate_salary_certificate(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        absence_data: Dict[str, Any],
        reference_salary: Dict[str, Any],
    ) -> bytes:
        """Génère une attestation de salaire conforme au formulaire Cerfa 11135*04."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
        )
        story = []

        company_name = (
            company_data.get("name")
            or company_data.get("raison_sociale", "Entreprise")
        )
        story.append(
            Paragraph(
                f"<b>{company_name}</b>",
                self.styles["EntrepriseHeader"],
            )
        )
        if company_data.get("address"):
            story.append(
                Paragraph(
                    company_data["address"],
                    self.styles["Normal"],
                )
            )
        if company_data.get("siret"):
            story.append(
                Paragraph(
                    f"SIRET : {company_data['siret']}",
                    self.styles["Normal"],
                )
            )
        story.append(Spacer(1, 1 * cm))

        story.append(
            Paragraph(
                "<b>ATTESTATION DE SALAIRE</b>",
                self.styles["TitrePrincipal"],
            )
        )
        story.append(
            Paragraph(
                "<i>Pour le paiement des indemnités journalières</i>",
                ParagraphStyle(
                    name="SousTitre",
                    parent=self.styles["Normal"],
                    fontSize=10,
                    alignment=TA_CENTER,
                    spaceAfter=20,
                ),
            )
        )
        story.append(Spacer(1, 0.8 * cm))

        story.append(
            Paragraph(
                "<b>INFORMATIONS SALARIÉ</b>",
                self.styles["Important"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        nom_complet = f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}"
        date_naissance = self._format_date(employee_data.get("date_naissance", ""))
        nir = employee_data.get("nir", "Non renseigné")
        date_embauche = self._format_date(employee_data.get("hire_date", ""))
        poste = employee_data.get("job_title", "Non renseigné")
        data_salarie = [
            ["Nom et prénom :", nom_complet],
            ["Date de naissance :", date_naissance],
            ["N° de Sécurité Sociale :", nir],
            ["Poste occupé :", poste],
            ["Date d'embauche :", date_embauche],
        ]
        table_salarie = Table(data_salarie, colWidths=[5 * cm, 11 * cm])
        table_salarie.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(table_salarie)
        story.append(Spacer(1, 0.8 * cm))

        story.append(
            Paragraph(
                "<b>INFORMATIONS SUR L'ARRÊT</b>",
                self.styles["Important"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        absence_type = absence_data.get("type", "")
        absence_label = self._get_absence_type_label(absence_type)
        selected_days = absence_data.get("selected_days", [])
        if selected_days:
            dates = []
            for day_str in selected_days:
                if isinstance(day_str, str):
                    dates.append(date.fromisoformat(day_str))
                else:
                    dates.append(day_str)
            dates.sort()
            date_debut = dates[0]
            date_fin = dates[-1]
        else:
            date_debut = date.today()
            date_fin = date.today()
        data_arret = [
            ["Type d'arrêt :", absence_label],
            ["Date de début :", self._format_date(date_debut)],
            ["Date de fin :", self._format_date(date_fin)],
        ]
        table_arret = Table(data_arret, colWidths=[5 * cm, 11 * cm])
        table_arret.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(table_arret)
        story.append(Spacer(1, 0.8 * cm))

        story.append(
            Paragraph(
                "<b>RÉMUNÉRATION DE RÉFÉRENCE</b>",
                self.styles["Important"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        period_start_str = self._format_date(reference_salary["period_start"])
        period_end_str = self._format_date(reference_salary["period_end"])
        story.append(
            Paragraph(
                f"Période de référence : du {period_start_str} au {period_end_str}",
                self.styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))

        table_data = [["Mois", "Salaire brut", "Primes", "Total"]]
        for month_info in reference_salary["reference_months"]:
            month_name = f"{month_info['month_name']} {month_info['year']}"
            brut_str = self._format_currency(month_info.get("brut", 0))
            primes_str = self._format_currency(month_info.get("primes", 0))
            total_str = self._format_currency(month_info.get("total", 0))
            table_data.append([month_name, brut_str, primes_str, total_str])
        total_brut_str = self._format_currency(reference_salary["total_brut"])
        total_primes_str = self._format_currency(reference_salary["total_primes"])
        total_remuneration_str = self._format_currency(
            reference_salary["total_remuneration"]
        )
        table_data.append([
            "<b>TOTAL</b>",
            f"<b>{total_brut_str}</b>",
            f"<b>{total_primes_str}</b>",
            f"<b>{total_remuneration_str}</b>",
        ])
        table_remuneration = Table(
            table_data,
            colWidths=[4 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm],
        )
        table_remuneration.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTSIZE", (0, 1), (-1, -2), 9),
                ("FONTSIZE", (0, -1), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 1), (-1, -2), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(table_remuneration)
        story.append(Spacer(1, 0.5 * cm))
        average_str = self._format_currency(
            reference_salary["average_monthly_brut"]
        )
        story.append(
            Paragraph(
                f"<b>Rémunération mensuelle moyenne : {average_str}</b>",
                self.styles["Normal"],
            )
        )
        story.append(Spacer(1, 1 * cm))
        story.append(
            Paragraph(
                "Le présent document est établi pour permettre le calcul des indemnités journalières "
                "par la Caisse Primaire d'Assurance Maladie (CPAM).",
                ParagraphStyle(
                    name="MentionLegale",
                    parent=self.styles["Normal"],
                    fontSize=9,
                    textColor=colors.HexColor("#6b7280"),
                    alignment=TA_JUSTIFY,
                ),
            )
        )
        story.append(Spacer(1, 1.5 * cm))
        date_aujourd_hui = self._format_date(datetime.now().date())
        story.append(
            Paragraph(
                f"Fait à {company_data.get('city', '___________')}, le {date_aujourd_hui}",
                self.styles["Signature"],
            )
        )
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                "Signature et cachet de l'employeur :",
                self.styles["Signature"],
            )
        )
        story.append(Spacer(1, 2 * cm))
        story.append(
            Paragraph(
                "<i>Formulaire Cerfa 11135*04 - Attestation de salaire pour le paiement des indemnités journalières</i>",
                ParagraphStyle(
                    name="PiedPage",
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
