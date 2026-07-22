"""Résolution des surcharges mensuelles de paramètres paie salarié."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def resolve_monthly_specificites(
    specificites: Any,
    year: int,
    month: int,
) -> dict[str, Any]:
    """Applique la surcharge exacte ``AAAA-MM`` sans modifier la fiche permanente."""
    if not isinstance(specificites, dict):
        return {}
    base = deepcopy(specificites)
    overrides = base.pop("overrides_mensuels", {})
    if not isinstance(overrides, dict):
        return base
    override = overrides.get(f"{year:04d}-{month:02d}")
    if not isinstance(override, dict):
        return base
    return _deep_merge(base, override)


__all__ = ["resolve_monthly_specificites"]
