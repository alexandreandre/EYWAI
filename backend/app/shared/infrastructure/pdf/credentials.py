"""
Génération PDF des identifiants de connexion (création de compte).
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Dict, Optional

from weasyprint import HTML

from app.shared.infrastructure.pdf.helpers import (
    build_branding_header_html,
    get_company_name,
    get_company_signatory,
    resolve_company_logo,
)


def _e(text: Any) -> str:
    return escape(str(text or ""))


def generate_credentials_pdf(
    first_name: str,
    last_name: str,
    username: str,
    password: str,
    logo_path: str = "",
    company_data: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Génère un PDF contenant les informations de connexion d'un employé.
    """
    company = company_data or {}
    logo_bytes = resolve_company_logo(company)
    if not logo_bytes and logo_path and Path(logo_path).exists():
        logo_bytes = Path(logo_path).read_bytes()

    header_html = build_branding_header_html(company, logo_bytes=logo_bytes)
    company_name = get_company_name(company)
    signatory, signatory_title = get_company_signatory(company)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Informations de connexion</title>
        <style>
            @page {{ size: A4; margin: 2cm; }}
            body {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                line-height: 1.6;
                color: #333;
                font-size: 11pt;
            }}
            .company-header {{ margin-bottom: 24px; }}
            .title {{
                font-size: 20px;
                font-weight: bold;
                color: #1e3a5f;
                margin-bottom: 24px;
            }}
            .credentials-box {{
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 20px;
                margin: 24px 0;
            }}
            .credential-item {{ margin: 12px 0; }}
            .credential-label {{ font-weight: bold; display: inline-block; width: 200px; }}
            .credential-value {{
                font-family: 'Courier New', monospace;
                font-size: 14px;
                font-weight: bold;
                color: #1e40af;
            }}
            .note {{
                background-color: #fffbeb;
                border-left: 4px solid #f59e0b;
                padding: 14px;
                margin: 24px 0;
                font-size: 10pt;
            }}
            .footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        {header_html}

        <div class="title">Informations de connexion</div>

        <p><strong>À l'attention de :</strong> {_e(first_name)} {_e(last_name)}</p>

        <p>Bonjour {_e(first_name)},</p>
        <p>Votre compte utilisateur sur la plateforme {_e(company_name)} a été créé avec succès.</p>
        <p>Voici vos identifiants de première connexion :</p>

        <div class="credentials-box">
            <div class="credential-item">
                <span class="credential-label">Nom d'utilisateur :</span>
                <span class="credential-value">{_e(username)}</span>
            </div>
            <div class="credential-item">
                <span class="credential-label">Mot de passe temporaire :</span>
                <span class="credential-value">{_e(password)}</span>
            </div>
        </div>

        <div class="note">
            <strong>Important :</strong> Ce mot de passe est temporaire et confidentiel.
            Vous devez le modifier dès votre première connexion. Ne communiquez
            ces identifiants à personne d'autre que le destinataire.
        </div>

        <p>En cas de difficulté, contactez le service des ressources humaines.</p>

        <div class="footer">
            <p>Cordialement,</p>
            <p><strong>{_e(signatory)}</strong><br/>
            {_e(signatory_title)}<br/>
            {_e(company_name)}</p>
        </div>
    </body>
    </html>
    """

    return HTML(string=html_content).write_pdf()
