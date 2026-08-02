"""Règles CP ancienneté (congés payés supplémentaires) — domaine pur."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.modules.absences.domain.cp_seniority_rules import (
    CpSeniorityRules,
    CpSeniorityTierRule,
    parse_cp_seniority_rules,
)
from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.work_medals.domain.rules import career_reference_date

EmployeeCategory = Literal["ouvrier_etam", "cadre", "forfait", "all"]
SeniorityBasis = Literal[
    "company_only", "include_prior_service", "seniority_reference_date"
]
SeniorityReference = Literal["cp_period_end"]
CpSeniorityPreset = Literal[
    "plasturgie_idcc_0292",
    "lewis_agreement",
    "metallurgie_idcc_3248",
    "custom",
]
RulesMode = Literal["tier_total", "cumulative_rules"]

FORFAIT_ANNUAL_DAYS_DEFAULT = 216.0


def _preset_rules():
    from app.modules.absences.domain.cp_seniority_resolver import (
        LEWIS_AGREEMENT_RULES,
        METALLURGIE_3248_RULES,
        PLASTURGIE_0292_RULES,
    )
    return PLASTURGIE_0292_RULES, LEWIS_AGREEMENT_RULES, METALLURGIE_3248_RULES


PLASTURGIE_0292_RULES, LEWIS_AGREEMENT_RULES, METALLURGIE_3248_RULES = _preset_rules()

__all__ = [
    "PLASTURGIE_0292_RULES",
    "LEWIS_AGREEMENT_RULES",
    "METALLURGIE_3248_RULES",
    "CpSeniorityRules",
    "CpSeniorityTierRule",
    "parse_cp_seniority_rules",
]


@dataclass(frozen=True)
class CpSenioritySettings:
    enabled: bool = False
    preset: CpSeniorityPreset = "plasturgie_idcc_0292"
    seniority_reference: SeniorityReference = "cp_period_end"
    seniority_basis: SeniorityBasis = "company_only"
    counting_unit: Literal["ouvrable", "ouvre"] = "ouvrable"
    rules: CpSeniorityRules = field(default_factory=CpSeniorityRules)
    forfait_annual_days_default: float = FORFAIT_ANNUAL_DAYS_DEFAULT
    forfait_reduction_enabled: bool = True
    company_agreement_overrides: bool = False

    @property
    def is_active(self) -> bool:
        return self.enabled and not self.company_agreement_overrides

    @staticmethod
    def disabled() -> "CpSenioritySettings":
        return CpSenioritySettings()

    @staticmethod
    def plasturgie_default() -> "CpSenioritySettings":
        return CpSenioritySettings(
            enabled=False,
            preset="plasturgie_idcc_0292",
            rules=parse_cp_seniority_rules(PLASTURGIE_0292_RULES),
        )


@dataclass(frozen=True)
class EmployeeCpSeniorityContext:
    hire_date: date | None
    birth_date: date | None = None
    seniority_reference_date: date | None = None
    statut: str | None = None
    prior_service_months: int = 0
    is_cadre_dirigeant: bool = False
    forfait_annual_days_override: float | None = None
    is_forfait_jour: bool = False

    @property
    def is_forfait(self) -> bool:
        """Salarié en forfait-jours.

        La source est le drapeau `employees.is_forfait_jour`. Le repli sur le
        libellé du statut ne sert que pour les contextes construits à la main :
        en base, `statut` ne vaut que « Cadre » ou « Non-Cadre », si bien que
        chercher « forfait » dedans ne reconnaissait jamais personne.
        """
        if self.is_forfait_jour:
            return True
        if not self.statut:
            return False
        return "forfait" in self.statut.lower()


@dataclass(frozen=True)
class CpSeniorityGrantResult:
    days_granted: float
    category: EmployeeCategory | None
    seniority_years_at_ref: float
    forfait_days_reduction: float
    grant_year: int
    reference_date: date
    tier_matched: dict[str, Any] | None = None
    days_before_prorata: float = 0.0
    prorata_applied: bool = False
    prorata_ratio: float = 1.0
    warnings: tuple[str, ...] = ()

    @property
    def days_for_period_n(self) -> float:
        return self.days_granted

    @property
    def days_for_period_n1(self) -> float:
        return self.days_granted

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "days_granted": self.days_granted,
            "category": self.category,
            "seniority_years_at_ref": self.seniority_years_at_ref,
            "forfait_days_reduction": self.forfait_days_reduction,
            "grant_year": self.grant_year,
            "reference_date": self.reference_date.isoformat(),
            "tier_matched": self.tier_matched,
            "days_before_prorata": self.days_before_prorata,
            "prorata_applied": self.prorata_applied,
            "prorata_ratio": self.prorata_ratio,
            "warnings": list(self.warnings),
        }

    @staticmethod
    def zero(grant_year: int, reference_date: date) -> "CpSeniorityGrantResult":
        return CpSeniorityGrantResult(
            days_granted=0.0,
            category=None,
            seniority_years_at_ref=0.0,
            forfait_days_reduction=0.0,
            grant_year=grant_year,
            reference_date=reference_date,
        )


def resolve_effective_rules(settings: CpSenioritySettings) -> CpSeniorityRules:
    from app.modules.absences.domain.cp_seniority_resolver import (
        resolve_effective_cp_seniority_rules,
    )
    return resolve_effective_cp_seniority_rules(settings)


def resolve_employee_category(ctx: EmployeeCpSeniorityContext) -> EmployeeCategory:
    if ctx.is_forfait:
        return "forfait"
    statut = (ctx.statut or "").lower().replace("-", " ").replace("_", " ")
    if "non cadre" in statut or statut.replace(" ", "") in ("noncadre", "noncadres"):
        return "ouvrier_etam"
    if ctx.is_cadre_dirigeant or "cadre" in statut:
        return "cadre"
    return "ouvrier_etam"


def seniority_reference_date(
    ref_date: date,
    policy: LeavePolicySettings,
    settings: CpSenioritySettings,
) -> date:
    if settings.seniority_reference == "cp_period_end":
        from app.modules.absences.domain.rules import get_cp_reference_period

        _, period_end = get_cp_reference_period(
            ref_date, start_month=policy.cp_reference_period_start_month
        )
        return period_end
    return ref_date


def _employee_age_at(birth_date: date | None, reference_date: date) -> float | None:
    if not birth_date or birth_date > reference_date:
        return None
    return round((reference_date - birth_date).days / 365.25, 2)


def compute_seniority_years(
    ctx: EmployeeCpSeniorityContext,
    basis: SeniorityBasis,
    reference_date: date,
) -> float:
    hire_date = ctx.hire_date
    if basis == "seniority_reference_date" and ctx.seniority_reference_date:
        hire_date = ctx.seniority_reference_date
    if not hire_date or hire_date > reference_date:
        return 0.0
    if basis == "seniority_reference_date":
        start = hire_date
    else:
        start = career_reference_date(
            hire_date, ctx.prior_service_months, basis
        )
    if start > reference_date:
        return 0.0
    return round((reference_date - start).days / 365.25, 2)


def _tier_matches_category(
    tier_cat: EmployeeCategory,
    employee_cat: EmployeeCategory,
    *,
    is_cadre_dirigeant: bool = False,
) -> bool:
    if tier_cat == "all":
        return True
    if tier_cat == employee_cat:
        return True
    if employee_cat == "forfait" and tier_cat == "cadre":
        return True
    # Art. 89 métallurgie : palier forfait 1 an = forfait jour/heure + cadres dirigeants
    if tier_cat == "forfait" and employee_cat == "cadre" and is_cadre_dirigeant:
        return True
    return False


def _tier_total_days(
    rules: CpSeniorityRules,
    category: EmployeeCategory,
    seniority_years: float,
    age_years: float | None,
    *,
    is_cadre_dirigeant: bool = False,
) -> tuple[float, dict[str, Any] | None]:
    matching = [
        t
        for t in rules.tiers
        if _tier_matches_category(
            t.category, category, is_cadre_dirigeant=is_cadre_dirigeant
        )
        and seniority_years >= t.min_years
        and (t.max_years is None or seniority_years < t.max_years)
        and (t.min_age is None or (age_years is not None and age_years >= t.min_age))
    ]
    if not matching:
        return 0.0, None
    best = max(matching, key=lambda t: (t.min_years, t.days))
    return best.days, {
        "category": best.category,
        "min_years": best.min_years,
        "days": best.days,
        "min_age": best.min_age,
    }


def _cumulative_days(
    rules: CpSeniorityRules,
    category: EmployeeCategory,
    seniority_years: float,
    age_years: float | None,
    *,
    is_cadre_dirigeant: bool = False,
) -> tuple[float, list[dict[str, Any]]]:
    total = 0.0
    matched: list[dict[str, Any]] = []
    for tier in rules.tiers:
        if not _tier_matches_category(
            tier.category, category, is_cadre_dirigeant=is_cadre_dirigeant
        ):
            continue
        if seniority_years < tier.min_years:
            continue
        if tier.max_years is not None and seniority_years >= tier.max_years:
            continue
        if tier.min_age is not None and (
            age_years is None or age_years < tier.min_age
        ):
            continue
        total += tier.days
        matched.append(
            {
                "category": tier.category,
                "min_years": tier.min_years,
                "days": tier.days,
                "min_age": tier.min_age,
            }
        )
    return total, matched


def _has_age_tiers(rules: CpSeniorityRules) -> bool:
    return any(t.min_age is not None for t in rules.tiers)


def _compute_prorata_ratio(
    ctx: EmployeeCpSeniorityContext,
    ref: date,
    policy: LeavePolicySettings,
) -> tuple[float, bool]:
    """Prorata conventionnel : CP acquis / CP max sur la période de référence."""
    from app.modules.absences.domain.rules import (
        calculate_acquired_cp_for_period,
        get_cp_reference_period,
    )

    if not ctx.hire_date:
        return 1.0, False
    period_start, period_end = get_cp_reference_period(
        ref, start_month=policy.cp_reference_period_start_month
    )
    if ctx.hire_date <= period_start:
        return 1.0, False
    if ctx.hire_date > period_end:
        return 0.0, True
    acquired = calculate_acquired_cp_for_period(
        ctx.hire_date, period_start, period_end, policy=policy
    )
    max_acquired = calculate_acquired_cp_for_period(
        period_start, period_start, period_end, policy=policy
    )
    if max_acquired <= 0:
        return 1.0, False
    ratio = min(1.0, acquired / max_acquired)
    return ratio, ratio < 1.0


def _build_warnings(
    ctx: EmployeeCpSeniorityContext,
    settings: CpSenioritySettings,
    rules: CpSeniorityRules,
    age_years: float | None,
    prorata_applied: bool,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if _has_age_tiers(rules) and age_years is None and not ctx.birth_date:
        warnings.append("birth_date_missing")
    if (
        settings.seniority_basis == "seniority_reference_date"
        and not ctx.seniority_reference_date
    ):
        warnings.append("seniority_reference_date_missing")
    if prorata_applied:
        warnings.append("prorata_applied")
    return tuple(warnings)


def compute_cp_seniority_grant(
    settings: CpSenioritySettings,
    ctx: EmployeeCpSeniorityContext,
    ref_date: date,
    policy: LeavePolicySettings | None = None,
) -> CpSeniorityGrantResult:
    policy = policy or LeavePolicySettings()
    ref = seniority_reference_date(ref_date, policy, settings)
    grant_year = ref.year

    if not settings.is_active or not ctx.hire_date:
        return CpSeniorityGrantResult.zero(grant_year, ref)

    rules = resolve_effective_rules(settings)
    category = resolve_employee_category(ctx)
    seniority_years = compute_seniority_years(ctx, settings.seniority_basis, ref)
    age_years = _employee_age_at(ctx.birth_date, ref)

    tier_matched: dict[str, Any] | None = None
    if rules.mode == "cumulative_rules":
        days, matched_list = _cumulative_days(
            rules,
            category,
            seniority_years,
            age_years,
            is_cadre_dirigeant=ctx.is_cadre_dirigeant,
        )
        if matched_list:
            tier_matched = {"matched": matched_list, "total": days}
    else:
        days, tier_matched = _tier_total_days(
            rules,
            category,
            seniority_years,
            age_years,
            is_cadre_dirigeant=ctx.is_cadre_dirigeant,
        )

    days_before_prorata = days
    prorata_ratio, prorata_applied = _compute_prorata_ratio(ctx, ref, policy)
    if prorata_applied and days > 0:
        days = float(math.ceil(days * prorata_ratio))

    warnings = _build_warnings(
        ctx, settings, rules, age_years, prorata_applied
    )

    forfait_reduction = 0.0
    if days > 0 and ctx.is_forfait and settings.forfait_reduction_enabled:
        forfait_reduction = days

    return CpSeniorityGrantResult(
        days_granted=days,
        category=category,
        seniority_years_at_ref=seniority_years,
        forfait_days_reduction=forfait_reduction,
        grant_year=grant_year,
        reference_date=ref,
        tier_matched=tier_matched,
        days_before_prorata=days_before_prorata,
        prorata_applied=prorata_applied,
        prorata_ratio=round(prorata_ratio, 4),
        warnings=warnings,
    )


def resolve_forfait_annual_days(
    settings: CpSenioritySettings,
    ctx: EmployeeCpSeniorityContext,
    grant: CpSeniorityGrantResult,
) -> float:
    base = ctx.forfait_annual_days_override
    if base is None:
        base = settings.forfait_annual_days_default
    if settings.forfait_reduction_enabled and ctx.is_forfait:
        return max(0.0, round(base - grant.forfait_days_reduction, 2))
    return base
