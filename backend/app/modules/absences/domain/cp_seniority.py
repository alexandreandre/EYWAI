"""Règles CP ancienneté (congés payés supplémentaires) — domaine pur."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.work_medals.domain.rules import career_reference_date

EmployeeCategory = Literal["ouvrier_etam", "cadre", "forfait", "all"]
SeniorityBasis = Literal[
    "company_only", "include_prior_service", "seniority_reference_date"
]
SeniorityReference = Literal["cp_period_end"]
CpSeniorityPreset = Literal["plasturgie_idcc_0292", "lewis_agreement", "custom"]
RulesMode = Literal["tier_total", "cumulative_rules"]

FORFAIT_ANNUAL_DAYS_DEFAULT = 216.0

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

LEWIS_AGREEMENT_RULES: dict[str, Any] = {
    "mode": "cumulative_rules",
    "tiers": [
        {"category": "all", "min_years": 2, "days": 1},
        {"category": "all", "min_years": 2, "min_age": 45, "days": 1},
        {"category": "all", "min_years": 20, "min_age": 55, "days": 1},
        {"category": "forfait", "min_years": 1, "days": 1},
    ],
}


@dataclass(frozen=True)
class CpSeniorityTierRule:
    category: EmployeeCategory
    min_years: float
    days: float
    min_age: float | None = None
    max_years: float | None = None


@dataclass(frozen=True)
class CpSeniorityRules:
    mode: RulesMode = "tier_total"
    tiers: tuple[CpSeniorityTierRule, ...] = ()


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

    @property
    def is_forfait(self) -> bool:
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


def resolve_effective_rules(settings: CpSenioritySettings) -> CpSeniorityRules:
    if settings.preset == "plasturgie_idcc_0292":
        return parse_cp_seniority_rules(PLASTURGIE_0292_RULES)
    if settings.preset == "lewis_agreement":
        return parse_cp_seniority_rules(LEWIS_AGREEMENT_RULES)
    return settings.rules


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


def _tier_matches_category(tier_cat: EmployeeCategory, employee_cat: EmployeeCategory) -> bool:
    if tier_cat == "all":
        return True
    if tier_cat == employee_cat:
        return True
    if employee_cat == "forfait" and tier_cat == "cadre":
        return True
    return False


def _tier_total_days(
    rules: CpSeniorityRules,
    category: EmployeeCategory,
    seniority_years: float,
    age_years: float | None,
) -> tuple[float, dict[str, Any] | None]:
    matching = [
        t
        for t in rules.tiers
        if _tier_matches_category(t.category, category)
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
) -> tuple[float, list[dict[str, Any]]]:
    total = 0.0
    matched: list[dict[str, Any]] = []
    for tier in rules.tiers:
        if not _tier_matches_category(tier.category, category):
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
            rules, category, seniority_years, age_years
        )
        if matched_list:
            tier_matched = {"matched": matched_list, "total": days}
    else:
        days, tier_matched = _tier_total_days(
            rules, category, seniority_years, age_years
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
