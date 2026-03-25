"""
Génération et stockage des documents PDF de promotion.

Implémentation autonome sous app/* : utilise app.core.database et
app.shared.infrastructure.pdf.helpers. Aucune dépendance legacy (services/*, core/* racine).
Comportement identique au legacy services.promotion_document_service.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.database import supabase
from app.shared.infrastructure.pdf.helpers import (
    format_currency,
    format_date as format_date_fr,
    safe_float,
    safe_str,
    setup_custom_styles,
)


def generate_promotion_letter(
    promotion_data: Dict[str, Any],
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    logo_path: Optional[str] = None,
) -> bytes:
    """
    Génère un document PDF de promotion professionnel.

    Comportement identique au legacy promotion_document_service.generate_promotion_letter.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story = []
    styles = getSampleStyleSheet()
    styles = setup_custom_styles(styles)

    styles.add(
        ParagraphStyle(
            name="PromotionTitle",
            parent=styles["TitrePrincipal"],
            fontSize=18,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="ComparisonLabel",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#4b5563"),
            spaceAfter=4,
            alignment=TA_LEFT,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="ComparisonValue",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.black,
            spaceAfter=8,
            alignment=TA_LEFT,
        )
    )

    if company_data:
        company_name = (
            company_data.get("company_name")
            or company_data.get("raison_sociale")
            or "Entreprise"
        )
        address_data = company_data.get("address") or company_data.get("adresse")
        company_street = ""
        company_city = ""
        company_postal_code = ""
        if address_data:
            if isinstance(address_data, dict):
                company_street = address_data.get("street", "") or address_data.get("rue", "")
                company_city = address_data.get("city", "") or address_data.get("ville", "")
                company_postal_code = (
                    address_data.get("postal_code", "") or address_data.get("code_postal", "")
                )
            elif isinstance(address_data, str):
                company_street = address_data
        if not company_street:
            company_street = company_data.get("adresse_rue", "") or company_data.get("street", "")
        if not company_city:
            company_city = company_data.get("adresse_ville", "") or company_data.get("city", "")
        if not company_postal_code:
            company_postal_code = (
                company_data.get("adresse_code_postal", "")
                or company_data.get("postal_code", "")
            )
        company_info = company_name
        if company_street:
            company_info += f"\n{company_street}"
        if company_postal_code or company_city:
            company_info += f"\n{company_postal_code} {company_city}".strip()
        story.append(Paragraph(company_info, styles["EntrepriseHeader"]))
        story.append(Spacer(1, 0.8 * cm))

    story.append(Paragraph("LETTRE DE PROMOTION", styles["PromotionTitle"]))
    story.append(Spacer(1, 0.5 * cm))

    today = datetime.now().date()
    employee_name = (
        f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}".strip()
    )
    date_and_recipient = f"""
    <b>Date :</b> {format_date_fr(today)}<br/>
    <b>À l'attention de :</b> {employee_name}
    """
    story.append(Paragraph(date_and_recipient, styles["CorpsTexte"]))
    story.append(Spacer(1, 0.8 * cm))

    intro_text = f"""
    <b>Objet : Promotion et évolution de carrière</b><br/><br/>

    Madame, Monsieur {employee_data.get('last_name', '')},<br/><br/>

    Nous avons le plaisir de vous informer de votre promotion au sein de notre entreprise.
    """
    story.append(Paragraph(intro_text, styles["CorpsTexte"]))
    story.append(Spacer(1, 0.5 * cm))

    promotion_data.get("promotion_type", "mixte")
    comparison_data = []

    if promotion_data.get("new_job_title") or promotion_data.get("previous_job_title"):
        previous_job = promotion_data.get("previous_job_title") or "Non renseigné"
        new_job = promotion_data.get("new_job_title") or "Non renseigné"
        comparison_data.append([
            Paragraph("<b>Poste</b>", styles["ComparisonLabel"]),
            Paragraph(safe_str(previous_job), styles["ComparisonValue"]),
            Paragraph("→", styles["ComparisonValue"]),
            Paragraph(safe_str(new_job), styles["ComparisonValue"]),
        ])

    if promotion_data.get("new_salary") or promotion_data.get("previous_salary"):
        previous_salary = promotion_data.get("previous_salary", {})
        new_salary = promotion_data.get("new_salary", {})
        prev_value = previous_salary.get("valeur") if isinstance(previous_salary, dict) else None
        new_value = new_salary.get("valeur") if isinstance(new_salary, dict) else None
        if prev_value or new_value:
            prev_str = (
                format_currency(safe_float(prev_value)) if prev_value else "Non renseigné"
            )
            new_str = format_currency(safe_float(new_value)) if new_value else "Non renseigné"
            increase_pct = ""
            if prev_value and new_value and prev_value > 0:
                pct = ((new_value - prev_value) / prev_value) * 100
                increase_pct = f" (+{pct:.1f}%)"
            comparison_data.append([
                Paragraph("<b>Salaire mensuel brut</b>", styles["ComparisonLabel"]),
                Paragraph(prev_str, styles["ComparisonValue"]),
                Paragraph("→", styles["ComparisonValue"]),
                Paragraph(f"{new_str}{increase_pct}", styles["ComparisonValue"]),
            ])

    if promotion_data.get("new_statut") or promotion_data.get("previous_statut"):
        previous_statut = promotion_data.get("previous_statut") or "Non renseigné"
        new_statut = promotion_data.get("new_statut") or "Non renseigné"
        comparison_data.append([
            Paragraph("<b>Statut</b>", styles["ComparisonLabel"]),
            Paragraph(safe_str(previous_statut), styles["ComparisonValue"]),
            Paragraph("→", styles["ComparisonValue"]),
            Paragraph(safe_str(new_statut), styles["ComparisonValue"]),
        ])

    if promotion_data.get("new_classification") or promotion_data.get("previous_classification"):
        previous_class = promotion_data.get("previous_classification", {})
        new_class = promotion_data.get("new_classification", {})
        prev_coeff = previous_class.get("coefficient") if isinstance(previous_class, dict) else None
        new_coeff = new_class.get("coefficient") if isinstance(new_class, dict) else None
        prev_classe = previous_class.get("classe_emploi") if isinstance(previous_class, dict) else None
        new_classe = new_class.get("classe_emploi") if isinstance(new_class, dict) else None
        if prev_coeff or new_coeff or prev_classe or new_classe:
            prev_str = f"Coeff. {prev_coeff}" if prev_coeff else "Non renseigné"
            if prev_classe:
                prev_str += f", Classe {prev_classe}"
            new_str = f"Coeff. {new_coeff}" if new_coeff else "Non renseigné"
            if new_classe:
                new_str += f", Classe {new_classe}"
            comparison_data.append([
                Paragraph(
                    "<b>Classification conventionnelle</b>",
                    styles["ComparisonLabel"],
                ),
                Paragraph(safe_str(prev_str), styles["ComparisonValue"]),
                Paragraph("→", styles["ComparisonValue"]),
                Paragraph(safe_str(new_str), styles["ComparisonValue"]),
            ])

    if promotion_data.get("grant_rh_access") and promotion_data.get("new_rh_access"):
        previous_rh = promotion_data.get("previous_rh_access") or "Aucun accès RH"
        new_rh = promotion_data.get("new_rh_access") or "Non renseigné"
        role_labels = {
            "collaborateur_rh": "Collaborateur RH",
            "rh": "RH",
            "admin": "Administrateur",
            "collaborateur": "Collaborateur",
        }
        previous_rh_label = (
            role_labels.get(previous_rh, previous_rh) if previous_rh else "Aucun accès RH"
        )
        new_rh_label = role_labels.get(new_rh, new_rh) if new_rh else "Non renseigné"
        comparison_data.append([
            Paragraph("<b>Accès RH</b>", styles["ComparisonLabel"]),
            Paragraph(safe_str(previous_rh_label), styles["ComparisonValue"]),
            Paragraph("→", styles["ComparisonValue"]),
            Paragraph(safe_str(new_rh_label), styles["ComparisonValue"]),
        ])

    if comparison_data:
        comparison_table = Table(
            comparison_data, colWidths=[5 * cm, 4 * cm, 1 * cm, 4 * cm]
        )
        comparison_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
                ("BACKGROUND", (2, 0), (2, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ALIGN", (2, 0), (2, -1), "CENTER"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ])
        )
        story.append(Paragraph("<b>Détails de la promotion :</b>", styles["Important"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(comparison_table)
        story.append(Spacer(1, 0.5 * cm))

    effective_date = promotion_data.get("effective_date")
    if effective_date:
        if isinstance(effective_date, str):
            try:
                effective_date = date.fromisoformat(effective_date)
            except Exception:
                pass
        if isinstance(effective_date, date):
            date_effet_text = f"""
            <b>Date d'effet :</b> Cette promotion prendra effet à compter du {format_date_fr(effective_date)}.
            """
            story.append(Paragraph(date_effet_text, styles["CorpsTexte"]))
            story.append(Spacer(1, 0.5 * cm))

    if promotion_data.get("reason"):
        reason_text = f"""
        <b>Raison de la promotion :</b> {safe_str(promotion_data.get('reason'))}
        """
        story.append(Paragraph(reason_text, styles["CorpsTexte"]))
        story.append(Spacer(1, 0.3 * cm))

    if promotion_data.get("justification"):
        justification_text = f"""
        {safe_str(promotion_data.get('justification'))}
        """
        story.append(Paragraph(justification_text, styles["CorpsTexte"]))
        story.append(Spacer(1, 0.5 * cm))

    congrats_text = """
    Nous vous félicitons pour cette évolution et vous souhaitons beaucoup de succès dans vos nouvelles fonctions.
    """
    story.append(Paragraph(congrats_text, styles["CorpsTexte"]))
    story.append(Spacer(1, 0.5 * cm))

    signature_text = """
    Veuillez agréer, Madame, Monsieur, l'expression de nos salutations distinguées.
    """
    story.append(Paragraph(signature_text, styles["CorpsTexte"]))
    story.append(Spacer(1, 1.5 * cm))

    signature_table_data = [
        ["", ""],
        ["", ""],
        [
            Paragraph("<b>Signature du salarié</b>", styles["Normal"]),
            Paragraph("<b>Signature de l'employeur</b>", styles["Normal"]),
        ],
        [
            '(Précédée de la mention "Lu et approuvé")',
            "(Cachet de l'entreprise)",
        ],
    ]
    signature_table = Table(signature_table_data, colWidths=[8 * cm, 8 * cm])
    signature_table.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 2), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 2), (-1, 2), 20),
            ("BOTTOMPADDING", (0, 3), (-1, 3), 40),
        ])
    )
    story.append(signature_table)
    story.append(Spacer(1, 0.5 * cm))

    footer_text = f"Document généré le {format_date_fr(today)}"
    story.append(
        Paragraph(
            footer_text,
            ParagraphStyle(
                name="Footer",
                parent=styles["Normal"],
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


def save_promotion_document(
    promotion_id: str,
    company_id: str,
    employee_id: str,
    employee_folder_name: str,
    pdf_bytes: bytes,
) -> str:
    """
    Sauvegarde le document PDF de promotion dans Supabase Storage.

    Comportement identique au legacy promotion_document_service.save_promotion_document.
    """
    today = datetime.now().date()
    pdf_name = f"Promotion_{employee_folder_name}_{today.strftime('%Y%m%d')}.pdf"
    storage_path = f"{company_id}/{employee_id}/promotions/{pdf_name}"

    supabase.storage.from_("promotion_documents").upload(
        path=storage_path,
        file=pdf_bytes,
        file_options={"content-type": "application/pdf", "x-upsert": "true"},
    )

    signed_url_response = supabase.storage.from_("promotion_documents").create_signed_url(
        storage_path,
        31536000,
        options={"download": True},
    )

    pdf_url = (
        signed_url_response.get("signedURL")
        if isinstance(signed_url_response, dict)
        else None
    )
    if not pdf_url:
        raise Exception("Impossible de générer l'URL signée")

    supabase.table("promotions").update(
        {"promotion_letter_url": pdf_url}
    ).eq("id", promotion_id).execute()

    return pdf_url


def get_promotion_pdf_stream(promotion_id: str, company_id: str) -> io.BytesIO:
    """
    Récupère le PDF de promotion comme stream pour le téléchargement.

    Comportement identique au legacy : lève NotImplementedError tant que
    le téléchargement depuis Supabase Storage n'est pas implémenté.
    """
    promotion_response = (
        supabase.table("promotions")
        .select("promotion_letter_url, employee_id")
        .eq("id", promotion_id)
        .eq("company_id", company_id)
        .single()
        .execute()
    )

    if not promotion_response.data:
        raise Exception("Promotion non trouvée")

    promotion = promotion_response.data
    pdf_url = promotion.get("promotion_letter_url")

    if not pdf_url:
        raise Exception("Document PDF non disponible")

    raise NotImplementedError("Téléchargement depuis Supabase Storage à implémenter")
