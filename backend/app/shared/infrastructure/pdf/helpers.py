"""
Helpers PDF génériques : styles ReportLab et formatage (date, devise, safe cast).

Utilisés par les générateurs PDF sous app/* (ex. attestations de salaire).
Aucune dépendance legacy (api/*, schemas/*, services/*, core/* racine).
"""

import base64
import logging
from datetime import datetime, date
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests

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
            "janvier",
            "février",
            "mars",
            "avril",
            "mai",
            "juin",
            "juillet",
            "août",
            "septembre",
            "octobre",
            "novembre",
            "décembre",
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


def get_company_name(company: Dict[str, Any]) -> str:
    """Raison sociale de l'employeur."""
    for key in ("company_name", "raison_sociale", "name"):
        val = company.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return "Entreprise"


def get_company_address(company: Dict[str, Any]) -> str:
    """Adresse postale de l'employeur (évite d'utiliser l'email par erreur)."""
    addr = company.get("address") or company.get("adresse")
    if isinstance(addr, str) and addr.strip():
        return addr.strip()
    if isinstance(addr, dict):
        parts = [
            addr.get("street") or addr.get("rue") or "",
            " ".join(
                filter(
                    None,
                    [
                        str(addr.get("postal_code") or addr.get("code_postal") or "").strip(),
                        str(addr.get("city") or addr.get("ville") or "").strip(),
                    ],
                )
            ).strip(),
        ]
        line = ", ".join(p for p in parts if p)
        if line:
            return line
    parts = [
        company.get("adresse_rue") or company.get("street") or "",
        " ".join(
            filter(
                None,
                [
                    str(company.get("adresse_code_postal") or company.get("postal_code") or "").strip(),
                    str(company.get("adresse_ville") or company.get("city") or company.get("ville") or "").strip(),
                ],
            )
        ).strip(),
    ]
    line = ", ".join(p for p in parts if p)
    if line:
        return line
    return company.get("full_address") or ""


def get_employee_address(employee: Dict[str, Any]) -> str:
    """Adresse postale du salarié."""
    addr = employee.get("adresse") or employee.get("address")
    if isinstance(addr, str) and addr.strip():
        return addr.strip()
    if isinstance(addr, dict):
        rue = addr.get("rue") or addr.get("street") or ""
        cp = addr.get("code_postal") or addr.get("postal_code") or ""
        ville = addr.get("ville") or addr.get("city") or ""
        line = ", ".join(p for p in (rue, f"{cp} {ville}".strip()) if p)
        if line:
            return line
    return ""


def get_salary_amount(employee: Dict[str, Any]) -> float:
    """Salaire brut mensuel en euros."""
    sb = employee.get("salaire_de_base")
    if isinstance(sb, dict):
        return safe_float(sb.get("valeur", sb.get("amount")), 0.0)
    return safe_float(sb, 0.0)


def format_salary_euros(employee: Dict[str, Any]) -> str:
    """Salaire brut mensuel formaté."""
    amount = get_salary_amount(employee)
    if amount <= 0:
        return "à définir"
    return format_currency(amount)


def format_periode_essai(employee: Dict[str, Any]) -> str:
    """Libellé de la période d'essai à partir des données employé."""
    for key in ("periode_essai_duree", "trial_period_duration", "duree_periode_essai"):
        val = employee.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()

    pe = employee.get("periode_essai")
    if isinstance(pe, dict):
        duree = pe.get("duree_initiale") or pe.get("duree")
        if duree is not None:
            unite = str(pe.get("unite") or "mois").lower()
            if unite.startswith("jour"):
                label = "jour" if int(duree) == 1 else "jours"
            elif unite.startswith("sem"):
                label = "semaine" if int(duree) == 1 else "semaines"
            else:
                label = "mois"
            renouv = pe.get("renouvellement_possible")
            base = f"{duree} {label}"
            if renouv:
                return f"{base}, renouvelable une fois conformément aux dispositions légales et conventionnelles"
            return f"{base}, conformément aux dispositions légales et conventionnelles applicables"

    return "Conformément aux dispositions légales et conventionnelles applicables à l'emploi concerné"


def get_company_city(company: Dict[str, Any]) -> str:
    """Ville du siège / établissement employeur."""
    for key in ("city", "ville", "adresse_ville"):
        val = company.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""


def get_lieu_travail(employee: Dict[str, Any], company: Dict[str, Any]) -> str:
    """Lieu de travail du salarié."""
    lt = employee.get("lieu_travail") or employee.get("workplace")
    if isinstance(lt, str) and lt.strip():
        return lt.strip()
    if isinstance(lt, dict):
        label = lt.get("libelle") or lt.get("label") or lt.get("name") or ""
        if str(label).strip():
            return str(label).strip()
    city = get_company_city(company)
    return city or "établissement de l'Employeur"


def get_convention_collective(company: Dict[str, Any], employee: Dict[str, Any]) -> str:
    """Convention collective applicable."""
    for source in (company, employee):
        for key in ("convention_collective", "collective_agreement_name", "ccn_name"):
            val = source.get(key)
            if val and str(val).strip():
                return str(val).strip()
    idcc = company.get("idcc") or company.get("code_idcc")
    if idcc:
        return f"Convention collective (IDCC {idcc})"
    return "Convention collective applicable dans l'entreprise"


