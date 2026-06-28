"""
Règles pures : résolution source paie (bulletins vs DSN) pour KPIs dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

PayrollMetric = Literal["gross", "employer_cost", "net"]
PayrollSource = Literal["payslip", "dsn", "none"]

DSN_FALLBACK_MODES = frozenset({"transition", "external"})

MONTH_NAMES_FR = {
    1: "janv.",
    2: "fév.",
    3: "mars",
    4: "avr.",
    5: "mai",
    6: "juin",
    7: "juil.",
    8: "août",
    9: "sept.",
    10: "oct.",
    11: "nov.",
    12: "déc.",
}


@dataclass(frozen=True)
class PayslipPeriodTotals:
    gross: float = 0.0
    net: float = 0.0
    employer_cost: float = 0.0
    employee_charges: float = 0.0
    employer_charges: float = 0.0
    payslip_count: int = 0


@dataclass(frozen=True)
class DsnPeriodTotals:
    gross: float = 0.0
    net_imposable: float = 0.0
    pas: float = 0.0
    employee_charges: float = 0.0
    employer_charges: float = 0.0
    employee_count: int = 0
    employees_with_gross: int = 0


@dataclass(frozen=True)
class PayrollPeriodSnapshot:
    period: str
    source: PayrollSource
    source_label: str
    gross: float
    net: float
    employer_cost: float
    employee_charges: float
    employer_charges: float
    partial: bool = False
    employee_count: Optional[int] = None


def extract_payslip_period_totals(payslip_data: Any) -> PayslipPeriodTotals:
    """Extrait brut, net et coût employeur d'un payslip_data EYWAI."""
    pd = payslip_data if isinstance(payslip_data, dict) else {}
    pied = pd.get("pied_de_page") if isinstance(pd.get("pied_de_page"), dict) else {}
    sc = (
        pd.get("structure_cotisations")
        if isinstance(pd.get("structure_cotisations"), dict)
        else {}
    )
    lines = sc.get("cotisations") if isinstance(sc.get("cotisations"), list) else []
    cot_sal = 0.0
    cot_pat = 0.0
    for line in lines:
        if not isinstance(line, dict):
            continue
        cot_sal += float(line.get("montant_salarial") or 0)
        cot_pat += float(line.get("montant_patronal") or 0)
    gross = float(pd.get("salaire_brut") or 0)
    if gross <= 0:
        remuneration = pd.get("remuneration") if isinstance(pd.get("remuneration"), dict) else {}
        gross = float(remuneration.get("brut") or 0)
    net = float(pd.get("net_a_payer") or 0)
    employer_cost = float(pied.get("cout_total_employeur") or 0)
    return PayslipPeriodTotals(
        gross=round(gross, 2),
        net=round(net, 2),
        employer_cost=round(employer_cost, 2),
        employee_charges=round(cot_sal, 2),
        employer_charges=round(cot_pat, 2),
        payslip_count=1,
    )


def aggregate_payslips_by_period(
    payslips: List[Dict[str, Any]],
) -> Dict[str, PayslipPeriodTotals]:
    """Agrège les bulletins par clé YYYY-MM."""
    out: Dict[str, PayslipPeriodTotals] = {}
    for row in payslips:
        month = row.get("month")
        year = row.get("year")
        if month is None or year is None:
            continue
        key = f"{int(year)}-{int(month):02d}"
        amounts = extract_payslip_period_totals(row.get("payslip_data"))
        prev = out.get(key)
        if prev:
            out[key] = PayslipPeriodTotals(
                gross=round(prev.gross + amounts.gross, 2),
                net=round(prev.net + amounts.net, 2),
                employer_cost=round(prev.employer_cost + amounts.employer_cost, 2),
                employee_charges=round(prev.employee_charges + amounts.employee_charges, 2),
                employer_charges=round(prev.employer_charges + amounts.employer_charges, 2),
                payslip_count=prev.payslip_count + 1,
            )
        else:
            out[key] = amounts
    return out


