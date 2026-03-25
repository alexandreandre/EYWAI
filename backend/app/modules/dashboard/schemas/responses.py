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
