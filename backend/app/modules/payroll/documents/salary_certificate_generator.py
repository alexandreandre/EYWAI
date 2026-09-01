# app/modules/payroll/documents/salary_certificate_generator.py
# Attestation de salaire CPAM (IJ). Hors Cerfa officiels / télétransmission Net-Entreprises.

"""
Attestation de salaire pour le paiement des IJ CPAM.

Maladie / maternité / paternité : salaires rétablis (même logique DSN type 003).
Accident du travail / maladie professionnelle : salaires nets.
Ce n'est pas un Cerfa 11135 / 11137 télétransmis.
"""

from __future__ import annotations

import io
from calendar import monthrange
from datetime import date, datetime
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
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
from app.modules.dsn_export.domain.remuneration_map import (
    build_remunerations_from_payslip,
)
from app.shared.infrastructure.pdf.helpers import (
    format_currency,
    format_date,
    safe_float,
    safe_str,
    setup_custom_styles,
)

KIND_RETABLI = "salaires_retablis"
KIND_NET = "salaires_nets"

_AT_MP_TYPES = frozenset({"arret_at", "arret_maladie_pro"})
_AT_ARRET_TYPES = frozenset({"accident_travail"})


def resolve_cpam_attestation_kind(
    absence_type: str,
    arret_type: Optional[str] = None,
) -> str:
    """AT/MP → nets ; maladie / mat / paternité → rétablis."""
    if (absence_type or "") in _AT_MP_TYPES:
        return KIND_NET
    if (arret_type or "") in _AT_ARRET_TYPES:
        return KIND_NET
    return KIND_RETABLI


