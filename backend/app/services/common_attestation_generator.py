"""
Génération PDF ReportLab pour attestations courantes (modèle EYWAI sans template client).
"""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_reportlab,
    get_company_city,
    get_company_signatory,
)


def _s(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _fmt_date_fr(v: Any) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        return v.date().strftime("%d/%m/%Y")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10]).strftime("%d/%m/%Y")
        except ValueError:
            return v
    return _s(v)


def _fmt_euros_amount(v: Any) -> str:
    if v is None or v == "":
        return "—"
    try:
        if isinstance(v, dict):
            inner = v.get("valeur", v.get("amount"))
            return _fmt_euros_amount(inner)
        if isinstance(v, Decimal):
            n = float(v)
        elif isinstance(v, (int, float)):
            n = float(v)
        else:
            n = float(str(v).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError, InvalidOperation):
        return _s(v)
    whole, frac = f"{abs(n):.2f}".split(".")
    int_str = f"{int(whole):,}".replace(",", " ")
    sign = "-" if n < 0 else ""
    return f"{sign}{int_str},{frac} €"


def _company_name(c: Dict[str, Any]) -> str:
    return _s(c.get("raison_sociale") or c.get("company_name") or c.get("name") or "Entreprise")


def _company_address(c: Dict[str, Any]) -> str:
    parts: List[str] = []
    rue = c.get("adresse_rue") or c.get("address_line1")
    cp = c.get("adresse_code_postal") or c.get("postal_code")
    ville = c.get("adresse_ville") or c.get("city")
    if rue:
        parts.append(_s(rue))
    line2 = " ".join(x for x in (_s(cp), _s(ville)) if x)
    if line2:
        parts.append(line2)
    if parts:
        return ", ".join(parts)
    return _s(c.get("address") or c.get("adresse") or c.get("full_address"))


def _employee_civilite(e: Dict[str, Any]) -> str:
    g = (e.get("gender") or e.get("civilite") or "").lower()
    if g in ("f", "femme", "female", "mme", "madame"):
        return "Mme"
    if g in ("m", "homme", "male", "monsieur"):
        return "M."
    return "M./Mme"


def _salaire_mensuel_str(e: Dict[str, Any]) -> str:
    return _fmt_euros_amount(e.get("salaire_de_base"))


def _salaire_annuel_str(e: Dict[str, Any]) -> str:
    sb = e.get("salaire_de_base")
    val = None
    if isinstance(sb, dict):
        val = sb.get("valeur", sb.get("amount"))
    elif sb is not None:
        val = sb
    if val is None or val == "":
        return "—"
    try:
        monthly = float(str(val).replace(",", ".").replace(" ", ""))
        return _fmt_euros_amount(monthly * 12.0)
    except (ValueError, TypeError):
        return "—"


def _temps_travail_label(e: Dict[str, Any]) -> str:
    h = e.get("duree_hebdomadaire") or e.get("weekly_hours")
    try:
        fh = float(h) if h is not None else 35.0
        return "partiel" if fh < 35 else "plein"
    except (TypeError, ValueError):
        return "plein"


def _anciennete_annees(e: Dict[str, Any]) -> str:
    hd = e.get("hire_date") or e.get("date_debut_contrat")
    d0 = None
    if isinstance(hd, str) and hd:
        try:
            d0 = date.fromisoformat(hd[:10])
        except ValueError:
            return "—"
    elif isinstance(hd, (date, datetime)):
        d0 = hd.date() if isinstance(hd, datetime) else hd
    if not d0:
        return "—"
    delta = date.today().year - d0.year
    if (date.today().month, date.today().day) < (d0.month, d0.day):
        delta -= 1
    return str(max(0, delta))


def _titre_attestation(attestation_type: str) -> str:
    return {
        "attestation_emploi": "Attestation d'emploi",
        "attestation_presence": "Attestation de présence",
        "attestation_anciennete": "Attestation d'ancienneté",
        "attestation_poste": "Attestation de poste",
        "attestation_salaire": "Attestation de salaire",
        "attestation_revenus": "Attestation de revenus annuels",
        "attestation_location": "Attestation employeur pour location",
        "attestation_pret": "Attestation pour prêt bancaire",
        "attestation_retraite": "Attestation retraite",
    }.get(attestation_type, "Attestation")


