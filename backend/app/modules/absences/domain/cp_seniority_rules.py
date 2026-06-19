"""Types et parsing barèmes CP ancienneté — sans dépendance resolver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RulesMode = Literal["tier_total", "cumulative_rules"]


@dataclass(frozen=True)
class CpSeniorityTierRule:
    category: Literal["ouvrier_etam", "cadre", "forfait", "all"]
    min_years: float
    days: float
    min_age: float | None = None
    max_years: float | None = None


@dataclass(frozen=True)
class CpSeniorityRules:
    mode: RulesMode = "tier_total"
    tiers: tuple[CpSeniorityTierRule, ...] = ()


def parse_cp_seniority_rules(raw: dict[str, Any] | None) -> CpSeniorityRules:
    if not raw:
        return CpSeniorityRules()
    mode = raw.get("mode") or "tier_total"
    if mode not in ("tier_total", "cumulative_rules"):
        mode = "tier_total"
    tiers_raw = raw.get("tiers") or []
    tiers: list[CpSeniorityTierRule] = []
    for t in tiers_raw:
        cat = t.get("category")
        if cat not in ("ouvrier_etam", "cadre", "forfait", "all"):
            continue
        min_age = t.get("min_age")
        max_years = t.get("max_years")
        tiers.append(
            CpSeniorityTierRule(
                category=cat,
                min_years=float(t.get("min_years") or 0),
                days=float(t.get("days") or 0),
                min_age=float(min_age) if min_age is not None else None,
                max_years=float(max_years) if max_years is not None else None,
            )
        )
    return CpSeniorityRules(mode=mode, tiers=tuple(tiers))
