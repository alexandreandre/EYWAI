"""
Rendu HTML/PDF du reçu pour solde de tout compte.

Format « classique » de cabinet d'avocat en droit du travail : document sobre,
en serif (Times), articulé en paragraphes et tableaux à bordures fines, sans
encadrés colorés. S'aligne sur le contrat de travail (``shared/.../pdf/contract.py``)
pour une cohérence visuelle entre les documents juridiques de l'entreprise.

Le moteur de rendu est WeasyPrint (HTML → PDF), qui gère nativement le retour à
la ligne dans les cellules : il n'y a donc plus de texte qui se chevauche comme
avec les tableaux ReportLab à cellules de largeur fixe.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional

from weasyprint import HTML

from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_html,
    format_amount_cell,
    format_currency,
    get_company_address,
    get_company_city,
    get_company_name,
    get_company_signatory,
    get_employee_address,
    resolve_company_logo,
    safe_str,
)

from .pdf_helpers import format_date


def _e(value: Any) -> str:
    """Échappe une valeur pour insertion HTML."""
    return escape(safe_str(value))


def amount_row(label: str, detail: str, montant: Optional[float]) -> Dict[str, Any]:
    """Construit une ligne « montant » (libellé, détail, montant)."""
    return {"kind": "amount", "label": label, "detail": detail, "montant": montant}


def info_row(label: str, value: str) -> Dict[str, Any]:
    """Construit une ligne « information » (libellé, valeur)."""
    return {"kind": "info", "label": label, "value": value}


def amounts_section(title: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Section présentant des sommes (3 colonnes)."""
    return {"type": "amounts", "title": title, "rows": rows}


