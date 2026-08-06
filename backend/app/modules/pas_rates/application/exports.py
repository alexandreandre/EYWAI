"""Export XLSX du suivi des taux de prélèvement à la source."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple

from app.modules.pas_rates.application.service import construire_lignes
from app.modules.pas_rates.domain.model import periode_courante
from app.shared.utils.export import generate_xlsx

SHEET_NAME = "Taux PAS"

COL_NOM = "Nom"
COL_PRENOM = "Prénom"
COL_MATRICULE = "Matricule"
COL_SOCIETE = "Société"
COL_TAUX = "Taux (%)"
COL_ORIGINE = "Origine du taux"
COL_PERIODE = "Période du taux"
COL_SOURCE = "Provenance"
COL_STATUT = "Statut"

EXPORT_HEADERS: List[str] = [
    COL_NOM,
    COL_PRENOM,
    COL_MATRICULE,
    COL_SOCIETE,
    COL_TAUX,
    COL_ORIGINE,
    COL_PERIODE,
    COL_SOURCE,
    COL_STATUT,
]

_SOURCE_LABELS = {
    "dsn": "DSN mensuelle",
    "crm": "Compte rendu métier",
    "manuel": "Saisie RH",
}


def _slug(valeur: str) -> str:
    sans_accent = unicodedata.normalize("NFD", valeur or "")
    sans_accent = "".join(c for c in sans_accent if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Za-z0-9]+", "_", sans_accent).strip("_").lower()


def build_export_filename(company_name: str) -> str:
    societe = _slug(company_name) or "societe"
    return f"taux_pas_{societe}_{periode_courante()}.xlsx"


def export_taux_pas(company_id: str, company_name: str) -> Tuple[bytes, str]:
    """Exporte l'écran tel qu'il est vu, statut compris."""
    lignes = construire_lignes(company_id, company_name)
    data: List[Dict[str, Any]] = [
        {
            COL_NOM: ligne.nom,
            COL_PRENOM: ligne.prenom,
            COL_MATRICULE: ligne.matricule,
            COL_SOCIETE: company_name,
            # Cellule vide et non zéro : un taux inconnu n'est pas un taux nul,
            # même si le bulletin prélève 0 % dans les deux cas.
            COL_TAUX: "" if ligne.taux is None else ligne.taux,
            COL_ORIGINE: ligne.type_libelle,
            COL_PERIODE: ligne.periode or "",
            COL_SOURCE: _SOURCE_LABELS.get(ligne.source or "", ""),
            COL_STATUT: ligne.statut_libelle,
        }
        for ligne in lignes
    ]
    return generate_xlsx(data, EXPORT_HEADERS, SHEET_NAME), build_export_filename(
        company_name
    )