def amounts_from_payslip_data(payslip_data: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Extrait brut, net, rétabli (DSN 003) et primes d'un bulletin."""
    data = payslip_data if isinstance(payslip_data, dict) else {}
    brut = safe_float(data.get("salaire_brut", 0))
    net = safe_float(data.get("net_a_payer", 0))
    primes = safe_float(data.get("total_primes", 0))
    retabli = brut
    if data:
        built = build_remunerations_from_payslip(
            data,
            brut=brut,
            period_start="01011900",
            period_end="31011900",
            period="1900-01",
        )
        retabli = float(built.salaire_retabli)
    return {
        "salaire_brut": round(brut, 2),
        "salaire_net": round(net, 2),
        "salaire_retabli": round(retabli, 2),
        "primes": round(primes, 2),
    }


class SalaryCertificateGenerator:
    """Générateur d'attestations de salaire pour arrêts de travail (CPAM)."""

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
        """Rémunération des 3 derniers mois complets avant l'arrêt (brut, rétabli, net)."""
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
            reference_months.append(
                {
                    "year": year,
                    "month": month,
                    "month_name": self._get_month_name(month),
                }
            )
        reference_months.reverse()

        total_brut = 0.0
        total_primes = 0.0
        total_retabli = 0.0
        total_net = 0.0
        for month_info in reference_months:
            payslip = (
                supabase.table("payslips")
                .select("id, month, year, payslip_data")
                .match(
                    {
                        "employee_id": employee_id,
                        "year": month_info["year"],
                        "month": month_info["month"],
                    }
                )
                .maybe_single()
                .execute()
            )
            if payslip and payslip.data:
                amounts = amounts_from_payslip_data(
                    payslip.data.get("payslip_data") or {}
                )
                month_info.update(amounts)
                month_info["brut"] = amounts["salaire_brut"]
                month_info["total"] = amounts["salaire_retabli"]
                month_info["has_payslip"] = True
                total_brut += amounts["salaire_brut"]
                total_primes += amounts["primes"]
                total_retabli += amounts["salaire_retabli"]
                total_net += amounts["salaire_net"]
            else:
                employee = (
                    supabase.table("employees")
                    .select("salaire_de_base")
                    .eq("id", employee_id)
                    .maybe_single()
                    .execute()
                )
                brut = 0.0
                if employee and employee.data:
                    salaire_base = employee.data.get("salaire_de_base") or {}
                    brut = self._safe_float(
                        salaire_base.get("valeur", 0)
                        if isinstance(salaire_base, dict)
                        else salaire_base
                    )
                month_info["salaire_brut"] = brut
                month_info["salaire_retabli"] = brut
                month_info["salaire_net"] = 0.0
                month_info["primes"] = 0.0
                month_info["brut"] = brut
                month_info["total"] = brut
                month_info["has_payslip"] = False
                total_brut += brut
                total_retabli += brut

        months_with_data = sum(
            1
            for m in reference_months
            if m.get("salaire_retabli", 0) or m.get("salaire_net", 0)
        )
        first_month = reference_months[0]
        last_month = reference_months[-1]
        period_start = date(first_month["year"], first_month["month"], 1)
        last_day = monthrange(last_month["year"], last_month["month"])[1]
        period_end = date(last_month["year"], last_month["month"], last_day)
        n = max(months_with_data, 1)
        return {
            "reference_months": reference_months,
            "total_brut": total_brut,
            "total_retabli": total_retabli,
            "total_net": total_net,
            "average_monthly_brut": total_brut / n if months_with_data else 0.0,
            "total_primes": total_primes,
            "total_remuneration": total_retabli,
            "period_start": period_start,
            "period_end": period_end,
            "months_count": months_with_data,
        }

    def _get_month_name(self, month: int) -> str:
        months = [
            "",
            "Janvier",
            "Février",
            "Mars",
            "Avril",
            "Mai",
            "Juin",
            "Juillet",
            "Août",
            "Septembre",
            "Octobre",
            "Novembre",
            "Décembre",
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

    def _absence_bounds(self, absence_data: Dict[str, Any]) -> tuple[date, date]:
        selected_days = absence_data.get("selected_days") or []
        if selected_days:
            dates = []
            for day_str in selected_days:
                if isinstance(day_str, str):
                    dates.append(date.fromisoformat(day_str[:10]))
                else:
                    dates.append(day_str)
            dates.sort()
            return dates[0], dates[-1]
        today = date.today()
        return today, today

    def _kv_table(self, rows: list[list[str]]) -> Table:
        table = Table(rows, colWidths=[5.2 * cm, 11.3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#d1d5db")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
                ]
            )
        )
        return table

    def generate_salary_certificate(
        self,
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        absence_data: Dict[str, Any],
        reference_salary: Dict[str, Any],
    ) -> bytes:
        """Génère l'attestation CPAM (salaires rétablis ou nets selon le motif)."""
        kind = resolve_cpam_attestation_kind(
            str(absence_data.get("type") or ""),
            arret_type=absence_data.get("arret_type"),
        )
        amount_key = "salaire_net" if kind == KIND_NET else "salaire_retabli"
        column_label = "Salaire net" if kind == KIND_NET else "Salaire rétabli"

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=1.4 * cm,
            bottomMargin=1.4 * cm,
            leftMargin=1.6 * cm,
            rightMargin=1.6 * cm,
        )
        story = []
        title_style = ParagraphStyle(
            name="AttestationTitre",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            alignment=TA_CENTER,
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            name="AttestationSousTitre",
            parent=self.styles["Normal"],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#374151"),
            spaceAfter=12,
        )
        section_style = ParagraphStyle(
            name="AttestationSection",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.white,
            alignment=TA_LEFT,
        )
        mention_style = ParagraphStyle(
            name="AttestationMention",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#4b5563"),
            alignment=TA_JUSTIFY,
            spaceBefore=6,
            spaceAfter=8,
        )

        story.append(
            Paragraph(
                "ATTESTATION DE SALAIRE",
                title_style,
            )
        )
        story.append(
            Paragraph(
                "Pour le paiement des indemnités journalières — Assurance maladie",
                subtitle_style,
            )
        )

        raison = self._safe_str(
            company_data.get("raison_sociale")
            or company_data.get("company_name")
            or ""
        )
        ville = self._safe_str(
            company_data.get("adresse_ville") or company_data.get("city") or ""
        )
        adresse = " ".join(
            part
            for part in (
                self._safe_str(company_data.get("adresse_rue") or ""),
                self._safe_str(company_data.get("adresse_code_postal") or ""),
                ville,
            )
            if part
        )
        story.append(self._section_banner("Employeur", section_style))
        story.append(
            self._kv_table(
                [
                    ["Raison sociale :", raison or "Non renseignée"],
                    [
                        "N° SIRET :",
                        self._safe_str(company_data.get("siret") or "Non renseigné"),
                    ],
                    ["Adresse :", adresse or "Non renseignée"],
                ]
            )
        )
        story.append(Spacer(1, 0.45 * cm))

        nom_complet = (
            f"{self._safe_str(employee_data.get('first_name', ''))} "
            f"{self._safe_str(employee_data.get('last_name', ''))}"
        ).strip()
        story.append(self._section_banner("Salarié", section_style))
        story.append(
            self._kv_table(
                [
                    ["Nom et prénom :", nom_complet or "Non renseigné"],
                    [
                        "Date de naissance :",
                        self._format_date(employee_data.get("date_naissance", "")),
                    ],
                    [
                        "N° de Sécurité sociale :",
                        self._safe_str(employee_data.get("nir") or "Non renseigné"),
                    ],
                    [
                        "Date d'embauche :",
                        self._format_date(employee_data.get("hire_date", "")),
                    ],
                    [
                        "Emploi :",
                        self._safe_str(employee_data.get("job_title") or "Non renseigné"),
                    ],
                ]
            )
        )
        story.append(Spacer(1, 0.45 * cm))

        absence_type = absence_data.get("type", "")
        date_debut, date_fin = self._absence_bounds(absence_data)
        story.append(self._section_banner("Arrêt de travail", section_style))
        story.append(
            self._kv_table(
                [
                    ["Nature :", self._get_absence_type_label(str(absence_type))],
                    ["Date de début :", self._format_date(date_debut)],
                    ["Date de fin :", self._format_date(date_fin)],
                ]
            )
        )
        story.append(Spacer(1, 0.45 * cm))

        period_start_str = self._format_date(reference_salary["period_start"])
        period_end_str = self._format_date(reference_salary["period_end"])
        story.append(
            self._section_banner("Rémunération des trois mois de référence", section_style)
        )
        story.append(Spacer(1, 0.15 * cm))
        story.append(
            Paragraph(
                f"Période : du {period_start_str} au {period_end_str}",
                self.styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.2 * cm))

        table_data = [["Mois", column_label]]
        total_amount = 0.0
        months_used = 0
        for month_info in reference_salary.get("reference_months") or []:
            month_name = f"{month_info.get('month_name', '')} {month_info.get('year', '')}"
            amount = self._safe_float(month_info.get(amount_key, 0))
            total_amount += amount
            if amount:
                months_used += 1
            table_data.append([month_name.strip(), self._format_currency(amount)])
        table_data.append(["TOTAL", self._format_currency(total_amount)])

        table_remuneration = Table(table_data, colWidths=[9 * cm, 7.5 * cm])
        table_remuneration.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(table_remuneration)

        if kind == KIND_NET:
            mention = (
                "Les montants indiqués sont les salaires nets des trois mois civils "
                "précédant l'arrêt (accident du travail ou maladie professionnelle)."
            )
        else:
            mention = (
                "Les montants indiqués sont les salaires rétablis des trois mois civils "
                "précédant l'arrêt : rémunération que le salarié aurait perçue en l'absence "
                "d'arrêt ou d'autre absence."
            )
        story.append(Paragraph(mention, mention_style))

        average = total_amount / max(months_used, 1) if months_used else 0.0
        story.append(
            Paragraph(
                f"<b>Moyenne mensuelle ({column_label.lower()}) : "
                f"{self._format_currency(average)}</b>",
                self.styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.8 * cm))
        date_aujourd_hui = self._format_date(datetime.now().date())
        story.append(
            Paragraph(
                f"Fait à {ville or '___________'}, le {date_aujourd_hui}",
                self.styles.get("Signature", self.styles["Normal"]),
            )
        )
        story.append(Spacer(1, 0.25 * cm))
        story.append(
            Paragraph(
                "Signature et cachet de l'employeur :",
                self.styles.get("Signature", self.styles["Normal"]),
            )
        )

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def _section_banner(self, title: str, section_style: ParagraphStyle) -> Table:
        banner = Table(
            [[Paragraph(title.upper(), section_style)]],
            colWidths=[16.5 * cm],
        )
        banner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111827")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return banner