class CommonAttestationGenerator:
    """PDF simples (ReportLab) pour attestations sans template client."""

    ATTESTATION_TYPES: List[str] = [
        "attestation_emploi",
        "attestation_presence",
        "attestation_anciennete",
        "attestation_poste",
        "attestation_salaire",
        "attestation_revenus",
        "attestation_location",
        "attestation_pret",
        "attestation_retraite",
    ]

    def __init__(self) -> None:
        self._types_set = frozenset(self.ATTESTATION_TYPES)

    def generate(
        self,
        attestation_type: str,
        employee: Dict[str, Any],
        company: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> bytes:
        if attestation_type not in self._types_set:
            raise ValueError(f"Type d'attestation non pris en charge : {attestation_type}")
        ctx = context or {}
        body = self._corps(attestation_type, employee, company, ctx)
        return self._build_pdf(employee, company, attestation_type, body)

    def _corps(
        self,
        attestation_type: str,
        e: Dict[str, Any],
        c: Dict[str, Any],
        ctx: Dict[str, Any],
    ) -> str:
        civ = _employee_civilite(e)
        prenom = _s(e.get("first_name") or e.get("prenom"))
        nom = _s(e.get("last_name") or e.get("nom"))
        poste = _s(e.get("job_title") or e.get("poste")) or "—"
        deb = _fmt_date_fr(e.get("hire_date") or e.get("date_debut_contrat"))
        type_ct = _s(e.get("contract_type") or e.get("type_contrat")) or "—"
        date_gen = _fmt_date_fr(ctx.get("date_generation")) or date.today().strftime("%d/%m/%Y")
        sal_m = _salaire_mensuel_str(e)
        sal_a = _salaire_annuel_str(e)
        annee = str(date.today().year)
        anc = _anciennete_annees(e)
        temps = _temps_travail_label(e)
        entreprise = _company_name(c)

        intro = (
            f"Nous soussignés, <b>{entreprise}</b>, attestons que {civ} "
            f"<b>{prenom} {nom}</b>, "
        )

        if attestation_type == "attestation_emploi":
            return (
                intro
                + f"est employé(e) en qualité de <b>{poste}</b> depuis le <b>{deb}</b> "
                f"en contrat <b>{type_ct}</b>."
            )

        if attestation_type == "attestation_presence":
            return (
                intro
                + f"est présent(e) dans nos effectifs à la date du <b>{date_gen}</b>."
            )

        if attestation_type == "attestation_anciennete":
            return (
                intro
                + f"justifie d'une ancienneté de <b>{anc} année(s)</b> au sein de notre entreprise "
                f"depuis le <b>{deb}</b>."
            )

        if attestation_type == "attestation_poste":
            return (
                intro
                + f"occupe le poste de <b>{poste}</b> depuis le <b>{deb}</b>."
            )

        if attestation_type == "attestation_salaire":
            return (
                intro
                + f"perçoit une rémunération brute mensuelle de <b>{sal_m}</b>."
            )

        if attestation_type == "attestation_revenus":
            return (
                intro
                + f"a perçu un salaire brut annuel de <b>{sal_a}</b> au cours de l'exercice <b>{annee}</b>."
            )

        if attestation_type == "attestation_location":
            return (
                intro
                + f"est employé(e) à temps <b>{temps}</b> et perçoit un salaire brut mensuel de "
                f"<b>{sal_m}</b>. Cette attestation est établie à la demande de l'intéressé(e) "
                "pour valoir ce que de droit."
            )

        if attestation_type == "attestation_pret":
            return (
                intro
                + f"est employé(e) à temps <b>{temps}</b> et perçoit un salaire brut mensuel de "
                f"<b>{sal_m}</b>. La présente attestation est établie pour constituer un dossier de "
                "<b>prêt bancaire</b>, pour valoir ce que de droit."
            )

        if attestation_type == "attestation_retraite":
            return self._generate_attestation_retraite_corps(
                civ, prenom, nom, poste, deb, anc, sal_m, sal_a
            )

        return intro + "."

    def _generate_attestation_retraite_corps(
        self,
        civ: str,
        prenom: str,
        nom: str,
        poste: str,
        deb: str,
        anc: str,
        sal_m: str,
        sal_a: str,
    ) -> str:
        """Corps PDF attestation retraite (droits acquis)."""
        return (
            f"Nous attestons que {civ} <b>{prenom} {nom}</b>, employé(e) en qualité de <b>{poste}</b> "
            f"depuis le <b>{deb}</b>, a acquis les droits suivants au sein de notre entreprise :<br/><br/>"
            f"— Ancienneté : <b>{anc} année(s)</b><br/>"
            f"— Salaire brut mensuel : <b>{sal_m}</b><br/>"
            f"— Salaire brut annuel : <b>{sal_a}</b><br/><br/>"
            "Cette attestation est établie à la demande de l'intéressé(e) pour faire valoir ses droits "
            "à la retraite."
        )

    def _build_pdf(
        self,
        employee: Dict[str, Any],
        company: Dict[str, Any],
        attestation_type: str,
        corps_html: str,
    ) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="AttTitle",
            parent=styles["Heading1"],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=16,
            textColor=colors.HexColor("#1e293b"),
        )
        body_style = ParagraphStyle(
            name="AttBody",
            parent=styles["Normal"],
            fontSize=11,
            leading=16,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#334155"),
        )
        small_style = ParagraphStyle(
            name="AttSmall",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b"),
        )
        story: List[Any] = []
        build_branding_header_reportlab(story, styles, company)
        story.append(Paragraph(_titre_attestation(attestation_type), title_style))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(corps_html, body_style))
        story.append(Spacer(1, 0.8 * cm))
        story.append(
            Paragraph(
                "La présente attestation est délivrée à la demande de l'intéressé(e) "
                "pour servir et valoir ce que de droit.",
                body_style,
            )
        )
        story.append(Spacer(1, 0.8 * cm))
        lieu = get_company_city(company) or "…………………"
        story.append(
            Paragraph(
                f"Fait à {lieu}, le {date.today().strftime('%d/%m/%Y')}.",
                small_style,
            )
        )
        story.append(Spacer(1, 1.5 * cm))
        rh, qual = get_company_signatory(company)
        sig_line = f"<b>{rh}</b>" + (f"<br/><i>{qual}</i>" if qual else "")
        story.append(Paragraph(sig_line, body_style))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("<i>Signature RH</i>", small_style))
        doc.build(story)
        return buf.getvalue()


common_attestation_generator = CommonAttestationGenerator()
