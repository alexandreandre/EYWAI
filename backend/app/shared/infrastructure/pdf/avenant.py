"""
Génération PDF d'avenant au contrat de travail.

Mentions obligatoires (art. L1221-1, jurisprudence Cass. soc.) :
identité des parties, référence au contrat initial, objet, description
ancien/nouveau, date d'effet, clause de maintien, double exemplaire, signatures.
"""

from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
from typing import Any, Dict, Optional

from weasyprint import HTML

from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_html,
    format_salary_euros,
    get_company_address,
    get_company_city,
    get_company_name,
    get_company_signatory,
    get_employee_address,
    get_lieu_travail,
    get_salary_amount,
    resolve_company_logo,
    safe_str,
)

AVENANT_TYPE_LABELS: Dict[str, str] = {
    "avenant_salaire": "la rémunération",
    "avenant_poste": "les fonctions et la qualification",
    "avenant_temps": "la durée du travail",
    "avenant_lieu": "le lieu de travail",
    "avenant_general": "certaines dispositions contractuelles",
}

_ECONOMIC_KEYWORDS = (
    "économique",
    "economique",
    "restructuration",
    "difficultés économiques",
    "difficultes economiques",
    "l1222-6",
    "l.1222-6",
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


def _fmt_salary(value: Any) -> str:
    if value is None or value == "":
        return "…………………"
    if isinstance(value, dict):
        return format_salary_euros({"salaire_de_base": value})
    try:
        return format_salary_euros({"salaire_de_base": {"valeur": float(value)}})
    except (TypeError, ValueError):
        return _e(value)


def _fmt_duree(value: Any) -> str:
    if value is None or value == "":
        return "…………………"
    try:
        f = float(str(value).replace(",", ".").replace(" h", "").strip())
        return f"{f:g} heures par semaine".replace(".", ",")
    except (ValueError, TypeError):
        s = safe_str(value)
        return s if "h" in s.lower() else f"{s} heures par semaine"


def _ctx_str(context: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = context.get(key)
        if val is not None and str(val).strip() != "":
            return safe_str(val)
    return ""


def _is_economic_motif(motif: str) -> bool:
    lower = motif.lower()
    return any(kw in lower for kw in _ECONOMIC_KEYWORDS)


def _modification_block(
    avenant_type: str,
    context: Dict[str, Any],
    employee_data: Dict[str, Any],
) -> str:
    """Bloc HTML décrivant la modification ancien -> nouveau selon le type."""
    motif = _ctx_str(context, "motif_avenant", "motif")

    if avenant_type == "avenant_salaire":
        ancien = _ctx_str(context, "ancien_salaire") or str(
            get_salary_amount(employee_data) or ""
        )
        nouveau = _ctx_str(context, "nouveau_salaire")
        return f"""
        <table class="modif-table">
            <tr><th>Élément</th><th>Ancienne rédaction</th><th>Nouvelle rédaction</th></tr>
            <tr>
                <td>Rémunération mensuelle brute</td>
                <td><strong>{_fmt_salary(ancien)}</strong></td>
                <td><strong>{_fmt_salary(nouveau)}</strong></td>
            </tr>
        </table>
        """

    if avenant_type == "avenant_poste":
        ancien = _ctx_str(context, "ancien_poste") or safe_str(
            employee_data.get("job_title", "")
        )
        nouveau = _ctx_str(context, "nouveau_poste")
        return f"""
        <table class="modif-table">
            <tr><th>Élément</th><th>Ancienne rédaction</th><th>Nouvelle rédaction</th></tr>
            <tr>
                <td>Fonctions / emploi</td>
                <td><strong>{_e(ancien) or "…………………"}</strong></td>
                <td><strong>{_e(nouveau) or "…………………"}</strong></td>
            </tr>
        </table>
        """

    if avenant_type == "avenant_temps":
        ancien = _ctx_str(context, "ancienne_duree") or safe_str(
            employee_data.get("duree_hebdomadaire", "")
        )
        nouveau = _ctx_str(context, "nouvelle_duree")
        return f"""
        <table class="modif-table">
            <tr><th>Élément</th><th>Ancienne rédaction</th><th>Nouvelle rédaction</th></tr>
            <tr>
                <td>Durée hebdomadaire de travail</td>
                <td><strong>{_fmt_duree(ancien)}</strong></td>
                <td><strong>{_fmt_duree(nouveau)}</strong></td>
            </tr>
        </table>
        """

    if avenant_type == "avenant_lieu":
        ancien = _ctx_str(context, "ancien_lieu") or get_lieu_travail(
            employee_data, {}
        )
        nouveau = _ctx_str(context, "nouveau_lieu")
        return f"""
        <table class="modif-table">
            <tr><th>Élément</th><th>Ancienne rédaction</th><th>Nouvelle rédaction</th></tr>
            <tr>
                <td>Lieu de travail</td>
                <td><strong>{_e(ancien) or "…………………"}</strong></td>
                <td><strong>{_e(nouveau) or "…………………"}</strong></td>
            </tr>
        </table>
        """

    # avenant_general ou type inconnu
    texte = motif or "Modification contractuelle convenue entre les parties."
    return f"""
    <p>Les parties conviennent de la modification suivante :</p>
    <p class="motif-block"><strong>{_e(texte)}</strong></p>
    """


def generate_avenant_pdf(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    logo_path: str = "",
) -> bytes:
    """
    Génère un PDF d'avenant au contrat de travail conforme aux mentions obligatoires.
    """
    ctx = context or {}
    avenant_type = _ctx_str(ctx, "type_avenant") or "avenant_general"
    objet_label = AVENANT_TYPE_LABELS.get(avenant_type, AVENANT_TYPE_LABELS["avenant_general"])

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
    job_title = _e(employee_data.get("job_title", "")) or "…………………"
    employee_address = _e(get_employee_address(employee_data)) or "…………………"
    contract_type = _e(employee_data.get("contract_type", "CDI")) or "CDI"
    contract_date = _fmt_date(
        employee_data.get("date_conclusion_contrat")
        or employee_data.get("date_debut_execution")
        or employee_data.get("hire_date")
    )
    date_effet = _fmt_date(ctx.get("date_effet"))
    date_avenant = _fmt_date(ctx.get("date_avenant") or date.today().isoformat())
    motif = _ctx_str(ctx, "motif_avenant", "motif")
    date_fin = _fmt_date(ctx.get("date_fin_avenant"))

    modif_html = _modification_block(avenant_type, ctx, employee_data)

    motif_paragraph = ""
    if motif and avenant_type != "avenant_general":
        motif_paragraph = f"""
        <p><strong>Motif :</strong> {_e(motif)}</p>
        """

    economic_note = ""
    if motif and _is_economic_motif(motif):
        economic_note = """
        <p class="mention-economique">
            <strong>Note — Modification pour motif économique (art. L1222-6 C. trav.) :</strong>
            la proposition de modification a été/not devra être adressée au salarié par lettre
            recommandée avec accusé de réception. Le salarié dispose d'un délai de réflexion
            d'un mois à compter de la réception de la proposition avant toute signature.
        </p>
        """

    date_fin_paragraph = ""
    if date_fin and date_fin != "…………………":
        date_fin_paragraph = f"""
        <p>Le présent avenant prend fin le <strong>{date_fin}</strong>, sauf prorogation
        ou renouvellement convenu par écrit entre les parties.</p>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Avenant au contrat de travail</title>
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
            .parties {{ margin: 18px 0 22px 0; }}
            .parties p {{ margin: 5px 0; text-align: justify; }}
            .party-block {{ margin-left: 24px; margin-bottom: 8px; }}
            .party-separator {{ text-align: center; margin: 12px 0; font-weight: bold; }}
            .article {{ margin: 12px 0; page-break-inside: avoid; }}
            .article-title {{
                font-weight: bold;
                font-size: 11.5pt;
                margin: 0 0 5px 0;
                text-transform: uppercase;
            }}
            .article p {{ margin: 4px 0; text-align: justify; }}
            .modif-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 10px 0;
                font-size: 10.5pt;
            }}
            .modif-table th, .modif-table td {{
                border: 0.5pt solid #000;
                padding: 6px 8px;
                text-align: left;
                vertical-align: top;
            }}
            .modif-table th {{
                background-color: #f0f0f0;
                font-weight: bold;
            }}
            .motif-block {{
                margin: 8px 0;
                padding: 8px 12px;
                border-left: 2pt solid #333;
                background: #fafafa;
            }}
            .maintien {{
                font-style: italic;
                margin: 14px 0;
                text-align: justify;
            }}
            .mention-economique {{
                font-size: 9.5pt;
                color: #333;
                margin-top: 14px;
                padding: 8px;
                border: 0.5pt solid #666;
                background: #fff8e6;
            }}
            .fait-a {{ margin-top: 28px; margin-bottom: 8px; }}
            .signature-area {{ margin-top: 12px; display: table; width: 100%; }}
            .signature-box {{ display: table-cell; width: 48%; vertical-align: top; padding: 0 1%; }}
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
        <div class="header">{company_header_html}</div>

        <div class="title">Avenant au contrat de travail</div>

        <div class="parties">
            <p><strong>Entre les soussignés :</strong></p>
            <p class="party-block">
                <strong>{_e(company_name)}</strong><br/>
                SIRET : {company_siret}<br/>
                Siège social : {_e(company_address)}<br/>
                Ci-après dénommée « <strong>l'Employeur</strong> »,
            </p>
            <p class="party-separator">D'une part,</p>
            <p class="party-block">
                <strong>{first_name} {last_name}</strong><br/>
                Domicilié(e) : {employee_address}<br/>
                Emploi actuel : <strong>{job_title}</strong><br/>
                Ci-après dénommé(e) « <strong>le Salarié</strong> »,
            </p>
            <p class="party-separator">D'autre part,</p>
        </div>

        <div class="article">
            <div class="article-title">Préambule — Rappel du contrat initial</div>
            <p>Le Salarié est lié à l'Employeur par un contrat de travail de type
            <strong>{contract_type}</strong>, conclu en date du <strong>{contract_date}</strong>.</p>
            <p>Les parties souhaitent modifier certaines dispositions de ce contrat et
            conviennent de conclure le présent avenant.</p>
        </div>

        <div class="article">
            <div class="article-title">Article 1 — Objet de l'avenant</div>
            <p>Le présent avenant a pour objet de modifier les dispositions relatives à
            <strong>{objet_label}</strong> du contrat de travail initial.</p>
            {motif_paragraph}
        </div>

        <div class="article">
            <div class="article-title">Article 2 — Modifications apportées</div>
            {modif_html}
        </div>

        <div class="article">
            <div class="article-title">Article 3 — Date d'effet</div>
            <p>Les modifications prévues au présent avenant prennent effet à compter du
            <strong>{date_effet}</strong>.</p>
            {date_fin_paragraph}
        </div>

        <div class="article">
            <div class="article-title">Article 4 — Maintien des autres clauses</div>
            <p class="maintien">
                Toutes les autres clauses du contrat de travail initial non modifiées par le
                présent avenant demeurent inchangées et continuent de produire leurs effets.
            </p>
        </div>

        {economic_note}

        <p class="fait-a">
            Fait à <strong>{_e(company_city)}</strong>, le <strong>{date_avenant}</strong>,
            en <strong>deux exemplaires originaux</strong>, remis à chaque partie.
        </p>

        <div class="signature-area">
            <div class="signature-box">
                <div class="signature-line">
                    {signatory}<br/>
                    <em>{signatory_title}</em><br/>
                    Signature de l'Employeur<br/>
                    (précédée de la mention manuscrite « Lu et approuvé »)
                </div>
            </div>
            <div class="signature-box">
                <div class="signature-line">
                    {first_name} {last_name}<br/>
                    Signature du Salarié<br/>
                    (précédée de la mention manuscrite « Lu et approuvé »)
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return HTML(string=html_content).write_pdf()
