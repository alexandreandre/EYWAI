"""
Génération PDF de contrat de travail.

Contrat type conforme aux mentions obligatoires de l'article L1221-1
et suivants du Code du travail (version allégée, à personnaliser par l'employeur).
"""

import base64
from datetime import date
from html import escape
from pathlib import Path
from typing import Any, Dict

from weasyprint import HTML

from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_html,
    format_periode_essai,
    format_salary_euros,
    get_company_address,
    get_company_city,
    get_company_name,
    get_company_signatory,
    get_convention_collective,
    get_employee_address,
    get_lieu_travail,
    get_salary_amount,
    resolve_company_logo,
    safe_str,
)


def _fmt_date(value: Any) -> str:
    if not value:
        return "…………………"
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10]).strftime("%d/%m/%Y")
        except ValueError:
            return value
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _e(text: Any) -> str:
    return escape(safe_str(text))


def _is_cdd(contract_type: str) -> bool:
    ct = contract_type.upper()
    return "CDD" in ct or "DETERMINE" in ct or "DÉTERMINÉ" in ct


def _contract_duration_article(contract_type: str, employee_data: Dict[str, Any]) -> str:
    if _is_cdd(contract_type):
        fin = _fmt_date(
            employee_data.get("date_fin_contrat")
            or employee_data.get("contract_end_date")
            or employee_data.get("end_date")
        )
        motif = safe_str(
            employee_data.get("motif_cdd") or employee_data.get("cdd_motif")
        ) or "remplacement ou accroissement temporaire d'activité"
        return f"""
        <div class="article">
            <div class="article-title">ARTICLE 3 — DURÉE DU CONTRAT</div>
            <p>Le présent contrat est conclu pour une <strong>durée déterminée</strong>,
            du {_fmt_date(employee_data.get('hire_date'))} au <strong>{fin}</strong>,
            pour le motif suivant : <strong>{_e(motif)}</strong>.</p>
            <p>Il prendra fin à l'échéance du terme, sous réserve des cas de prorogation
            ou de renouvellement prévus par la loi et la convention collective.</p>
        </div>
        """
    return """
        <div class="article">
            <div class="article-title">ARTICLE 3 — DURÉE DU CONTRAT</div>
            <p>Le présent contrat est conclu pour une <strong>durée indéterminée (CDI)</strong>.
            Il prend effet à la date d'entrée en fonction mentionnée à l'article 1.</p>
        </div>
        """