# --- Branding entreprise (logo, en-têtes PDF) ---

logger = logging.getLogger(__name__)

_LOGO_CACHE: dict[str, bytes] = {}
_LOGO_CACHE_MAX = 32
_NEANT_LABEL = "Néant"


def clear_logo_cache() -> None:
    """Vide le cache logo (tests)."""
    _LOGO_CACHE.clear()


def get_company_signatory(company: Dict[str, Any]) -> Tuple[str, str]:
    """Nom et qualité du signataire RH."""
    nom = (
        safe_str(company.get("nom_signataire_rh") or company.get("signatory_name"))
        or "Le service RH"
    )
    qual = safe_str(
        company.get("qualite_signataire_rh") or company.get("signatory_title")
    )
    return nom, qual


def resolve_company_logo(company_data: Dict[str, Any]) -> Optional[bytes]:
    """Télécharge le logo entreprise depuis logo_url (HTTP ou Supabase Storage)."""
    logo_url = safe_str(company_data.get("logo_url"))
    if not logo_url:
        return None
    if logo_url in _LOGO_CACHE:
        return _LOGO_CACHE[logo_url]

    raw: Optional[bytes] = None
    try:
        if logo_url.lower().startswith(("http://", "https://")):
            resp = requests.get(logo_url, timeout=8)
            resp.raise_for_status()
            raw = resp.content
        else:
            from app.modules.uploads.infrastructure.mappers import (
                storage_path_from_logo_url,
            )
            from app.core.database import supabase

            path = storage_path_from_logo_url(logo_url) or logo_url
            if path.startswith("logos/"):
                bucket_path = path[len("logos/") :]
            else:
                bucket_path = path
            data = supabase.storage.from_("logos").download(bucket_path)
            raw = bytes(data) if data is not None else None
    except Exception as exc:
        logger.warning("resolve_company_logo failed url=%s: %s", logo_url[:80], exc)
        return None

    if raw and len(_LOGO_CACHE) < _LOGO_CACHE_MAX:
        _LOGO_CACHE[logo_url] = raw
    return raw


def logo_to_base64_data_uri(logo_bytes: Optional[bytes]) -> str:
    """Data URI pour balise img HTML."""
    if not logo_bytes:
        return ""
    mime = "image/png"
    if logo_bytes[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif logo_bytes[:4] == b"RIFF":
        mime = "image/webp"
    b64 = base64.b64encode(logo_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def build_branding_header_html(
    company_data: Dict[str, Any], logo_bytes: Optional[bytes] = None
) -> str:
    """Bloc HTML en-tête entreprise (logo + coordonnées)."""
    if logo_bytes is None:
        logo_bytes = resolve_company_logo(company_data)
    logo_uri = logo_to_base64_data_uri(logo_bytes)
    name = get_company_name(company_data)
    addr = get_company_address(company_data)
    siret = safe_str(company_data.get("siret"))
    phone = safe_str(company_data.get("phone"))
    parts = ['<div class="company-header">']
    if logo_uri:
        parts.append(
            f'<img src="{logo_uri}" alt="Logo" style="max-width:120px;max-height:60px;margin-bottom:12px;" />'
        )
    parts.append(f"<p><strong>{name}</strong></p>")
    if addr:
        parts.append(f"<p>{addr}</p>")
    if siret:
        parts.append(f"<p>SIRET : {siret}</p>")
    if phone:
        parts.append(f"<p>Tél. : {phone}</p>")
    parts.append("</div>")
    return "\n".join(parts)


def build_branding_header_reportlab(
    story: List,
    styles: Any,
    company_data: Dict[str, Any],
    logo_bytes: Optional[bytes] = None,
) -> None:
    """En-tête ReportLab : logo + raison sociale + adresse + SIRET."""
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, Spacer

    if logo_bytes is None:
        logo_bytes = resolve_company_logo(company_data)
    if logo_bytes:
        try:
            img = Image(
                BytesIO(logo_bytes),
                width=3 * cm,
                height=1.5 * cm,
                kind="proportional",
            )
            story.append(img)
            story.append(Spacer(1, 0.2 * cm))
        except Exception as exc:
            logger.warning("Logo ReportLab ignoré: %s", exc)

    name = get_company_name(company_data)
    addr = get_company_address(company_data)
    siret = safe_str(company_data.get("siret"))
    phone = safe_str(company_data.get("phone"))
    lines = [f"<b>{name}</b>"]
    if addr:
        lines.append(addr.replace("\n", "<br/>"))
    if siret:
        lines.append(f"SIRET : {siret}")
    if phone:
        lines.append(f"Tél. : {phone}")

    try:
        header_style = styles["EntrepriseHeader"]
    except KeyError:
        header_style = styles["Normal"]
    story.append(Paragraph("<br/>".join(lines), header_style))
    story.append(Spacer(1, 0.6 * cm))


def format_amount_cell(amount: float) -> str:
    """Montant formaté ou « Néant » si nul."""
    if amount is None or safe_float(amount) <= 0:
        return _NEANT_LABEL
    return format_currency(safe_float(amount))
