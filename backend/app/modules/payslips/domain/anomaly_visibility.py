"""
Règles de visibilité des anomalies paie (pilotage RH).

Sans I/O : utilisées par le rapport analytics et les jobs de purge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

ARCHIVED_EXIT_STATUS = "archivee"
LEFT_EMPLOYMENT_STATUSES = frozenset({"parti", "inactif"})

WARNING_TYPES_WHEN_SETTLED = frozenset(
    {
        "DELAI_VALIDATION",
        "TAUX_HORAIRE_INCOHERENT",
        "PRIMES_EXCESSIVES",
    }
)


def period_month_index(year: int, month: int) -> int:
    return year * 12 + month


def parse_date_value(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def is_period_after_last_working_day(
    last_working_day: Optional[date],
    year: int,
    month: int,
    *,
    date_debut_periode: Optional[date] = None,
) -> bool:
    """
    Le bulletin (year, month) est-il entièrement postérieur au départ ?

    Pour une société à arrêté glissant, le bulletin de juillet peut couvrir
    une période commençant fin juin : il porte alors le dernier salaire et le
    STC d'un départ au 30/06. Quand `date_debut_periode` est fournie, seul un
    bulletin dont la PÉRIODE démarre après le dernier jour travaillé est
    « postérieur » ; sinon, repli sur la comparaison au mois civil.
    """
    if last_working_day is None:
        return False
    if date_debut_periode is not None:
        return date_debut_periode > last_working_day
    return period_month_index(year, month) > period_month_index(
        last_working_day.year, last_working_day.month
    )


@dataclass(frozen=True)
class EmployeeAnomalyContext:
    employment_status: str
    exit_status: Optional[str] = None
    last_working_day: Optional[date] = None

    @property
    def is_definitively_left(self) -> bool:
        if str(self.exit_status or "").lower() == ARCHIVED_EXIT_STATUS:
            return True
        return str(self.employment_status or "").lower() in LEFT_EMPLOYMENT_STATUSES


def should_include_payslip_in_anomalies_report(
    ctx: EmployeeAnomalyContext,
    *,
    year: int,
    month: int,
) -> bool:
    """Exclut les bulletins postérieurs au dernier mois travaillé d'un salarié sorti."""
    if not ctx.is_definitively_left:
        return True
    return not is_period_after_last_working_day(ctx.last_working_day, year, month)


def should_include_anomaly_in_report(
    *,
    anomaly_type: str,
    severite: str,
    payslip_status: str,
    period_closed: bool,
    employee_ctx: EmployeeAnomalyContext,
) -> bool:
    """Filtre les anomalies devenues du bruit (période clos, sortie archivée, etc.)."""
    if employee_ctx.is_definitively_left and period_closed:
        return False

    if payslip_status == "valide":
        if severite == "avertissement":
            return False
        if anomaly_type.startswith("ALERTE_"):
            return False
        if anomaly_type in WARNING_TYPES_WHEN_SETTLED:
            return False

    return True


def is_system_config_anomaly(anomaly_type: str, valeur_detectee: str) -> bool:
    return valeur_detectee == "moteur_paie" and anomaly_type.startswith("ALERTE_")
