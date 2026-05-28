import apiClient from '@/api/apiClient';

// --- Types ---

export interface ShiftType {
  id: string;
  code: string;
  label: string;
  color: string;
  default_start?: string;
  default_end?: string;
}

export interface Shift {
  id: string;
  company_id: string;
  employee_id: string;
  employee_first_name?: string;
  employee_last_name?: string;
  shift_type?: ShiftType;
  transverse_category?: string;
  shift_date: string;
  start_time: string;
  end_time: string;
  post?: string;
  location?: string;
  comment_internal?: string;
  comment_employee?: string;
  is_locked: boolean;
  source: string;
  is_replacement?: boolean;
  replacing_employee_id?: string | null;
  replacement_reason?: string | null;
  original_employee_id?: string | null;
  replacing_employee_name?: string | null;
  original_employee_name?: string | null;
}

export interface EmployeeForPlanning {
  id: string;
  first_name: string;
  last_name: string;
  duree_hebdomadaire?: number;
  job_title?: string;
}

export interface EmployeeHours {
  employee_id: string;
  total_minutes: number;
  contract_minutes: number;
  delta: number;
}

export interface WeekPlanning {
  week_start: string;
  week_end: string;
  status: string;
  payroll_transmitted: boolean;
  /** ISO 8601 si renvoyé par l’API après transmission paie */
  payroll_transmitted_at?: string;
  team_view_enabled: boolean;
  shifts: Shift[];
  employee_hours: EmployeeHours[];
}

export interface WeekStatus {
  week_start: string;
  status: string;
  locked_at?: string;
  payroll_transmitted: boolean;
  team_view_enabled: boolean;
}

export interface ShiftCreatePayload {
  employee_id: string;
  shift_type_id?: string | null;
  transverse_category?: string | null;
  shift_date: string;
  start_time: string;
  end_time: string;
  post?: string;
  location?: string;
  comment_internal?: string;
  comment_employee?: string;
  is_replacement?: boolean;
  replacing_employee_id?: string | null;
  replacement_reason?: string | null;
  original_employee_id?: string | null;
}

export interface ShiftUpdatePayload {
  shift_type_id?: string | null;
  transverse_category?: string | null;
  start_time?: string;
  end_time?: string;
  post?: string | null;
  location?: string | null;
  comment_internal?: string | null;
  comment_employee?: string | null;
}

export interface WeekDuplicatePayload {
  source_week_start: string;
  target_weeks: string[];
  include_comments?: boolean;
  skip_locked_days?: boolean;
  skip_absent_employees?: boolean;
}

export interface DuplicationResult {
  shifts_created: number;
  shifts_skipped: number;
  conflicts: Array<Record<string, unknown>>;
}

export type ShiftWithWarnings = Shift & {
  conflict_warnings?: Array<{
    type: string;
    message: string;
    details: Record<string, unknown>;
  }>;
};

// --- API ---

export async function getWeekPlanning(weekStart: string): Promise<WeekPlanning> {
  const { data } = await apiClient.get<WeekPlanning>('/api/planning/week', {
    params: { week_start: weekStart },
  });
  return data;
}

/** Shifts du mois (entreprise) — RH. `companyId` sert surtout aux clés React Query. */
export async function getMonthPlanning(
  _companyId: string,
  year: number,
  month: number
): Promise<Shift[]> {
  const { data } = await apiClient.get<Shift[]>('/api/planning/month', {
    params: { year, month },
  });
  return data ?? [];
}

/** Shifts du mois pour le salarié connecté. */
export async function getMyMonthPlanning(
  _companyId: string,
  year: number,
  month: number
): Promise<Shift[]> {
  const { data } = await apiClient.get<Shift[]>('/api/planning/me/month', {
    params: { year, month },
  });
  return data ?? [];
}

/** Astreintes du mois (RH). Année / mois omis → mois courant côté API. */
export async function getOnCallSchedule(
  _companyId: string,
  year?: number,
  month?: number
): Promise<Shift[]> {
  const params: { year?: number; month?: number } = {};
  if (year !== undefined) params.year = year;
  if (month !== undefined) params.month = month;
  const { data } = await apiClient.get<Shift[]>('/api/planning/on-call', {
    params: Object.keys(params).length ? params : undefined,
  });
  return data ?? [];
}

