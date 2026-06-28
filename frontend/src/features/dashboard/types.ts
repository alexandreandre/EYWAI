export type PayrollSource = 'payslip' | 'dsn' | 'none';

export type ChartStackMode = 'employer_cost' | 'gross';

export interface PayrollKpiMeta {
  source: PayrollSource;
  source_label: string;
  gross: number;
  employer_cost: number;
  net: number;
  partial: boolean;
  has_mixed_sources: boolean;
}

export interface KpiData {
  coutTotal: number;
  netVerse: number;
  effectifActif: number;
  tauxAbsenteisme: number;
  currentMonth: string;
  cdiCount: number;
  cddCount: number;
  contractDistribution?: Record<string, number>;
  hommesCount?: number | null;
  femmesCount?: number | null;
  handicapesCount?: number | null;
  payroll: PayrollKpiMeta;
}

export interface ChartDataPoint {
  name: string;
  Net_Verse: number;
  Charges: number;
  stackMode?: ChartStackMode;
  source?: PayrollSource;
  period?: string;
}

export interface ActionItems {
  pendingAbsences: number;
  pendingExpenses: number;
}

export interface AlertItems {
  obsoleteRates: number;
  expiringContracts: number;
  endOfTrialPeriods: number;
}

export interface TeamPulseEmployee {
  id: string;
  first_name: string;
  last_name: string;
  status: string;
}

export interface TeamPulseEvent {
  id: string;
  type: 'birthday' | 'work_anniversary';
  employee_name: string;
  date: string;
  detail: string;
}

export type SimpleEmployee = {
  id: string;
  first_name: string;
  last_name: string;
};

export interface DashboardData {
  kpis: KpiData;
  chartData: ChartDataPoint[];
  actions: ActionItems;
  alerts: AlertItems;
  teamPulse: {
    absentToday: TeamPulseEmployee[];
    upcomingEvents: TeamPulseEvent[];
  };
  employees: SimpleEmployee[];
  payrollStatus: {
    currentMonth: string;
    step: number;
    totalSteps: number;
  };
}

export interface ResidencePermitStats {
  total_expire: number;
  total_a_renouveler: number;
  total_a_renseigner: number;
  total_valide: number;
}

export type DashboardPriorityKey = string;

export type PriorityValidationByCount = Record<string, number>;
