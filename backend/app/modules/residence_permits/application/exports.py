"""
Cas d'usage : export XLSX des titres de séjour pour un ensemble de salariés désignés.

Le navigateur envoie les identifiants des lignes qu'il affiche, jamais les critères
de filtrage. Ce module ne refiltre donc pas : il borne (via le lecteur), restaure
l'ordre demandé, puis délègue la mise en forme. La règle de filtrage n'existe qu'à
un seul endroit, l'écran, et le fichier correspond à l'affichage par construction.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.modules.residence_permits.application.service import (
    enrich_row_with_residence_permit_status,
)
from app.modules.residence_permits.infrastructure.export_xlsx import (
    build_export_filename,
    build_residence_permits_xlsx,
)
from app.modules.residence_permits.infrastructure.providers import (
    get_residence_permit_status_calculator,
)
from app.modules.residence_permits.infrastructure.repository import (
    ResidencePermitListRepository,
)

# Garde-fou : la plus grosse société compte 34 salariés soumis. Cette borne protège
# d'une requête forgée, elle n'est pas une limite fonctionnelle.
MAX_EXPORT_EMPLOYEES = 1000

_repo = ResidencePermitListRepository()


class ResidencePermitExportEmpty(Exception):
    """Aucun salarié exportable parmi les identifiants reçus."""


class ResidencePermitExportTooLarge(Exception):
    """Plus d'identifiants demandés que la borne autorisée."""


def _identifiants_normalises(employee_ids: Optional[List[str]]) -> List[str]:
    """Nettoie et déduplique en conservant l'ordre d'affichage."""
    vus: Dict[str, None] = {}
    for brut in employee_ids or []:
        valeur = str(brut).strip()
        if valeur and valeur not in vus:
            vus[valeur] = None
    return list(vus)


def export_residence_permits(
    company_id: str,
    company_name: str,
    employee_ids: Optional[List[str]],
    *,
    reader: Any = None,
    calculator: Any = None,
    today: Optional[date] = None,
) -> Tuple[bytes, str]:
    """
    Produit le fichier XLSX et son nom pour les salariés désignés.

    Lève ResidencePermitExportEmpty si rien n'est exportable, et
    ResidencePermitExportTooLarge au-delà de MAX_EXPORT_EMPLOYEES.
    """
    identifiants = _identifiants_normalises(employee_ids)
    if not identifiants:
        raise ResidencePermitExportEmpty("Aucun salarié à exporter")
    if len(identifiants) > MAX_EXPORT_EMPLOYEES:
        raise ResidencePermitExportTooLarge(
            f"Export limité à {MAX_EXPORT_EMPLOYEES} salariés par fichier"
        )

    lecteur = reader if reader is not None else _repo
    rows: List[Dict[str, Any]] = lecteur.get_employees_for_export(
        company_id, identifiants
    )
    if not rows:
        raise ResidencePermitExportEmpty("Aucun salarié à exporter")

    calculateur = (
        calculator
        if calculator is not None
        else get_residence_permit_status_calculator()
    )
    enrichies = [
        enrich_row_with_residence_permit_status(row, calculateur) for row in rows
    ]

    # PostgREST ne garantit aucun ordre sur un `IN` : on rétablit celui du navigateur,
    # qui est l'ordre d'urgence affiché à l'écran.
    rang = {identifiant: index for index, identifiant in enumerate(identifiants)}
    enrichies.sort(key=lambda row: rang.get(str(row.get("id")), len(identifiants)))

    contenu = build_residence_permits_xlsx(enrichies, company_name)
    return contenu, build_export_filename(company_name, today)
