"""
Schémas de réponse du module dashboard.

Source unique pour GET /api/dashboard/all et GET /api/dashboard/residence-permit-stats.
Le router legacy api/routers/dashboard.py les importe ici (compatibilité).
"""

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class KpiData(BaseModel):
    coutTotal: float
    netVerse: float
    effectifActif: int
    tauxAbsenteisme: float
    currentMonth: str  # Format "MM/YYYY"
    cdiCount: int
    cddCount: int
    contractDistribution: Dict[str, int] = {}
    hommesCount: Optional[int] = None
    femmesCount: Optional[int] = None
    handicapesCount: Optional[int] = None


class ChartDataPoint(BaseModel):
    name: str
    Net_Verse: float
    Charges: float


class ActionItems(BaseModel):
    pendingAbsences: int
    pendingExpenses: int


class AlertItems(BaseModel):
    obsoleteRates: int
    expiringContracts: int
    endOfTrialPeriods: int


class TeamPulseEmployee(BaseModel):
    id: str
    first_name: str
    last_name: str
    status: str


class TeamPulseEvent(BaseModel):
    id: str
    type: Literal["birthday", "work_anniversary"]
    employee_name: str
    date: date
    detail: str


class TeamPulse(BaseModel):
    absentToday: List[TeamPulseEmployee]
    upcomingEvents: List[TeamPulseEvent]


class SimpleEmployee(BaseModel):
    id: str
    first_name: str
    last_name: str


class PayrollStatus(BaseModel):
    currentMonth: str
    step: int
    totalSteps: int


class PayrollVariablesSummary(BaseModel):
    """Variables de paie à suivre (frais en attente, primes saisies, HS sur bulletins du mois de réf.)."""

    pending_expense_reports: int
    primes_saisies_count: int
    heures_sup_heures_reference_month: float


class PayrollAlertsSummary(BaseModel):
    """Alertes bloquantes avant export / génération."""

    employees_without_iban: int
    payslips_negative_net: int


class SalaryAdvancesMonthSummary(BaseModel):
    """Avances sur salaire : demandes en attente et volume du mois civil."""

    pending_count: int
    pending_requested_total_eur: float
    requested_in_calendar_month_count: int
    requested_in_calendar_month_total_eur: float


class HeuresSupMonthSummary(BaseModel):
    """Heures sup. agrégées bulletins : mois de référence KPI vs mois précédent."""

    hours_reference_month: float
    hours_previous_month: float


class ResidencePermitStats(BaseModel):
    total_expire: int
    total_a_renouveler: int
    total_a_renseigner: int
    total_valide: int


class DashboardData(BaseModel):
    kpis: KpiData
    chartData: List[ChartDataPoint]
    actions: ActionItems
    alerts: AlertItems
    teamPulse: TeamPulse
    employees: List[SimpleEmployee]
    payrollStatus: PayrollStatus
    payrollVariables: PayrollVariablesSummary
    payrollAlerts: PayrollAlertsSummary
    salaryAdvancesMonth: SalaryAdvancesMonthSummary
    heuresSupMonths: HeuresSupMonthSummary
