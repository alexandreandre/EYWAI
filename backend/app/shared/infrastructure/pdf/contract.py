"""
Génération PDF de contrat de travail.

Implémentation autonome dans app/* (pas de dépendance à services/).
"""
import base64
from datetime import date
from pathlib import Path
from typing import Any, Dict

from weasyprint import HTML


def generate_contract_pdf(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    logo_path: str,
) -> bytes:
    """
    Génère un PDF de contrat de travail standardisé.

    Args:
        employee_data: Données complètes de l'employé
        company_data: Données de l'entreprise
        logo_path: Chemin vers le logo de l'entreprise

    Returns:
        bytes: Contenu du PDF généré
    """
    logo_base64 = ""
    if Path(logo_path).exists():
        with open(logo_path, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode("utf-8")

    hire_date_str = employee_data.get("hire_date", "")
    if isinstance(hire_date_str, str):
        try:
            hire_date_obj = date.fromisoformat(hire_date_str)
            hire_date_formatted = hire_date_obj.strftime("%d/%m/%Y")
        except ValueError:
            hire_date_formatted = hire_date_str
    else:
        hire_date_formatted = str(hire_date_str)

    salaire = employee_data.get("salaire_de_base", {}).get("valeur", 0)
    duree_hebdo = employee_data.get("duree_hebdomadaire", 35)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Contrat de Travail</title>
        <style>
            @page {{
                size: A4;
                margin: 2.5cm;
            }}
            body {{
                font-family: 'Arial', 'Helvetica', sans-serif;
                line-height: 1.8;
                color: #000;
                font-size: 11pt;
            }}
            .header {{
                text-align: center;
                margin-bottom: 40px;
            }}
            .logo {{
                width: 120px;
                margin-bottom: 20px;
            }}
            .title {{
                font-size: 20pt;
                font-weight: bold;
                text-align: center;
                margin: 30px 0;
                text-transform: uppercase;
            }}
            .subtitle {{
                font-size: 14pt;
                font-weight: bold;
                margin: 20px 0 10px 0;
                color: #2c3e50;
            }}
            .section {{
                margin: 25px 0;
            }}
            .article {{
                margin: 20px 0;
            }}
            .article-title {{
                font-weight: bold;
                margin: 15px 0 5px 0;
            }}
            .info-box {{
                background-color: #f8f9fa;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
            }}
            .signature-area {{
                margin-top: 60px;
                display: flex;
                justify-content: space-between;
            }}
            .signature-box {{
                width: 45%;
            }}
            .signature-line {{
                border-top: 1px solid #000;
                margin-top: 60px;
                padding-top: 5px;
                text-align: center;
                font-size: 9pt;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            {"<img src='data:image/png;base64," + logo_base64 + "' class='logo' />" if logo_base64 else ""}
        </div>

        <div class="title">Contrat de Travail {employee_data.get('contract_type', 'CDI')}</div>

        <div class="section">
            <strong>Entre les soussignés :</strong>
            <div style="margin: 15px 0 15px 30px;">
                <p><strong>{company_data.get('company_name', 'MAJI')}</strong></p>
                <p>SIRET : {company_data.get('siret', 'N/A')}</p>
                <p>Adresse : {company_data.get('email', 'N/A')}</p>
            </div>
            <p>Ci-après dénommée « l'Employeur »,</p>
            <p style="text-align: center; margin: 20px 0;"><strong>ET</strong></p>
            <p><strong>{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}</strong></p>
            <p>Né(e) le : {employee_data.get('date_naissance', 'N/A')}</p>
            <p>À : {employee_data.get('lieu_naissance', 'N/A')}</p>
            <p>Nationalité : {employee_data.get('nationalite', 'Française')}</p>
            <p>Domicilié(e) : {employee_data.get('adresse', {}).get('rue', '')}, {employee_data.get('adresse', {}).get('code_postal', '')} {employee_data.get('adresse', {}).get('ville', '')}</p>
            <p>N° Sécurité Sociale : {employee_data.get('nir', 'N/A')}</p>
            <p>Ci-après dénommé(e) « le Salarié »,</p>
        </div>

        <div class="subtitle">IL A ÉTÉ CONVENU CE QUI SUIT :</div>

        <div class="article">
            <div class="article-title">ARTICLE 1 - ENGAGEMENT</div>
            <p>L'Employeur engage le Salarié qui accepte, à compter du <strong>{hire_date_formatted}</strong>, en qualité de <strong>{employee_data.get('job_title', '')}</strong>.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 2 - FONCTIONS</div>
            <p>Le Salarié exercera les fonctions de <strong>{employee_data.get('job_title', '')}</strong>.</p>
            <p>Le Salarié s'engage à consacrer toute son activité professionnelle à l'entreprise et à se conformer aux instructions qui lui seront données par sa hiérarchie.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 3 - DURÉE DU TRAVAIL</div>
            <p>Le Salarié est employé à temps {"partiel" if employee_data.get('is_temps_partiel') else "complet"}.</p>
            <p>La durée hebdomadaire de travail est fixée à <strong>{duree_hebdo} heures</strong>.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 4 - RÉMUNÉRATION</div>
            <p>En contrepartie de son travail, le Salarié percevra une rémunération mensuelle brute de <strong>{salaire:.2f} €</strong>.</p>
            <div class="info-box">
                <p><strong>Classification conventionnelle :</strong></p>
                <p>Groupe : {employee_data.get('classification_conventionnelle', {}).get('groupe_emploi', 'N/A')}</p>
                <p>Classe : {employee_data.get('classification_conventionnelle', {}).get('classe_emploi', 'N/A')}</p>
                <p>Coefficient : {employee_data.get('classification_conventionnelle', {}).get('coefficient', 'N/A')}</p>
            </div>
            <p>Le salaire sera versé mensuellement par virement bancaire.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 5 - STATUT</div>
            <p>Le Salarié relève du statut <strong>{employee_data.get('statut', 'Non-Cadre')}</strong>.</p>
        </div>

        <div class="article">
            <div class="article-title">ARTICLE 6 - CONVENTION COLLECTIVE</div>
            <p>Le présent contrat est soumis aux dispositions de la convention collective applicable dans l'entreprise.</p>
        </div>

        <div class="signature-area">
            <div class="signature-box">
                <p><strong>Fait à _____________, le _____________</strong></p>
                <div class="signature-line">
                    Signature de l'Employeur<br>
                    (Précédée de la mention "Lu et approuvé")
                </div>
            </div>
            <div class="signature-box">
                <p><strong>Fait à _____________, le _____________</strong></p>
                <div class="signature-line">
                    Signature du Salarié<br>
                    (Précédée de la mention "Lu et approuvé")
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return HTML(string=html_content).write_pdf()
