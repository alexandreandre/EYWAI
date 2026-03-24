"""
Helpers PDF génériques : styles ReportLab et formatage (date, devise, safe cast).

Utilisés par les générateurs PDF sous app/* (ex. attestations de salaire).
Aucune dépendance legacy (api/*, schemas/*, services/*, core/* racine).
"""
from datetime import datetime, date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle


def setup_custom_styles(base_styles):
    """
    Configure les styles personnalisés pour les documents PDF.
    Ajoute TitrePrincipal, EntrepriseHeader, CorpsTexte, Important, Signature.
    """
    base_styles.add(
        ParagraphStyle(
            name="TitrePrincipal",
            parent=base_styles["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )
    )
    base_styles.add(
        ParagraphStyle(
            name="EntrepriseHeader",
            parent=base_styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=6,
            alignment=TA_LEFT,
        )
    )
    base_styles.add(
        ParagraphStyle(
            name="CorpsTexte",
            parent=base_styles["Normal"],
            fontSize=11,
            textColor=colors.black,
            spaceAfter=12,
            alignment=TA_JUSTIFY,
            leading=16,
        )
    )
    base_styles.add(
        ParagraphStyle(
            name="Important",
            parent=base_styles["Normal"],
            fontSize=11,
            textColor=colors.black,
            spaceAfter=10,
            fontName="Helvetica-Bold",
        )
    )
    base_styles.add(
        ParagraphStyle(
            name="Signature",
            parent=base_styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=6,
            alignment=TA_RIGHT,
        )
    )
    return base_styles


def format_date(date_value: Any) -> str:
    """Formate une date en français (ex. 15 janvier 2024)."""
    if isinstance(date_value, str):
        try:
            date_value = datetime.fromisoformat(
                date_value.replace("Z", "+00:00")
            ).date()
        except Exception:
            try:
                date_value = datetime.strptime(date_value, "%Y-%m-%d").date()
            except Exception:
                return date_value

    if isinstance(date_value, (datetime, date)):
        mois_francais = [
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        ]
        d = date_value.date() if isinstance(date_value, datetime) else date_value
        return f"{d.day} {mois_francais[d.month - 1]} {d.year}"

    return str(date_value)


def format_currency(amount: float) -> str:
    """Formate un montant en euros."""
    return f"{amount:,.2f} €".replace(",", " ")


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convertit une valeur en float de manière sécurisée."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Convertit une valeur en string de manière sécurisée."""
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default
