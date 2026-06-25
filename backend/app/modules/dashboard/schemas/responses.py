"""
Schémas de réponse du module dashboard.

Source unique pour GET /api/dashboard/all et GET /api/dashboard/residence-permit-stats.
Le router legacy api/routers/dashboard.py les importe ici (compatibilité).
"""

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class PayrollKpiMeta(BaseModel):
    source: Literal["payslip", "dsn", "none"]
    source_label: str
    gross: float = 0
    employer_cost: float = 0
    net: float = 0
    partial: bool = False
    has_mixed_sources: bool = False


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
    payroll: PayrollKpiMeta


class ChartDataPoint(BaseModel):
    name: str
    Net_Verse: float
    Charges: float
    source: Optional[Literal["payslip", "dsn", "none"]] = None
    period: Optional[str] = None


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


class TurnoverStats(BaseModel):
    taux_turnover_annuel: float
    nb_departs_12_mois: int
    nb_embauches_12_mois: int
    taux_embauches: float
    taux_departs: float


class PyramideAge(BaseModel):
    tranche: str
    count: int
    pourcentage: float


class AbsentéismeDetail(BaseModel):
    taux_global: float
    taux_maladie: float
    taux_at: float
    taux_autres: float
    jours_perdus_total: int
    jours_perdus_maladie: int
    jours_perdus_at: int
    jours_perdus_autres: int
    evolution_vs_mois_precedent: float


class AnalyticsAvances(BaseModel):
    turnover: TurnoverStats
    pyramide_ages: List[PyramideAge]
    absenteisme: AbsentéismeDetail
    effectif_par_service: List[Dict]
    effectif_par_contrat: List[Dict]
    masse_salariale_par_service: List[Dict]
    effectif_actif: int = 0
    age_moyen: float = 0.0
    anciennete_moyenne_annees: float = 0.0
    masse_salariale_brute_totale: float = 0.0
    masse_salariale_source: Literal["contractual_base"] = "contractual_base"