def generate_contract_pdf(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    logo_path: str = "",
) -> bytes:
    """
    Génère un PDF de contrat de travail avec les mentions légales essentielles.
    """
    logo_bytes = resolve_company_logo(company_data)
    if not logo_bytes and logo_path and Path(logo_path).exists():
        logo_bytes = Path(logo_path).read_bytes()

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
    hire_date = _fmt_date(employee_data.get("hire_date"))
    contract_type = safe_str(employee_data.get("contract_type", "CDI")) or "CDI"
    job_title = _e(employee_data.get("job_title", "")) or "…………………"
    duree_hebdo = employee_data.get("duree_hebdomadaire", 35)
    is_partiel = employee_data.get("is_temps_partiel") or (
        isinstance(duree_hebdo, (int, float)) and float(duree_hebdo) < 35
    )
    statut = _e(employee_data.get("statut", "Non-cadre"))
    lieu_travail = _e(get_lieu_travail(employee_data, company_data))
    salaire_str = format_salary_euros(employee_data)
    cc = employee_data.get("classification_conventionnelle") or {}
    groupe = _e(cc.get("groupe_emploi")) if isinstance(cc, dict) else ""
    classe = _e(cc.get("classe_emploi")) if isinstance(cc, dict) else ""
    coefficient = _e(cc.get("coefficient")) if isinstance(cc, dict) else ""
    convention = _e(get_convention_collective(company_data, employee_data))
    periode_essai = _e(format_periode_essai(employee_data))
    employee_address = _e(get_employee_address(employee_data)) or "…………………"
    date_naissance = _e(employee_data.get("date_naissance")) or "…………………"
    lieu_naissance = _e(employee_data.get("lieu_naissance")) or "…………………"
    nationalite = _e(employee_data.get("nationalite", "Française"))
    nir = _e(employee_data.get("nir")) or "…………………"

    classification_block = ""
    if groupe or classe or coefficient:
        classification_block = f"""
            <p><strong>Classification conventionnelle :</strong>
            groupe {groupe or '—'}, classe {classe or '—'}, coefficient {coefficient or '—'}.</p>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Contrat de travail — {_e(contract_type)}</title>
        <style>
            @page {{
                size: A4;
                margin: 2.5cm 2.5cm 2cm 2.5cm;
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
            .company-header p {{
                margin: 2px 0;
            }}
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
                margin: 22px 0 18px 0;
                padding-bottom: 8px;
                border-bottom: 0.75pt solid #000;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }}
            .parties {{
                margin: 18px 0 22px 0;
            }}
            .parties p {{
                margin: 5px 0;
                text-align: justify;
            }}
            .parties-intro {{
                margin-bottom: 10px;
            }}
            .party-block {{
                margin-left: 24px;
                margin-bottom: 8px;
            }}
            .party-separator {{
                text-align: center;
                margin: 12px 0;
                font-weight: bold;
            }}
            .subtitle {{
                font-size: 11.5pt;
                font-weight: bold;
                text-align: center;
                margin: 22px 0 18px 0;
                text-transform: uppercase;
                letter-spacing: 0.2px;
            }}
            .article {{
                margin: 12px 0;
                page-break-inside: avoid;
            }}
            .article-title {{
                font-weight: bold;
                font-size: 11.5pt;
                margin: 0 0 5px 0;
                color: #000;
                text-transform: uppercase;
            }}
            .article p {{
                margin: 4px 0;
                text-align: justify;
            }}
            .mention {{
                font-size: 9.5pt;
                color: #000;
                margin-top: 22px;
                text-align: justify;
            }}
            .fait-a {{
                margin-top: 28px;
                margin-bottom: 8px;
                text-align: left;
            }}
            .signature-area {{
                margin-top: 12px;
                display: table;
                width: 100%;
            }}
            .signature-box {{
                display: table-cell;
                width: 48%;
                vertical-align: top;
                padding: 0 1%;
            }}
            .signature-line {{
                border-top: 0.5pt solid #000;
                margin-top: 55px;
                padding-top: 6px;
                font-size: 9.5pt;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            {company_header_html}
        </div>

        <div class="title">Contrat de travail — {_e(contract_type)}</div>

        <div class="parties">
            <p class="parties-intro"><strong>Entre les soussignés :</strong></p>
            <p class="party-block">
                <strong>{_e(company_name)}</strong><br/>
                SIRET : {company_siret}<br/>
                Siège social : {_e(company_address)}<br/>
                Ci-après dénommée « <strong>l'Employeur</strong> »,
            </p>
            <p class="party-separator">D'une part,</p>
            <p class="party-block">
                <strong>{first_name} {last_name}</strong><br/>
                Né(e) le {date_naissance} à {lieu_naissance}<br/>
                Nationalité : {nationalite}<br/>
                Domicilié(e) : {employee_address}<br/>
                N° de sécurité sociale : {nir}<br/>
                Ci-après dénommé(e) « <strong>le Salarié</strong> »,
            </p>
            <p class="party-separator">D'autre part,</p>
        </div>

        <div class="subtitle">IL A ÉTÉ CONVENU CE QUI SUIT :</div>

        <div class="article">
            <div class="article-title">ARTICLE 1 — ENGAGEMENT ET DATE D'ENTRÉE</div>
            <p>L'Employeur engage le Salarié, qui accepte, à compter du
            <strong>{hire_date}</strong>, en qualité de <strong>{job_title}</strong>,
            sous contrat de type <strong>{_e(contract_type)}</strong>.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 2 — FONCTIONS ET LIEU DE TRAVAIL</div>
            <p>Le Salarié exercera les fonctions de <strong>{job_title}</strong>,
            rattaché(e) à la direction dont il/elle relève.</p>
            <p>Le lieu habituel de travail est fixé à <strong>{lieu_travail}</strong>.
            L'Employeur se réserve la possibilité de modifier le lieu de travail
            dans le respect des dispositions légales et conventionnelles.</p>
            <p>Le Salarié s'engage à consacrer l'intégralité de son activité professionnelle
            à l'Employeur et à exécuter les missions confiées avec diligence et loyauté.</p>
        </div>

        {_contract_duration_article(contract_type, employee_data)}

        <div class="article">
            <div class="article-title">ARTICLE 4 — PÉRIODE D'ESSAI</div>
            <p>Le contrat est conclus sous réserve d'une période d'essai de
            <strong>{periode_essai}</strong>.</p>
            <p>Chacune des parties pourra rompre le contrat pendant cette période,
            dans les conditions et délais prévus par le Code du travail et la
            convention collective applicable.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 5 — DURÉE DU TRAVAIL</div>
            <p>Le Salarié est employé à <strong>temps {"partiel" if is_partiel else "complet"}</strong>.</p>
            <p>La durée hebdomadaire de travail est fixée à
            <strong>{duree_hebdo} heures</strong>, répartie conformément au planning
            et aux usages de l'entreprise, dans le respect des durées maximales légales.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 6 — RÉMUNÉRATION</div>
            <p>En contrepartie de son travail, le Salarié percevra une rémunération
            mensuelle brute de <strong>{salaire_str}</strong>, pour un temps de travail
            à hauteur de la durée prévue à l'article 5.</p>
            {classification_block}
            <p>Le salaire est payable mensuellement, par virement bancaire,
            au plus tard le dernier jour ouvré du mois.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 7 — CONGÉS PAYÉS ET ABSENCES</div>
            <p>Le Salarié bénéficie des congés payés dans les conditions prévues
            par le Code du travail et la convention collective. Les absences doivent
            être signalées et justifiées selon les règles internes de l'entreprise.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 8 — CONVENTION COLLECTIVE ET STATUT</div>
            <p>Le Salarié relève du statut <strong>{statut}</strong>.</p>
            <p>Le présent contrat est soumis aux dispositions du Code du travail,
            à la convention collective <strong>{convention}</strong>,
            ainsi qu'au règlement intérieur et aux usages en vigueur dans l'entreprise.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 9 — PROTECTION SOCIALE COMPLÉMENTAIRE</div>
            <p>Le Salarié bénéficie, dans les conditions prévues par la loi et les accords
            applicables, de la couverture complémentaire santé (mutuelle) et de la
            prévoyance mises en place par l'Employeur. Les cotisations afférentes
            sont réparties conformément aux textes en vigueur.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 10 — OBLIGATIONS PROFESSIONNELLES</div>
            <p>Le Salarié est tenu au respect du règlement intérieur, des consignes
            de sécurité, du secret professionnel et de la confidentialité des
            informations dont il/elle a connaissance dans l'exercice de ses fonctions.</p>
            <p>Le Salarié s'engage à respecter les règles relatives à la protection
            des données à caractère personnel (RGPD) applicables dans l'entreprise.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 11 — RUPTURE DU CONTRAT</div>
            <p>Le contrat pourra être rompu par l'une ou l'autre des parties dans
            les conditions et formes prévues par le Code du travail, notamment en
            cas de démission, licenciement ou rupture conventionnelle, sous réserve
            du respect des délais de préavis légaux ou conventionnels.</p>
        </div>

        <p class="mention">
            Il contient les mentions obligatoires prévues à l'article L1221-1 du Code du travail.
            {"Le salaire indiqué est provisoire et devra être complété avant signature définitive." if get_salary_amount(employee_data) <= 0 else ""}
        </p>

        <p class="fait-a">
            Fait à <strong>{_e(company_city)}</strong>, le <strong>{hire_date}</strong>,
            en deux exemplaires originaux, remis à chaque partie.
        </p>

        <div class="signature-area">
            <div class="signature-box">
                <div class="signature-line">
                    {signatory}<br/>
                    <em>{signatory_title}</em><br/>
                    Signature de l'Employeur<br/>
                    (précédée de la mention « Lu et approuvé »)
                </div>
            </div>
            <div class="signature-box">
                <div class="signature-line">
                    {first_name} {last_name}<br/>
                    Signature du Salarié<br/>
                    (précédée de la mention « Lu et approuvé »)
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return HTML(string=html_content).write_pdf()
