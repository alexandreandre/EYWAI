"""
Entité domaine : formule de mutuelle du catalogue entreprise (MutuelleType).

Alignée sur la table company_mutuelle_types et le legacy schemas.mutuelle_type.MutuelleType.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=False)
class MutuelleType:
    """Formule de mutuelle du catalogue entreprise."""

    id: Optional[UUID]
    company_id: UUID
    libelle: str
    montant_salarial: float
    montant_patronal: float
    part_patronale_soumise_a_csg: bool
    is_active: bool
    pack_couverture: Optional[str] = None
    statut_categoriel: str = "tous"
    code_option_dsn: Optional[str] = None
    code_organisme_dsn: Optional[str] = None
    reference_contrat_dsn: Optional[str] = None
    organisme_label: Optional[str] = None
    note: Optional[str] = None
    source: str = "manual"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
