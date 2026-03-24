"""
Entités du domaine companies.

Placeholder : structure cible pour la migration.
L'entité Company représentera l'agrégat entreprise (données + settings).
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Company:
    """
    Agrégat entreprise.
    Champs alignés sur la table companies (à compléter lors de la migration).
    """
    id: str
    company_name: str
    siret: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_active: bool = True
    # Autres champs (effectif, group_id, logo_url, etc.) à ajouter si besoin
