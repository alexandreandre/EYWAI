"""Paramètres congés / RTT — value objects domaine pur."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CpCountingUnit = Literal["ouvrable", "ouvre"]

CP_ACQUISITION_DAYS_PER_MONTH_DEFAULT = 2.5
CP_REFERENCE_PERIOD_START_MONTH_DEFAULT = 6
RTT_ANNUAL_DAYS_DEFAULT = 10.0
RTT_PERIOD_START_MONTH_DEFAULT = 1
RTT_PERIOD_END_MONTH_DEFAULT = 12
RTT_YEAR_END_REMINDER_DAYS_DEFAULT = 15
RTT_FORFAIT_ANNUAL_DAYS_DEFAULT = 214
RTT_FORFAIT_CP_OUVRES_DEDUCTION_DEFAULT = 25.0

# Affichage ouvrés : 25 j/an ≈ 2,08 j/mois (équivalent légal des 2,5 ouvrables).
CP_DAYS_PER_MONTH_OUVRE_DISPLAY = 25.0 / 12.0


@dataclass(frozen=True)
class LeavePolicySettings:
    """Politique congés / RTT entreprise. Defaults = comportement historique EYWAI."""

    cp_acquisition_days_per_month: float = CP_ACQUISITION_DAYS_PER_MONTH_DEFAULT
    cp_counting_unit: CpCountingUnit = "ouvrable"
    cp_reference_period_start_month: int = CP_REFERENCE_PERIOD_START_MONTH_DEFAULT
    cp_carryover_enabled: bool = False
    cp_carryover_max_days: float | None = None
    rtt_annual_days: float | None = None
    rtt_use_calendar_formula: bool = False
    rtt_use_forfait_jours_formula: bool = False
    rtt_forfait_annual_days: int = RTT_FORFAIT_ANNUAL_DAYS_DEFAULT
    rtt_forfait_cp_ouvres_deduction: float = RTT_FORFAIT_CP_OUVRES_DEDUCTION_DEFAULT
    rtt_forfait_cadres_only: bool = True
    rtt_period_start_month: int = RTT_PERIOD_START_MONTH_DEFAULT
    rtt_period_end_month: int = RTT_PERIOD_END_MONTH_DEFAULT
    rtt_carryover_enabled: bool = False
    rtt_year_end_reminder_enabled: bool = False
    rtt_year_end_reminder_days_before: int = RTT_YEAR_END_REMINDER_DAYS_DEFAULT

    @property
    def cp_acquisition_rate_internal(self) -> float:
        """Taux utilisé pour le calcul (toujours en jours ouvrables équivalents)."""
        if self.cp_counting_unit == "ouvre":
            # 2,08 ouvrés/mois → 2,5 ouvrables/mois en interne
            return CP_ACQUISITION_DAYS_PER_MONTH_DEFAULT
        return self.cp_acquisition_days_per_month

    @property
    def cp_acquisition_rate_display(self) -> float:
        """Taux affiché aux RH / salariés."""
        if self.cp_counting_unit == "ouvre":
            return round(CP_DAYS_PER_MONTH_OUVRE_DISPLAY, 2)
        return self.cp_acquisition_days_per_month

    @property
    def cp_annual_days_display(self) -> float:
        if self.cp_counting_unit == "ouvre":
            return 25.0
        return round(self.cp_acquisition_days_per_month * 12, 2)


@dataclass(frozen=True)
class EmployeeLeaveAdjustment:
    """Ajustement manuel / import historique pour un salarié sur une année."""

    cp_n1_opening_balance: float = 0.0
    cp_n_opening_balance: float = 0.0
    rtt_opening_balance: float = 0.0
    rtt_forfeited_at: str | None = None
    rtt_forfeited_days: float = 0.0
    note: str | None = None

    @staticmethod
    def empty() -> "EmployeeLeaveAdjustment":
        return EmployeeLeaveAdjustment()


DEFAULT_LEAVE_POLICY = LeavePolicySettings()
