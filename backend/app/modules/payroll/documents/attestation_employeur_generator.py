"""
Génération PDF de l'attestation employeur destinée à France Travail.

Reproduit la structure officielle (rubriques numérotées, tableau des salaires 25/37 mois).
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.payroll.documents.attestation_employeur_salary_history import (
    get_salary_history,
)
from app.modules.payroll.solde_de_tout_compte.common.pdf_helpers import (
    build_company_header,
    format_currency,
    format_date,
    safe_float,
    safe_str,
)
from app.shared.infrastructure.pdf.helpers import (
    format_amount_cell,
    get_company_address,
    get_company_city,
    get_company_name,
    get_company_signatory,
    get_convention_collective,
    get_employee_address,
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

ELIGIBLE_PORTABILITY_MOTIFS = frozenset(
    {"licenciement", "fin_cdd", "rupture_conventionnelle"}
)

_NEANT = "Néant"


def _section_title(text: str, styles: Any) -> Paragraph:
    return Paragraph(f"<b>{text}</b>", styles["Important"])


def _info_table(rows: List[List[str]], col_widths=None) -> Table:
    table = Table(rows, colWidths=col_widths or [5.5 * cm, 10.5 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _salary_table(months: List[Dict[str, Any]]) -> Table:
    header = [
        "Période de paie",
        "Temps de travail",
        "Absences non assimilées",
        "Salaire brut",
    ]
    data = [header]
    total = 0.0
    for row in months:
        brut = safe_float(row.get("gross_salary"), 0.0)
        total += brut
        label = safe_str(row.get("period_label"))
        if row.get("is_estimated"):
            label += " *"
        data.append(
            [
                label,
                safe_str(row.get("working_time")) or _NEANT,
                safe_str(row.get("absences")) or _NEANT,
                format_amount_cell(brut),
            ]
        )
    data.append(["TOTAL", "", "", format_amount_cell(total)])

    table = Table(
        data,
        colWidths=[4.8 * cm, 3.6 * cm, 3.8 * cm, 3.3 * cm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _collect_indemnity_lines(indemnities: Optional[Dict[str, Any]]) -> List[List[str]]:
    if not indemnities:
        return [[_NEANT, _NEANT]]
    mapping = [
        ("indemnite_preavis", "Indemnité compensatrice de préavis"),
        ("indemnite_conges", "Indemnité compensatrice de congés payés"),
        ("indemnite_licenciement", "Indemnité de licenciement"),
        ("indemnite_rupture_conventionnelle", "Indemnité de rupture conventionnelle"),
    ]
    lines: List[List[str]] = []
    for key, label in mapping:
        block = indemnities.get(key)
        if not isinstance(block, dict):
            continue
        amount = safe_float(block.get("montant") or block.get("montant_negocie"), 0.0)
        if amount > 0:
            lines.append([label, format_currency(amount)])
    if not lines:
        return [[_NEANT, _NEANT]]
    return lines


def _collect_primes_lines(
    salary_history: Dict[str, Any],
    document_data: Optional[Dict[str, Any]],
) -> List[List[str]]:
    custom = (document_data or {}).get("primes_lines")
    if isinstance(custom, list) and custom:
        lines = []
        for item in custom:
            if not isinstance(item, dict):
                continue
            nature = safe_str(item.get("nature") or item.get("label"))
            amount = safe_float(item.get("montant") or item.get("amount"), 0.0)
            if nature and amount > 0:
                lines.append([nature, format_currency(amount)])
        if lines:
            return lines

    primes = salary_history.get("primes_lines") or []
    if not primes:
        return [[_NEANT, _NEANT]]
    return [
        [safe_str(p.get("nature")), format_currency(safe_float(p.get("montant"), 0.0))]
        for p in primes
        if safe_float(p.get("montant"), 0.0) > 0
    ] or [[_NEANT, _NEANT]]


def _preavis_lines(exit_data: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    notice_days = exit_data.get("notice_period_days") or 0
    notice_end = exit_data.get("notice_end_date")
    notice_indemnity_type = exit_data.get("notice_indemnity_type", "not_applicable")

    if notice_days and int(notice_days) > 0:
        lines.append(f"Durée du préavis : {notice_days} jours.")
        if notice_end:
            lines.append(f"Fin de préavis : {format_date(notice_end)}.")
        if notice_indemnity_type == "waived":
            lines.append("Préavis non exécuté (dispense accordée).")
        elif notice_indemnity_type == "paid":
            indemnities = exit_data.get("calculated_indemnities") or {}
            montant = safe_float(
                (indemnities.get("indemnite_preavis") or {}).get("montant", 0)
            )
            if montant > 0:
                lines.append(
                    f"Indemnité compensatrice de préavis : {format_currency(montant)}."
                )
            else:
                lines.append("Préavis non exécuté — indemnité compensatrice due.")
        else:
            lines.append("Préavis exécuté ou en cours d'exécution.")
    else:
        lines.append("Aucun préavis applicable.")
    return lines


def build_attestation_employeur_pdf(
    styles: Any,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    indemnities: Optional[Dict[str, Any]] = None,
    supabase_client: Any = None,
    document_data: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Génère le PDF de l'attestation employeur (structure officielle France Travail)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
    )
    story: List[Any] = []

    build_company_header(story, styles, company_data)

    story.append(
        Paragraph(
            "<b>ATTESTATION EMPLOYEUR</b><br/>"
            "<i>Destinée à France Travail</i>",
            styles["TitrePrincipal"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    # 1. Employeur
    story.append(_section_title("1. EMPLOYEUR", styles))
    story.append(Spacer(1, 0.15 * cm))
    naf = (
        company_data.get("naf_code")
        or company_data.get("ape_code")
        or company_data.get("code_naf")
        or _NEANT
    )
    story.append(
        _info_table(
            [
                ["Raison sociale :", get_company_name(company_data)],
                ["Adresse :", get_company_address(company_data) or _NEANT],
                ["SIRET :", safe_str(company_data.get("siret")) or _NEANT],
                ["Code NAF/APE :", safe_str(naf)],
                [
                    "N° URSSAF :",
                    safe_str(company_data.get("urssaf_number")) or _NEANT,
                ],
            ]
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    # 2. Salarié
    story.append(_section_title("2. SALARIÉ", styles))
    story.append(Spacer(1, 0.15 * cm))
    nom_complet = (
        f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}".strip()
    )
    nir = (
        employee_data.get("nir")
        or employee_data.get("social_security_number")
        or employee_data.get("numero_securite_sociale")
        or _NEANT
    )
    birth_place = (
        employee_data.get("birth_place")
        or employee_data.get("lieu_naissance")
        or _NEANT
    )
    story.append(
        _info_table(
            [
                ["Nom et prénom :", nom_complet or _NEANT],
                [
                    "Date de naissance :",
                    format_date(employee_data.get("date_naissance", "")) or _NEANT,
                ],
                ["Lieu de naissance :", safe_str(birth_place)],
                ["N° de Sécurité sociale :", safe_str(nir)],
                ["Adresse :", get_employee_address(employee_data) or _NEANT],
            ]
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    # 3. Emploi et contrat
    story.append(_section_title("3. EMPLOI ET CONTRAT DE TRAVAIL", styles))
    story.append(Spacer(1, 0.15 * cm))
    ccn = (document_data or {}).get("convention_collective") or get_convention_collective(
        company_data, employee_data
    )
    story.append(
        _info_table(
            [
                ["Emploi occupé :", safe_str(employee_data.get("job_title")) or _NEANT],
                [
                    "Qualification :",
                    safe_str(
                        employee_data.get("qualification")
                        or employee_data.get("job_title")
                    )
                    or _NEANT,
                ],
                ["Convention collective :", safe_str(ccn)],
                [
                    "Nature du contrat :",
                    safe_str(employee_data.get("contract_type")) or "CDI",
                ],
                [
                    "Date d'embauche :",
                    format_date(employee_data.get("hire_date", "")) or _NEANT,
                ],
                [
                    "Date de fin de contrat :",
                    format_date(exit_data.get("last_working_day", "")) or _NEANT,
                ],
            ]
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    # 4. Motif de rupture
    story.append(_section_title("4. MOTIF DE LA RUPTURE DU CONTRAT", styles))
    story.append(Spacer(1, 0.15 * cm))
    exit_type = exit_data.get("exit_type", "")
    motif = EXIT_TYPE_LABELS.get(
        exit_type,
        exit_type.replace("_", " ").title() if exit_type else "Non spécifié",
    )
    story.append(Paragraph(f"Motif : <b>{motif}</b>", styles["CorpsTexte"]))
    if exit_data.get("exit_reason"):
        story.append(
            Paragraph(
                f"Précisions : {safe_str(exit_data.get('exit_reason'))}",
                styles["CorpsTexte"],
            )
        )
    story.append(Spacer(1, 0.35 * cm))

    # Historique salaires
    employee_id = str(employee_data.get("id") or "")
    custom_rows = (document_data or {}).get("salary_history")
    salary_history = get_salary_history(
        employee_id=employee_id,
        employee_data=employee_data,
        end_date=exit_data.get("last_working_day"),
        supabase_client=supabase_client,
        custom_rows=custom_rows if isinstance(custom_rows, list) else None,
    )
    month_count = salary_history.get("month_count", 25)

    story.append(
        _section_title(
            f"5. SALAIRES DES {month_count} DERNIERS MOIS",
            styles,
        )
    )
    story.append(Spacer(1, 0.1 * cm))
    story.append(
        Paragraph(
            "<i>Montants bruts soumis à cotisations — temps de travail en heures ou jours.</i>",
            ParagraphStyle(
                name="AttestationNote",
                parent=styles["Normal"],
                fontSize=8,
                textColor=colors.HexColor("#64748b"),
            ),
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(_salary_table(salary_history.get("months") or []))
    story.append(Spacer(1, 0.1 * cm))
    story.append(
        Paragraph(
            "<i>* Montant estimé (bulletin absent ou incomplet).</i>",
            ParagraphStyle(
                name="AttestationEstime",
                parent=styles["Normal"],
                fontSize=7,
                textColor=colors.HexColor("#94a3b8"),
            ),
        )
    )

    # 6. Primes
    story.append(Spacer(1, 0.3 * cm))
    story.append(_section_title("6. PRIMES ET INDEMNITÉS PERÇUES", styles))
    story.append(Spacer(1, 0.15 * cm))
    primes_rows = _collect_primes_lines(salary_history, document_data)
    primes_table = Table(
        [["Nature", "Montant brut"]] + primes_rows,
        colWidths=[11 * cm, 5 * cm],
    )
    primes_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(primes_table)

    # 7. Sommes versées à la rupture
    effective_indemnities = indemnities or exit_data.get("calculated_indemnities")
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        _section_title("7. SOMMES VERSÉES À L'OCCASION DE LA RUPTURE", styles)
    )
    story.append(Spacer(1, 0.15 * cm))
    indemnity_rows = _collect_indemnity_lines(effective_indemnities)
    indemnity_table = Table(
        [["Nature", "Montant"]] + indemnity_rows,
        colWidths=[11 * cm, 5 * cm],
    )
    indemnity_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(indemnity_table)

    # 8. Préavis
    story.append(Spacer(1, 0.3 * cm))
    story.append(_section_title("8. PRÉAVIS", styles))
    story.append(Spacer(1, 0.15 * cm))
    for line in _preavis_lines({**exit_data, "calculated_indemnities": effective_indemnities}):
        story.append(Paragraph(line, styles["CorpsTexte"]))

    # 9. Organismes complémentaires
    story.append(Spacer(1, 0.3 * cm))
    story.append(_section_title("9. ORGANISMES COMPLÉMENTAIRES", styles))
    story.append(Spacer(1, 0.15 * cm))
    if exit_type in ELIGIBLE_PORTABILITY_MOTIFS:
        mutuelle = (
            company_data.get("mutuelle_nom")
            or company_data.get("organisme_mutuelle")
            or "organisme complémentaire santé de l'entreprise"
        )
        prevoyance = (
            company_data.get("prevoyance_nom")
            or company_data.get("organisme_prevoyance")
            or "organisme de prévoyance de l'entreprise"
        )
        portabilite_text = (
            f"Le salarié bénéficie du maintien des garanties (portabilité) auprès de "
            f"<b>{mutuelle}</b> (complémentaire santé) et <b>{prevoyance}</b> (prévoyance), "
            "conformément aux articles L911-8 et suivants du Code de la sécurité sociale."
        )
    else:
        portabilite_text = (
            "Maintien des garanties de prévoyance et de mutuelle : non applicable "
            "ou non renseigné pour ce motif de rupture."
        )
    story.append(Paragraph(portabilite_text, styles["CorpsTexte"]))

    # Signature
    story.append(Spacer(1, 0.8 * cm))
    company_city = get_company_city(company_data) or "…………………"
    today = format_date(datetime.now().date())
    story.append(
        Paragraph(
            f"Fait à {company_city}, le {today}",
            styles["Signature"],
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    signatory, signatory_title = get_company_signatory(company_data)
    sig = f"<b>{signatory}</b>"
    if signatory_title:
        sig += f"<br/><i>{signatory_title}</i>"
    sig += "<br/>Signature et cachet de l'employeur"
    story.append(Paragraph(sig, styles["Signature"]))
    story.append(Spacer(1, 0.6 * cm))

    story.append(
        Paragraph(
            "<i>Document établi par l'employeur. La version faisant foi auprès de "
            "France Travail est transmise via la DSN (signalement fin de contrat).</i>",
            ParagraphStyle(
                name="AttestationFooter",
                parent=styles["Normal"],
                fontSize=7,
                textColor=colors.HexColor("#94a3b8"),
                alignment=TA_CENTER,
            ),
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