export async function createOnCallShift(
  _companyId: string,
  payload: ShiftCreatePayload
): Promise<ShiftWithWarnings> {
  const { data } = await apiClient.post<ShiftWithWarnings>(
    '/api/planning/on-call',
    payload
  );
  return data;
}

/** Remplacements du mois (RH). */
export async function getReplacements(
  _companyId: string,
  year?: number,
  month?: number
): Promise<Shift[]> {
  const params: { year?: number; month?: number } = {};
  if (year !== undefined) params.year = year;
  if (month !== undefined) params.month = month;
  const { data } = await apiClient.get<Shift[]>('/api/planning/replacements', {
    params: Object.keys(params).length ? params : undefined,
  });
  return data ?? [];
}

export async function createReplacement(
  _companyId: string,
  payload: ShiftCreatePayload
): Promise<ShiftWithWarnings> {
  const { data } = await apiClient.post<ShiftWithWarnings>(
    '/api/planning/replacements',
    payload
  );
  return data;
}

/** Liste des salariés actifs (entreprise active) pour la grille planning. */
export async function getEmployeesForPlanning(): Promise<EmployeeForPlanning[]> {
  const { fetchEmployeesSummary } = await import('@/api/employees');
  const rows = await fetchEmployeesSummary('active');
  return rows
    .filter((r) => {
      const status = r.employment_status;
      if (status === undefined || status === null) return true;
      const s = String(status).toLowerCase();
      return s === 'actif' || s === 'active';
    })
    .map((r) => ({
      id: String(r.id),
      first_name: r.first_name ?? '',
      last_name: r.last_name ?? '',
      duree_hebdomadaire:
        r.duree_hebdomadaire !== undefined && r.duree_hebdomadaire !== null
          ? Number(r.duree_hebdomadaire)
          : undefined,
      job_title: r.job_title ?? undefined,
    }));
}

export async function createShift(
  payload: ShiftCreatePayload
): Promise<ShiftWithWarnings> {
  const { data } = await apiClient.post<ShiftWithWarnings>(
    '/api/planning/shifts',
    payload
  );
  return data;
}

export async function updateShift(
  shiftId: string,
  payload: ShiftUpdatePayload
): Promise<ShiftWithWarnings> {
  const { data } = await apiClient.patch<ShiftWithWarnings>(
    `/api/planning/shifts/${shiftId}`,
    payload
  );
  return data;
}

export async function deleteShift(shiftId: string): Promise<void> {
  await apiClient.delete(`/api/planning/shifts/${shiftId}`);
}

export async function lockWeek(
  weekStart: string,
  reason?: string
): Promise<WeekStatus> {
  const { data } = await apiClient.post<WeekStatus>('/api/planning/week/lock', {
    week_start: weekStart,
    reason: reason ?? null,
  });
  return data;
}

export async function unlockWeek(
  weekStart: string,
  reason?: string
): Promise<WeekStatus> {
  const { data } = await apiClient.post<WeekStatus>('/api/planning/week/unlock', {
    week_start: weekStart,
    reason: reason ?? null,
  });
  return data;
}

export async function publishWeek(
  weekStart: string,
  publishDays?: string[]
): Promise<WeekStatus> {
  const body: Record<string, unknown> = { week_start: weekStart };
  if (publishDays !== undefined) {
    body.publish_days = publishDays;
  }
  const { data } = await apiClient.post<WeekStatus>(
    '/api/planning/week/publish',
    body
  );
  return data;
}

export async function duplicateWeek(
  payload: WeekDuplicatePayload
): Promise<DuplicationResult> {
  const { data } = await apiClient.post<DuplicationResult>(
    '/api/planning/week/duplicate',
    payload
  );
  return data;
}

export async function getShiftTypes(): Promise<ShiftType[]> {
  const { data } = await apiClient.get<ShiftType[]>('/api/planning/shift-types');
  return data;
}

export async function lockDay(dayDate: string, reason?: string): Promise<void> {
  await apiClient.post('/api/planning/day/lock', {
    day_date: dayDate,
    reason: reason ?? null,
  });
}

export async function unlockDay(dayDate: string, reason?: string): Promise<void> {
  await apiClient.post('/api/planning/day/unlock', {
    day_date: dayDate,
    reason: reason ?? null,
  });
}
