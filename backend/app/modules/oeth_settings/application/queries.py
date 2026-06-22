"""Lecture paramètres et calculs OETH."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.oeth_settings.application import calculator
from app.modules.oeth_settings.domain import rules
from app.modules.oeth_settings.domain.constants import SEUIL_ASSUJETTISSEMENT
from app.modules.oeth_settings.infrastructure.boeth_repository import (
    boeth_profiles_repository,
    oeth_annual_repository,
)
from app.modules.oeth_settings.infrastructure.headcount_service import (
    count_active_employees,
    ecap_job_codes,
    load_employees_for_oeth,
    load_oeth_config,
    load_smic_horaire,
)
from app.modules.oeth_settings.infrastructure.repository import oeth_settings_repository
from app.modules.oeth_settings.schemas.responses import (
    BoethExterne,
    BoethStatusHistoryItem,
    EmployeeBoethProfile,
    OethAnnualReview,
    OethCompliance,
    OethDeduction,
    OethDsnPayload,
    OethEcapPosition,
    OethSettings,
)


def _label_boeth(code: Optional[str], config: dict) -> Optional[str]:
    if not code:
        return None
    return (config.get("boeth_codes") or {}).get(code)


def _defaults(company_id: str) -> OethSettings:
    effectif = count_active_employees(company_id)
    return OethSettings(
        company_id=company_id,
        oeth_assujetti=effectif >= SEUIL_ASSUJETTISSEMENT,
        effectif_actif=effectif,
    )


def get_oeth_settings(company_id: str, employment_year: Optional[int] = None) -> OethSettings:
    year = employment_year or date.today().year
    config = load_oeth_config()
    raw = oeth_settings_repository.get_by_company(company_id)
    effectif = count_active_employees(company_id)
    if not raw:
        s = _defaults(company_id)
        s.effectif_actif = effectif
        return s
    settings = OethSettings.model_validate(raw)
    settings.effectif_actif = effectif
    if settings.oeth_assujetti_override is not None:
        settings.oeth_assujetti = settings.oeth_assujetti_override
    else:
        settings.oeth_assujetti = effectif >= int(config.get("seuil_assujettissement", 20))
    settings.neutralisation_active = rules.is_neutralisation_active(
        settings.date_franchissement_seuil_20, year, config
    )
    return settings


def get_employee_boeth(employee_id: str, company_id: str) -> Optional[EmployeeBoethProfile]:
    raw = boeth_profiles_repository.get_active_by_employee(employee_id)
    if not raw or raw.get("company_id") != company_id:
        return None
    config = load_oeth_config()
    prof = EmployeeBoethProfile.model_validate(raw)
    prof.boeth_label = _label_boeth(prof.boeth_code, config)
    return prof


def get_employee_boeth_history(employee_id: str) -> List[BoethStatusHistoryItem]:
    rows = boeth_profiles_repository.get_history(employee_id)
    return [BoethStatusHistoryItem.model_validate(r) for r in rows]


def get_compliance(company_id: str) -> OethCompliance:
    load_oeth_config()
    settings = get_oeth_settings(company_id)
    year = date.today().year
    employees = load_employees_for_oeth(company_id)
    codes = ecap_job_codes(company_id, year)
    ema = calculator.compute_ema_from_employees(employees, year, codes)
    ema_assuj = ema["ema_assujettissement"]
    ema_boeth = ema["ema_boeth_interne"]
    quota = rules.quota_boeth(ema_assuj, settings.taux_obligation)
    manquants = max(0, quota - int(ema_boeth))
    taux = round((ema_boeth / ema_assuj * 100) if ema_assuj > 0 else 0.0, 2)
    alertes: List[str] = []
    if settings.oeth_assujetti and manquants > 0:
        alertes.append(
            f"Écart OETH : {manquants} BOETH manquant(s) pour atteindre {settings.taux_obligation * 100:.0f} %."
        )
    if settings.oeth_assujetti and date.today().month >= 3:
        alertes.append("Préparer la DOETH annuelle (DSN d'avril).")
    accord_active = rules.is_accord_agree_active(
        settings.accord_agree_code,
        settings.accord_agree_valid_from,
        settings.accord_agree_valid_to,
        year,
    )
    return OethCompliance(
        effectif_actif=settings.effectif_actif or 0,
        boeth_count=boeth_profiles_repository.count_active_by_company(company_id),
        taux_emploi_pct=taux,
        quota_6_pct=quota,
        boeth_manquants=manquants,
        oeth_assujetti=settings.oeth_assujetti,
        neutralisation_active=settings.neutralisation_active,
        accord_agree_active=accord_active,
        alertes=alertes,
    )


def _deductions_map(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for r in rows:
        result[r["deduction_type"]] = float(r.get("amount_eur") or 0)
    return result


def compute_annual_review(company_id: str, year: int) -> OethAnnualReview:
    config = load_oeth_config()
    settings = get_oeth_settings(company_id, year)
    employees = load_employees_for_oeth(company_id)
    codes = ecap_job_codes(company_id, year)
    ema_calc = calculator.compute_ema_from_employees(employees, year, codes)

    externes_rows = oeth_annual_repository.list_externes(company_id, year)
    ema_externe = sum(float(r.get("annual_average_count") or 0) for r in externes_rows)
    deductions_rows = oeth_annual_repository.list_deductions(company_id, year)
    ecap_rows = oeth_annual_repository.list_ecap(company_id, year)
    history = oeth_annual_repository.list_reviews(company_id)

    existing = oeth_annual_repository.get_review(company_id, year) or {}

    ema_assuj = float(
        existing.get("urssaf_ema_assujettissement")
        or ema_calc["ema_assujettissement"]
    )
    ema_boeth_int = float(existing.get("urssaf_ema_boeth") or ema_calc["ema_boeth_interne"])
    ema_ecap = float(existing.get("urssaf_ema_ecap") or ema_calc["ema_ecap"])

    neutralisation = rules.is_neutralisation_active(
        settings.date_franchissement_seuil_20, year, config
    )
    accord_active = rules.is_accord_agree_active(
        settings.accord_agree_code,
        settings.accord_agree_valid_from,
        settings.accord_agree_valid_to,
        year,
    )
    surcontribution = calculator.compute_surcontribution(history, year, config)
    smic = load_smic_horaire(year)
    ded_map = _deductions_map(deductions_rows)

    calc = calculator.compute_annual_contribution(
        employment_year=year,
        ema_assujettissement=ema_assuj,
        ema_boeth_interne=ema_boeth_int,
        ema_boeth_externe=ema_externe,
        ema_ecap=ema_ecap,
        smic_horaire=smic,
        taux_obligation=settings.taux_obligation,
        deductions=ded_map,
        config=config,
        neutralisation_active=neutralisation,
        surcontribution_applicable=surcontribution and settings.oeth_assujetti,
        accord_agree_active=accord_active,
    )

    review_data = {
        "ema_assujettissement": ema_calc["ema_assujettissement"],
        "ema_boeth_interne": ema_calc["ema_boeth_interne"],
        "ema_boeth_externe": ema_externe,
        "ema_ecap": ema_calc["ema_ecap"],
        "boeth_manquants": calc["boeth_manquants"],
        "contribution_brute": calc["contribution_brute"],
        "contribution_nette": calc["contribution_nette"],
        "contribution_due": calc["contribution_due"],
        "deductions_detail": calc["deductions_detail"],
        "neutralisation_active": neutralisation,
        "surcontribution_applicable": surcontribution,
        "accord_agree_active": accord_active,
        "status": existing.get("status") or "draft",
        "urssaf_ema_assujettissement": existing.get("urssaf_ema_assujettissement"),
        "urssaf_ema_boeth": existing.get("urssaf_ema_boeth"),
        "urssaf_ema_ecap": existing.get("urssaf_ema_ecap"),
        "urssaf_notified_at": existing.get("urssaf_notified_at"),
        "declared_in_dsn_period": existing.get("declared_in_dsn_period"),
    }
    saved = oeth_annual_repository.upsert_review(company_id, year, review_data)

    review = OethAnnualReview.model_validate(saved)
    review.taux_emploi_pct = calc["taux_emploi_pct"]
    review.quota_boeth = calc["quota_boeth"]
    review.externes = [
        BoethExterne(
            **r,
            external_label=(config.get("external_types") or {}).get(r["external_type"]),
        )
        for r in externes_rows
    ]
    review.deductions = [
        OethDeduction(
            **r,
            deduction_label=(config.get("deduction_types") or {}).get(r["deduction_type"]),
        )
        for r in deductions_rows
    ]
    review.ecap_positions = [OethEcapPosition.model_validate(r) for r in ecap_rows]
    return review


def get_annual_review(company_id: str, year: int) -> OethAnnualReview:
    return compute_annual_review(company_id, year)


def build_dsn_payload(company_id: str, year: int) -> OethDsnPayload:
    review = compute_annual_review(company_id, year)
    settings = get_oeth_settings(company_id, year)
    config = load_oeth_config()

    complement: List[Dict[str, Any]] = []
    for ext in review.externes:
        complement.append(
            {
                "S21.G00.13.002": ext.external_type,
                "S21.G00.13.003": ext.annual_average_count,
            }
        )
    if settings.accord_agree_code and review.accord_agree_active:
        complement.append(
            {
                "S21.G00.13.001": settings.accord_agree_code,
                "S21.G00.13.004": str(year),
            }
        )

    debut = f"0101{year}"
    fin = f"3112{year}"
    cotisations: List[Dict[str, Any]] = []
    if settings.oeth_assujetti:
        cotisations.extend(
            [
                {
                    "S21.G00.82.001": f"{review.contribution_brute:.2f}",
                    "S21.G00.82.002": "065",
                    "S21.G00.82.003": debut,
                    "S21.G00.82.004": fin,
                },
                {
                    "S21.G00.82.001": f"{review.contribution_nette:.2f}",
                    "S21.G00.82.002": "066",
                    "S21.G00.82.003": debut,
                    "S21.G00.82.004": fin,
                },
                {
                    "S21.G00.82.001": f"{review.contribution_due:.2f}",
                    "S21.G00.82.002": "068",
                    "S21.G00.82.003": debut,
                    "S21.G00.82.004": fin,
                },
            ]
        )
        detail = review.deductions_detail or {}
        for code in ("060", "061", "062", "063", "064"):
            amount = detail.get(code)
            if amount and float(amount) > 0:
                cotisations.append(
                    {
                        "S21.G00.82.001": f"{float(amount):.2f}",
                        "S21.G00.82.002": code,
                        "S21.G00.82.003": debut,
                        "S21.G00.82.004": fin,
                    }
                )

    ctp = config.get("dsn", {}).get("ctp_contribution", "730")
    cotisation_agregee = None
    if settings.oeth_assujetti and review.contribution_due and review.contribution_due > 0:
        cotisation_agregee = {
            "S21.G00.23.002": ctp,
            "S21.G00.23.004": f"{review.contribution_due:.2f}",
        }

    return OethDsnPayload(
        employment_year=year,
        period_rattachement_debut=debut,
        period_rattachement_fin=fin,
        complement_oeth=complement,
        cotisations_etablissement=cotisations,
        cotisation_agregee=cotisation_agregee,
    )


def get_boeth_code_for_employee(employee_id: str, period: str) -> Optional[str]:
    """Code BOETH pour DSN mensuelle."""
    raw = boeth_profiles_repository.get_active_by_employee(employee_id)
    if not raw:
        return None
    year, month = map(int, period.split("-"))
    from datetime import date as date_cls
    import calendar

    month_start = date_cls(year, month, 1)
    month_end = date_cls(year, month, calendar.monthrange(year, month)[1])
    valid_from = raw.get("valid_from")
    valid_to = raw.get("valid_to")
    if valid_from:
        vf = date_cls.fromisoformat(str(valid_from)[:10])
        if vf > month_end:
            return None
    if valid_to:
        vt = date_cls.fromisoformat(str(valid_to)[:10])
        if vt < month_start:
            return None
    return raw.get("boeth_code")


def get_previous_boeth_for_period(employee_id: str, period: str) -> Optional[str]:
    change = boeth_profiles_repository.get_change_in_period(employee_id, period)
    if change:
        return change.get("previous_boeth_code")
    return None
