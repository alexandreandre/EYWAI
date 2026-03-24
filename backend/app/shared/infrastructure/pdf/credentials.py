"""
Génération PDF des identifiants de connexion (création de compte).

Implémentation autonome dans app/* ; comportement identique à services.pdf_generator.generate_credentials_pdf.
"""
import base64
from pathlib import Path

from weasyprint import HTML


def generate_credentials_pdf(
    first_name: str,
    last_name: str,
    username: str,
    password: str,
    logo_path: str,
) -> bytes:
    """
    Génère un PDF contenant les informations de connexion d'un employé.

    Args:
        first_name: Prénom de l'employé
        last_name: Nom de l'employé
        username: Nom d'utilisateur
        password: Mot de passe
        logo_path: Chemin vers le logo (ex. Colorplast.png)

    Returns:
        bytes: Contenu du PDF généré
    """
    logo_base64 = ""
    if Path(logo_path).exists():
        with open(logo_path, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode("utf-8")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Informations de Connexion</title>
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: 'Arial', 'Helvetica', sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                margin-bottom: 30px;
            }}
            .logo {{
                width: 150px;
                margin-bottom: 20px;
            }}
            .title {{
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 30px;
            }}
            .recipient {{
                margin-bottom: 40px;
                font-size: 14px;
            }}
            .content {{
                margin: 40px 0;
            }}
            .credentials-box {{
                background-color: #f8f9fa;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 20px;
                margin: 30px 0;
            }}
            .credential-item {{
                margin: 15px 0;
                font-size: 14px;
            }}
            .credential-label {{
                font-weight: bold;
                color: #495057;
                display: inline-block;
                width: 180px;
            }}
            .credential-value {{
                color: #0066cc;
                font-family: 'Courier New', monospace;
                font-size: 16px;
                font-weight: bold;
            }}
            .footer {{
                margin-top: 60px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
            }}
            .signature {{
                margin-top: 40px;
                font-size: 14px;
            }}
            .note {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 30px 0;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            {"<img src='data:image/png;base64," + logo_base64 + "' class='logo' />" if logo_base64 else ""}
        </div>

        <div class="title">
            Informations de Connexion
        </div>

        <div class="recipient">
            <strong>À l'attention de :</strong><br>
            {first_name} {last_name}
        </div>

        <div class="content">
            <p>Bonjour {first_name},</p>

            <p>Nous avons le plaisir de vous informer que votre compte utilisateur a été créé avec succès.</p>

            <p>Vous trouverez ci-dessous vos informations de connexion à la plateforme :</p>

            <div class="credentials-box">
                <div class="credential-item">
                    <span class="credential-label">Nom d'utilisateur :</span>
                    <span class="credential-value">{username}</span>
                </div>
                <div class="credential-item">
                    <span class="credential-label">Mot de passe temporaire :</span>
                    <span class="credential-value">{password}</span>
                </div>
            </div>

            <div class="note">
                <strong>⚠ Important :</strong> Pour des raisons de sécurité, nous vous recommandons vivement de changer votre mot de passe lors de votre première connexion.
            </div>

            <p>Si vous rencontrez des difficultés lors de votre connexion ou si vous avez des questions, n'hésitez pas à contacter le service des ressources humaines.</p>
        </div>

        <div class="footer">
            <div class="signature">
                <p>Cordialement,</p>
                <p><strong>Vanessa Amate</strong><br>
                Directrice Financière<br>
                MAJI</p>
            </div>
        </div>
    </body>
    </html>
    """

    return HTML(string=html_content).write_pdf()
