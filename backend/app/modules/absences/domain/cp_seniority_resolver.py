"""Résolution barèmes CP ancienneté — cascade CC / preset / custom (DRY)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.modules.absences.domain.cp_seniority_rules import (
    CpSeniorityRules,
    parse_cp_seniority_rules,
)

if TYPE_CHECKING:
    from app.modules.absences.domain.cp_seniority import CpSenioritySettings

# Barèmes canoniques (alignés seeds CC)
METALLURGIE_3248_RULES: dict[str, Any] = {
    "mode": "cumulative_rules",
    "tiers": [
        {"category": "all", "min_years": 2, "days": 1},
        {"category": "all", "min_years": 2, "min_age": 45, "days": 1},
        {"category": "all", "min_years": 20, "min_age": 55, "days": 1},
        {"category": "forfait", "min_years": 1, "days": 1},
    ],
}

PLASTURGIE_0292_RULES: dict[str, Any] = {
    "mode": "tier_total",
    "tiers": [
        {"category": "cadre", "min_years": 3, "days": 1},
        {"category": "cadre", "min_years": 5, "days": 2},
        {"category": "cadre", "min_years": 10, "days": 3},
        {"category": "ouvrier_etam", "min_years": 5, "days": 1},
        {"category": "ouvrier_etam", "min_years": 10, "days": 2},
    ],
}

# Alias rétrocompat client référence
LEWIS_AGREEMENT_RULES: dict[str, Any] = METALLURGIE_3248_RULES

_PRESET_RULES: dict[str, dict[str, Any]] = {
    "plasturgie_idcc_0292": PLASTURGIE_0292_RULES,
    "metallurgie_idcc_3248": METALLURGIE_3248_RULES,
    "lewis_agreement": LEWIS_AGREEMENT_RULES,
}

_IDCC_PRESET: dict[str, str] = {
    "0292": "plasturgie_idcc_0292",
    "1297": "plasturgie_idcc_0292",
    "3248": "metallurgie_idcc_3248",
}


def map_cc_cp_anciennete_to_rules(cc_data: dict[str, Any] | None) -> CpSeniorityRules | None:
    """Convertit un bloc cp_anciennete (JSON CC) en règles domaine absences."""
    if not cc_data:
        return None
    return parse_cp_seniority_rules(cc_data)


def resolve_barème_from_cc(idcc: str | None) -> tuple[CpSeniorityRules | None, str | None]:
    """
    Retourne (règles, source) depuis seed CC officiel.
    source : seed_officiel | None
    """
    if not idcc:
        return None, None
    norm = idcc.strip().lstrip("0") or idcc
    padded = idcc.zfill(4) if idcc.isdigit() else idcc
    for key in (idcc, norm, padded, idcc.zfill(4)):
        preset = _IDCC_PRESET.get(key)
        if preset and preset in _PRESET_RULES:
            return parse_cp_seniority_rules(_PRESET_RULES[preset]), "seed_officiel"
    try:
        from app.modules.collective_agreements.rules.seeds import get_seed_for_idcc

        seed = get_seed_for_idcc(idcc)
        if seed and seed.cp_anciennete:
            return map_cc_cp_anciennete_to_rules(seed.cp_anciennete.model_dump()), "seed_officiel"
    except Exception:
        pass
    try:
        from app.modules.collective_agreements.rules.repository import CCRulesRepository

        repo = CCRulesRepository()
        rules_doc = repo.get_rules_by_idcc(idcc)
        if rules_doc and rules_doc.get("cp_anciennete"):
            mapped = map_cc_cp_anciennete_to_rules(rules_doc["cp_anciennete"])
            if mapped and mapped.tiers:
                return mapped, "rules_extraites"
    except Exception:
        pass
    return None, None


def resolve_effective_cp_seniority_rules(
    settings: CpSenioritySettings,
) -> CpSeniorityRules:
    """Règles effectives : preset codé ou barème custom entreprise."""
    if settings.preset in _PRESET_RULES:
        return parse_cp_seniority_rules(_PRESET_RULES[settings.preset])
    return settings.rules


def recommended_preset_for_idcc(idcc: str | None) -> str | None:
    if not idcc:
        return None
    norm = idcc.strip().lstrip("0") or idcc
    for key in (idcc, norm, idcc.zfill(4)):
        if key in _IDCC_PRESET:
            return _IDCC_PRESET[key]
    return None