def dsn_row_to_totals(row: Optional[Dict[str, Any]]) -> DsnPeriodTotals:
    if not row:
        return DsnPeriodTotals()
    gross = float(row.get("gross_salary") or 0)
    net_imposable = float(row.get("net_imposable") or 0)
    employee_charges = float(row.get("employee_charges") or 0)
    employer_charges = float(row.get("employer_charges") or 0)
    if employee_charges <= 0 and gross > net_imposable:
        employee_charges = round(gross - net_imposable, 2)
    return DsnPeriodTotals(
        gross=gross,
        net_imposable=net_imposable,
        pas=float(row.get("pas") or 0),
        employee_charges=employee_charges,
        employer_charges=employer_charges,
        employee_count=int(row.get("employee_count") or 0),
        employees_with_gross=int(row.get("employees_with_gross") or 0),
    )


def format_period_label(period: str) -> str:
    parts = period.split("-")
    if len(parts) != 2:
        return period
    try:
        year, month = int(parts[0]), int(parts[1])
        return f"{MONTH_NAMES_FR.get(month, parts[1])} {year}"
    except ValueError:
        return period


def resolve_period_snapshot(
    period: str,
    *,
    payslip_totals: PayslipPeriodTotals,
    dsn_totals: DsnPeriodTotals,
    dsn_sync_mode: str,
) -> PayrollPeriodSnapshot:
    mode = (dsn_sync_mode or "native").strip().lower()
    period_label = format_period_label(period)

    if payslip_totals.gross > 0 or payslip_totals.employer_cost > 0:
        return PayrollPeriodSnapshot(
            period=period,
            source="payslip",
            source_label=f"Bulletins validés · {period_label}",
            gross=payslip_totals.gross,
            net=payslip_totals.net,
            employer_cost=payslip_totals.employer_cost,
            employee_charges=payslip_totals.employee_charges,
            employer_charges=payslip_totals.employer_charges,
            partial=False,
            employee_count=payslip_totals.payslip_count or None,
        )

    if mode in DSN_FALLBACK_MODES and dsn_totals.gross > 0:
        partial = (
            dsn_totals.employee_count > 0
            and dsn_totals.employees_with_gross < dsn_totals.employee_count
        )
        employee_charges = dsn_totals.employee_charges
        employer_charges = dsn_totals.employer_charges
        employer_cost = (
            round(dsn_totals.gross + employer_charges, 2) if employer_charges > 0 else 0.0
        )
        return PayrollPeriodSnapshot(
            period=period,
            source="dsn",
            source_label=f"Masse déclarée (DSN) · {period_label}",
            gross=dsn_totals.gross,
            net=dsn_totals.net_imposable,
            employer_cost=employer_cost,
            employee_charges=employee_charges,
            employer_charges=employer_charges,
            partial=partial,
            employee_count=dsn_totals.employee_count or None,
        )

    return PayrollPeriodSnapshot(
        period=period,
        source="none",
        source_label="Donnée indisponible",
        gross=0.0,
        net=0.0,
        employer_cost=0.0,
        employee_charges=0.0,
        employer_charges=0.0,
        partial=False,
        employee_count=None,
    )


def build_period_series(
    period_keys: List[str],
    payslips_by_period: Dict[str, PayslipPeriodTotals],
    dsn_by_period: Dict[str, DsnPeriodTotals],
    dsn_sync_mode: str,
) -> List[PayrollPeriodSnapshot]:
    return [
        resolve_period_snapshot(
            key,
            payslip_totals=payslips_by_period.get(key, PayslipPeriodTotals()),
            dsn_totals=dsn_by_period.get(key, DsnPeriodTotals()),
            dsn_sync_mode=dsn_sync_mode,
        )
        for key in period_keys
    ]


def series_has_mixed_sources(snapshots: List[PayrollPeriodSnapshot]) -> bool:
    sources = {s.source for s in snapshots if s.source != "none"}
    return len(sources) > 1


def primary_source(snapshots: List[PayrollPeriodSnapshot]) -> PayrollSource:
    for preferred in ("payslip", "dsn"):
        if any(s.source == preferred for s in snapshots):
            return preferred  # type: ignore[return-value]
    return "none"