def info_section(title: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Section présentant des informations (2 colonnes)."""
    return {"type": "info", "title": title, "rows": rows}


def _render_amounts_section(section: Dict[str, Any], index: int) -> str:
    body_rows = []
    for row in section["rows"]:
        montant = row.get("montant")
        # montant None => ligne informative (cellule vide) ; un nombre (même 0)
        # => formaté, « Néant » si <= 0.
        montant_cell = "" if montant is None else format_amount_cell(montant)
        detail = row.get("detail") or ""
        body_rows.append(
            f"""
            <tr>
                <td class="lbl">{_e(row.get('label'))}</td>
                <td class="dtl">{_e(detail)}</td>
                <td class="amt">{_e(montant_cell)}</td>
            </tr>"""
        )
    return f"""
        <div class="section">
            <div class="section-title">{index}. {_e(section['title'])}</div>
            <table class="grid">
                <thead>
                    <tr>
                        <th class="lbl">Libellé</th>
                        <th class="dtl">Détails</th>
                        <th class="amt">Montant</th>
                    </tr>
                </thead>
                <tbody>{''.join(body_rows)}</tbody>
            </table>
        </div>
    """


def _render_info_section(section: Dict[str, Any], index: int) -> str:
    body_rows = []
    for row in section["rows"]:
        body_rows.append(
            f"""
            <tr>
                <td class="lbl">{_e(row.get('label'))}</td>
                <td class="val">{_e(row.get('value'))}</td>
            </tr>"""
        )
    return f"""
        <div class="section">
            <div class="section-title">{index}. {_e(section['title'])}</div>
            <table class="grid">
                <tbody>{''.join(body_rows)}</tbody>
            </table>
        </div>
    """


def _render_section(section: Dict[str, Any], index: int) -> str:
    if section["type"] == "info":
        return _render_info_section(section, index)
    return _render_amounts_section(section, index)


def render_solde_tout_compte_html(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    *,
    motif_label: str,
    sections: List[Dict[str, Any]],
    total_brut: float,
    total_cotisations: float,
    total_net: float,
    specific_mention: Optional[str] = None,
    articles: str = "Articles D1234-7 et L1234-20 du Code du travail",
) -> bytes:
    """
    Génère le reçu pour solde de tout compte en PDF (format avocat).

    Args:
        motif_label: motif de rupture en clair (ex. « DÉMISSION »).
        sections: liste de sections construites via ``amounts_section`` /
            ``info_section``.
        total_brut / total_cotisations / total_net: récapitulatif chiffré.
        specific_mention: mention juridique propre au type de rupture.
        articles: articles du Code du travail rappelés en pied de page.
    """
    logo_bytes = resolve_company_logo(company_data)
    company_header_html = build_branding_header_html(company_data, logo_bytes=logo_bytes)

    company_name = get_company_name(company_data)
    company_address = get_company_address(company_data) or "…………………"
    company_siret = safe_str(company_data.get("siret")) or "…………………"
    company_city = get_company_city(company_data) or "…………………"
    signatory, signatory_title = get_company_signatory(company_data)
    if signatory == "Le service RH":
        signatory = "Le représentant légal"
    if not signatory_title:
        signatory_title = "Employeur"

    first_name = _e(employee_data.get("first_name", ""))
    last_name = _e(employee_data.get("last_name", ""))
    nom_complet = f"{first_name} {last_name}".strip() or "…………………"
    employee_address = _e(get_employee_address(employee_data)) or "…………………"
    job_title = _e(employee_data.get("job_title", "")) or "…………………"
    contract_type = _e(employee_data.get("contract_type", "CDI")) or "CDI"
    hire_date = format_date(employee_data.get("hire_date", "")) or "…………………"
    exit_date = format_date(exit_data.get("last_working_day", "")) or "…………………"
    date_du_jour = format_date(datetime.now().date())

    sections_html = "".join(
        _render_section(section, idx) for idx, section in enumerate(sections, start=1)
    )

    specific_mention_html = ""
    if specific_mention:
        specific_mention_html = f'<p class="mention">{_e(specific_mention)}</p>'

    net_str = format_currency(total_net)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Reçu pour solde de tout compte — {nom_complet}</title>
        <style>
            @page {{
                size: A4;
                margin: 2.5cm 2.5cm 2cm 2.5cm;
                @bottom-center {{
                    content: "{_e(articles)}";
                    font-family: 'Times New Roman', Times, serif;
                    font-size: 8pt;
                    color: #555;
                }}
            }}
            body {{
                font-family: 'Times New Roman', Times, Georgia, serif;
                line-height: 1.45;
                color: #000;
                font-size: 11.5pt;
            }}
            .header {{
                text-align: left;
                margin-bottom: 18px;
                border-bottom: 0.5pt solid #000;
                padding-bottom: 10px;
            }}
            .company-header {{
                text-align: left;
                margin-bottom: 0;
                font-size: 9.5pt;
                line-height: 1.35;
            }}
            .company-header p {{ margin: 2px 0; }}
            .company-header img {{
                max-width: 70px;
                max-height: 35px;
                margin-bottom: 6px;
                display: block;
            }}
            .title {{
                font-size: 14pt;
                font-weight: bold;
                text-align: center;
                margin: 22px 0 6px 0;
                padding-bottom: 8px;
                border-bottom: 0.75pt solid #000;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }}
            .parties {{ margin: 16px 0; }}
            .parties p {{ margin: 4px 0; text-align: justify; }}
            .party-block {{ margin-left: 24px; margin-bottom: 8px; }}
            .intro {{ margin: 14px 0 6px 0; text-align: justify; }}
            .section {{ margin: 14px 0; page-break-inside: avoid; }}
            .section-title {{
                font-weight: bold;
                font-size: 11pt;
                margin: 0 0 5px 0;
                text-transform: uppercase;
            }}
            table.grid {{
                width: 100%;
                border-collapse: collapse;
                font-size: 10pt;
            }}
            table.grid th, table.grid td {{
                border: 0.5pt solid #000;
                padding: 4px 7px;
                vertical-align: top;
                text-align: left;
            }}
            table.grid thead th {{
                background: #ececec;
                font-weight: bold;
            }}
            table.grid td.amt, table.grid th.amt {{
                text-align: right;
                white-space: nowrap;
            }}
            table.grid th.lbl, table.grid td.lbl {{ width: 34%; }}
            table.grid th.dtl, table.grid td.dtl {{ width: 48%; }}
            table.grid th.amt, table.grid td.amt {{ width: 18%; }}
            table.grid td.val {{ width: 50%; }}
            .recap {{
                margin: 18px 0 6px 0;
                width: 60%;
                margin-left: auto;
                border-collapse: collapse;
                font-size: 11pt;
            }}
            .recap td {{ padding: 4px 8px; }}
            .recap td.k {{ text-align: left; }}
            .recap td.v {{ text-align: right; white-space: nowrap; font-weight: bold; }}
            .recap tr.net td {{
                border-top: 1pt solid #000;
                font-weight: bold;
                font-size: 12pt;
            }}
            .quittance {{
                margin: 20px 0 6px 0;
                text-align: justify;
                font-weight: bold;
            }}
            .denonciation {{ margin: 6px 0; text-align: justify; }}
            .mention {{
                font-size: 9.5pt;
                color: #000;
                margin-top: 12px;
                text-align: justify;
            }}
            .fait-a {{ margin-top: 22px; margin-bottom: 8px; text-align: left; }}
            .signature-area {{ margin-top: 8px; display: table; width: 100%; }}
            .signature-box {{
                display: table-cell;
                width: 48%;
                vertical-align: top;
                padding: 0 1%;
            }}
            .signature-line {{
                border-top: 0.5pt solid #000;
                margin-top: 60px;
                padding-top: 6px;
                font-size: 9.5pt;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="header">{company_header_html}</div>

        <div class="title">Reçu pour solde de tout compte</div>

        <div class="parties">
            <p class="party-block">
                <strong>{_e(company_name)}</strong><br/>
                SIRET : {company_siret}<br/>
                Siège social : {_e(company_address)}<br/>
                Ci-après dénommée « <strong>l'Employeur</strong> »,
            </p>
            <p class="party-block">
                <strong>{nom_complet}</strong><br/>
                Emploi occupé : {job_title} — Contrat {contract_type}<br/>
                Domicilié(e) : {employee_address}<br/>
                Entré(e) le {hire_date}, sorti(e) le {exit_date}<br/>
                Ci-après dénommé(e) « <strong>le Salarié</strong> ».
            </p>
        </div>

        <p class="intro">
            Je soussigné(e) <strong>{nom_complet}</strong>, dont le contrat de travail
            a pris fin le <strong>{exit_date}</strong> par suite de
            <strong>{_e(motif_label)}</strong>, reconnais avoir reçu de l'Employeur,
            pour solde de tout compte, la somme nette de <strong>{_e(net_str)}</strong>,
            se décomposant comme suit :
        </p>

        {sections_html}

        <table class="recap">
            <tr>
                <td class="k">Total brut</td>
                <td class="v">{_e(format_currency(total_brut))}</td>
            </tr>
            <tr>
                <td class="k">Total des cotisations et retenues salariales</td>
                <td class="v">{_e(format_currency(total_cotisations))}</td>
            </tr>
            <tr class="net">
                <td class="k">Net à payer pour solde de tout compte</td>
                <td class="v">{_e(format_currency(total_net))}</td>
            </tr>
        </table>

        <p class="quittance">
            Le présent reçu vaut quittance pour solde de tout compte.
        </p>
        <p class="denonciation">
            Je reconnais avoir pris connaissance de la faculté de dénonciation qui m'est
            offerte par l'article D1234-7 du Code du travail, aux termes duquel je dispose
            d'un délai de six mois à compter de ce jour pour dénoncer les sommes qui
            m'auraient été réglées par l'Employeur. Le présent reçu est établi en application
            de l'article L1234-20 du Code du travail.
        </p>
        {specific_mention_html}

        <p class="fait-a">
            Fait en double exemplaire à <strong>{_e(company_city)}</strong>,
            le <strong>{date_du_jour}</strong>.
        </p>

        <div class="signature-area">
            <div class="signature-box">
                <div class="signature-line">
                    {nom_complet}<br/>
                    Signature du Salarié<br/>
                    (précédée de la mention manuscrite « Pour solde de tout compte »)
                </div>
            </div>
            <div class="signature-box">
                <div class="signature-line">
                    {_e(signatory)}<br/>
                    <em>{_e(signatory_title)}</em><br/>
                    Signature de l'Employeur et cachet
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return HTML(string=html_content).write_pdf()
