"""
Requêtes infrastructure monthly_inputs : DB + interprétation (payroll_config primes).

Lecture et parsing de config_data (str -> json, dict -> primes, list) identique à l'ancien routeur.
Aucune logique métier pure : uniquement accès DB et format de persistance.
"""
from __future__ import annotations

import json
from typing import Any, List

from app.core.database import supabase
from app.modules.monthly_inputs.domain.interfaces import IPrimesCatalogueProvider


def _parse_primes_config(config_data: Any) -> List[Any]:
    """Parse config_data (str, dict ou list) en liste de primes. Comportement identique au routeur legacy."""
    if config_data is None:
        return []
    if isinstance(config_data, str):
        try:
            config_data = json.loads(config_data)
        except json.JSONDecodeError:
            return []
    if isinstance(config_data, dict):
        return config_data.get("primes", [])
    if isinstance(config_data, list):
        return config_data
    return []


class SupabasePrimesCatalogueProvider(IPrimesCatalogueProvider):
    """Catalogue de primes depuis payroll_config (config_key=primes). Fetch + parsing en infrastructure."""

    def get_primes_catalogue(self) -> List[Any]:
        response = (
            supabase.table("payroll_config")
            .select("config_data")
            .eq("config_key", "primes")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not response.data or len(response.data) == 0:
            return []
        config_data = response.data[0].get("config_data")
        return _parse_primes_config(config_data)


primes_catalogue_provider = SupabasePrimesCatalogueProvider()
