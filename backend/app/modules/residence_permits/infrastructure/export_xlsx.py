"""
Fabrication du fichier XLSX des titres de séjour.

Ce module ne connaît ni HTTP, ni entreprise active, ni provenance des lignes : il
reçoit des lignes déjà lues et enrichies du statut calculé. C'est ce qui le rend
réutilisable par un envoi planifié (cf. notifications/application/hr_deadline_reminders),
qui choisira ses propres lignes sans passer par un écran.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.shared.utils.export import generate_xlsx

SHEET_NAME = "Titres de séjour"

COL_NOM = "Nom"
COL_PRENOM = "Prénom"
COL_MATRICULE = "Matricule"
COL_SOCIETE = "Société"
COL_POSTE = "Poste"
COL_DATE_ENTREE = "Date d'entrée"
COL_NATIONALITE = "Nationalité"
COL_STATUT_EMPLOI = "Statut d'emploi"
COL_STATUT_TITRE = "Statut du titre"
COL_TYPE_TITRE = "Type de titre"
COL_NUMERO_TITRE = "Numéro de titre"
COL_DATE_EXPIRATION = "Date d'expiration"
COL_JOURS_RESTANTS = "Jours restants"

EXPORT_HEADERS: List[str] = [
    COL_NOM,
    COL_PRENOM,
    COL_MATRICULE,
    COL_SOCIETE,
    COL_POSTE,
    COL_DATE_ENTREE,
    COL_NATIONALITE,
    COL_STATUT_EMPLOI,
    COL_STATUT_TITRE,
    COL_TYPE_TITRE,
    COL_NUMERO_TITRE,
    COL_DATE_EXPIRATION,
    COL_JOURS_RESTANTS,
]

# Un statut absent signifie « données incomplètes » : c'est exactement ce que le
# calculateur renvoie pour un salarié soumis sans date d'expiration.
_STATUT_TITRE_LABELS = {
    "expired": "Expiré",
    "to_renew": "À renouveler",
    "to_complete": "À compléter",
    "valid": "Valide",
}
_STATUT_TITRE_DEFAUT = "À compléter"

_STATUT_EMPLOI_LABELS = {
    "actif": "Actif",
    "en_sortie": "En sortie",
}


def _texte(value: Any) -> str:
    """Cellule vide plutôt que « None » : Excel doit pouvoir filtrer sur le vide."""
    if value is None:
        return ""
    return str(value)


def _date_fr(value: Any) -> str:
    """Formate en JJ/MM/AAAA ; rend la valeur brute si elle n'est pas une date."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(value)


def _statut_titre(value: Any) -> str:
    return _STATUT_TITRE_LABELS.get(str(value or ""), _STATUT_TITRE_DEFAUT)


def _statut_emploi(value: Any) -> str:
    brut = str(value or "")
    return _STATUT_EMPLOI_LABELS.get(brut, brut)


def _jours_restants(value: Any) -> Any:
    """Reste un entier — un titre expiré porte une valeur négative, triable dans Excel."""
    if value is None or value == "":
        return ""
    try:
        return int(value)
    except (TypeError, ValueError):
        return ""


def _ligne_export(row: Dict[str, Any], company_name: str) -> Dict[str, Any]:
    return {
        COL_NOM: _texte(row.get("last_name")),
        COL_PRENOM: _texte(row.get("first_name")),
        COL_MATRICULE: _texte(row.get("matricule")),
        COL_SOCIETE: _texte(company_name),
        COL_POSTE: _texte(row.get("job_title")),
        COL_DATE_ENTREE: _date_fr(row.get("hire_date")),
        COL_NATIONALITE: _texte(row.get("nationalite")),
        COL_STATUT_EMPLOI: _statut_emploi(row.get("employment_status")),
        COL_STATUT_TITRE: _statut_titre(row.get("residence_permit_status")),
        COL_TYPE_TITRE: _texte(row.get("residence_permit_type")),
        COL_NUMERO_TITRE: _texte(row.get("residence_permit_number")),
        COL_DATE_EXPIRATION: _date_fr(row.get("residence_permit_expiry_date")),
        COL_JOURS_RESTANTS: _jours_restants(row.get("residence_permit_days_remaining")),
    }


def build_residence_permits_xlsx(
    rows: List[Dict[str, Any]], company_name: str
) -> bytes:
    """
    Fabrique le classeur à partir de lignes déjà enrichies du statut calculé.

    L'ordre des lignes reçues est conservé tel quel : c'est l'appelant qui décide
    du tri (à l'écran, l'ordre d'urgence affiché).
    """
    data = [_ligne_export(row, company_name) for row in rows]
    return generate_xlsx(data, EXPORT_HEADERS, SHEET_NAME)


def _slug(value: str) -> str:
    """Réduit un nom de société aux caractères sûrs dans un nom de fichier."""
    normalise = unicodedata.normalize("NFKD", str(value or ""))
    ascii_only = normalise.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")


def build_export_filename(company_name: str, today: Optional[date] = None) -> str:
    """Nom du fichier proposé au téléchargement."""
    reference = today or date.today()
    return (
        f"titres-de-sejour_{_slug(company_name) or 'entreprise'}"
        f"_{reference.isoformat()}.xlsx"
    )
