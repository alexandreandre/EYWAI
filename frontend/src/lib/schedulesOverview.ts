import * as calendarApi from '@/api/calendar';
import { getAbsencesForEmployee } from '@/api/absences';
import type { PlannedEventData, ActualHoursData } from '@/api/calendar';
import { runWithConcurrency } from '@/lib/concurrency';
import {
  computeMonthStats,
  computeEmployeeRowStatus,
  type EmployeeRowStatus,
} from '@/lib/calendarStats';
import {
  detectAbsenceConflictDays,
  validatedAbsenceDaysInMonth,
} from '@/lib/schedulesAbsenceConflict';
import {
  buildBasePlannedCalendarWithHolidays,
} from '@/lib/companyCalendarHolidays';
import type { FrenchPublicHolidayId } from '@/lib/frenchPublicHolidays';
import { isForfaitJour } from '@/utils/employeeUtils';
import { downloadBlob } from '@/lib/downloadBlob';

export interface DayPatch {
  type?: string;
  heures_prevues?: number | null;
  heures_faites?: number | null;
}

export interface SchedulesEmployeeInput {
  id: string;
  first_name: string;
  last_name: string;
  job_title?: string | null;
  statut?: string | null;
  is_forfait_jour?: boolean | null;
  contract_type?: string | null;
  team_id?: string | null;
  employment_status?: string | null;
}

export interface EmployeeCalendarOverviewRow {
  employee: SchedulesEmployeeInput;
  planned: PlannedEventData[];
  actual: ActualHoursData[];
  heuresPrevues: number;
  heuresFaites: number;
  ecart: number;
  rowStatus: EmployeeRowStatus;
  absenceConflictDays: number[];
  loadError: boolean;
  isForfaitJour: boolean;
}

function buildBasePlannedCalendar(
  year: number,
  month: number,
  isForfaitJourMode: boolean,
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null
): PlannedEventData[] {
  return buildBasePlannedCalendarWithHolidays(
    year,
    month,
    isForfaitJourMode,
    observedHolidayIds
  );
}

function mergePlannedCalendar(
  base: PlannedEventData[],
  apiData: PlannedEventData[]
): PlannedEventData[] {
  return base.map((defaultDay) => {
    const apiDay = apiData.find((p) => p.jour === defaultDay.jour);
    return apiDay ? { ...defaultDay, ...apiDay } : defaultDay;
  });
}

async function fetchEmployeeOverview(
  employee: SchedulesEmployeeInput,
  year: number,
  month: number,
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null
): Promise<EmployeeCalendarOverviewRow> {
  const forfait = isForfaitJour(employee.statut, employee.is_forfait_jour);

  try {
    const [plannedRes, actualRes, absencesRes] = await Promise.all([
      calendarApi.getPlannedCalendar(employee.id, year, month),
      calendarApi.getActualHours(employee.id, year, month),
      getAbsencesForEmployee(employee.id),
    ]);

    const plannedFromApi: PlannedEventData[] =
      plannedRes.data.calendrier_prevu ?? [];
    const actualFromApi: ActualHoursData[] =
      actualRes.data.calendrier_reel ?? [];

    const base = buildBasePlannedCalendar(year, month, forfait, observedHolidayIds);
    const planned = mergePlannedCalendar(base, plannedFromApi);

    const actual: ActualHoursData[] = planned.map((plannedDay) => {
      const apiDay = actualFromApi.find((a) => a.jour === plannedDay.jour);
      return {
        jour: plannedDay.jour,
        type: plannedDay.type,
        heures_faites: apiDay ? apiDay.heures_faites : null,
      };
    });

    const stats = computeMonthStats(planned, actual, forfait);
    const rowStatus = computeEmployeeRowStatus(
      planned,
      actual,
      year,
      month,
      forfait
    );

    const validatedDays = validatedAbsenceDaysInMonth(
      absencesRes.data ?? [],
      year,
      month
    );
    const absenceConflictDays = detectAbsenceConflictDays(
      planned,
      validatedDays
    );

    return {
      employee,
      planned,
      actual,
      heuresPrevues: stats.heuresPrevues,
      heuresFaites: stats.heuresFaites,
      ecart: forfait ? stats.ecartJours : stats.ecart,
      rowStatus,
      absenceConflictDays,
      loadError: false,
      isForfaitJour: forfait,
    };
  } catch {
    return {
      employee,
      planned: buildBasePlannedCalendar(year, month, forfait, observedHolidayIds),
      actual: [],
      heuresPrevues: 0,
      heuresFaites: 0,
      ecart: 0,
      rowStatus: 'a_saisir',
      absenceConflictDays: [],
      loadError: true,
      isForfaitJour: forfait,
    };
  }
}

export async function fetchAllEmployeesOverview(
  employees: SchedulesEmployeeInput[],
  year: number,
  month: number,
  concurrency = 5,
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null
): Promise<EmployeeCalendarOverviewRow[]> {
  const tasks = employees.map(
    (emp) => () => fetchEmployeeOverview(emp, year, month, observedHolidayIds)
  );
  return runWithConcurrency(tasks, concurrency);
}

export interface GlobalOverviewKpis {
  total: number;
  saisis: number;
  aSaisir: number;
  avecEcart: number;
  conflitsAbsences: number;
  heuresPrevuesTotal: number;
  heuresFaitesTotal: number;
  progressPercent: number;
}

export function computeGlobalKpis(
  rows: EmployeeCalendarOverviewRow[]
): GlobalOverviewKpis {
  const total = rows.length;
  const saisis = rows.filter((r) => r.rowStatus !== 'a_saisir').length;
  const aSaisir = rows.filter((r) => r.rowStatus === 'a_saisir').length;
  const avecEcart = rows.filter((r) => r.rowStatus === 'saisi_avec_ecart').length;
  const conflitsAbsences = rows.filter(
    (r) => r.absenceConflictDays.length > 0
  ).length;
  const heuresPrevuesTotal = rows.reduce((s, r) => s + r.heuresPrevues, 0);
  const heuresFaitesTotal = rows.reduce((s, r) => s + r.heuresFaites, 0);
  const progressPercent =
    total > 0 ? Math.round((saisis / total) * 100) : 0;

  return {
    total,
    saisis,
    aSaisir,
    avecEcart,
    conflitsAbsences,
    heuresPrevuesTotal,
    heuresFaitesTotal,
    progressPercent,
  };
}

/** Calendriers du mois en cours encore à saisir (pastille sidebar / dashboard). */
export function countSchedulesToEnter(rows: EmployeeCalendarOverviewRow[]): number {
  return rows.filter((r) => !r.loadError && r.rowStatus === 'a_saisir').length;
}

/** Collaborateurs dont le calendrier du mois nécessite une action RH (écarts, conflits, saisie). */
export function countSchedulesAttention(rows: EmployeeCalendarOverviewRow[]): number {
  return rows.filter(
    (r) =>
      !r.loadError &&
      (r.rowStatus === 'a_saisir' ||
        r.rowStatus === 'saisi_avec_ecart' ||
        r.absenceConflictDays.length > 0),
  ).length;
}

export function applyDayPatchToRow(
  row: EmployeeCalendarOverviewRow,
  day: number,
  patch: DayPatch,
  year: number,
  month: number
): EmployeeCalendarOverviewRow {
  const newPlanned = row.planned.map((p) => {
    if (p.jour !== day) return p;
    return {
      ...p,
      type: patch.type !== undefined ? patch.type : p.type,
      heures_prevues:
        patch.heures_prevues !== undefined ? patch.heures_prevues : p.heures_prevues,
    };
  });
  const newActual = row.actual.map((a) => {
    if (a.jour !== day) return a;
    return {
      ...a,
      type: patch.type !== undefined ? patch.type : a.type,
      heures_faites:
        patch.heures_faites !== undefined ? patch.heures_faites : a.heures_faites,
    };
  });

  const stats = computeMonthStats(newPlanned, newActual, row.isForfaitJour);
  const rowStatus = computeEmployeeRowStatus(
    newPlanned,
    newActual,
    year,
    month,
    row.isForfaitJour
  );

  return {
    ...row,
    planned: newPlanned,
    actual: newActual,
    heuresPrevues: stats.heuresPrevues,
    heuresFaites: stats.heuresFaites,
    ecart: row.isForfaitJour ? stats.ecartJours : stats.ecart,
    rowStatus,
  };
}

export async function persistEmployeeMonth(
  employeeId: string,
  year: number,
  month: number,
  planned: PlannedEventData[],
  actual: ActualHoursData[]
): Promise<void> {
  await Promise.all([
    calendarApi.updatePlannedCalendar(employeeId, year, month, planned),
    calendarApi.updateActualHours(employeeId, year, month, actual),
  ]);
}

export type OverviewExportFormat = 'csv' | 'xlsx' | 'pdf';

export interface OverviewExportTable {
  monthLabel: string;
  filenameBase: string;
  headers: string[];
  records: string[][];
}

function statusExportLabel(status: EmployeeCalendarOverviewRow['rowStatus']): string {
  if (status === 'a_saisir') return 'À saisir';
  if (status === 'saisi_avec_ecart') return 'Écart à vérifier';
  return 'Saisi';
}

export function buildOverviewExportTable(
  rows: EmployeeCalendarOverviewRow[],
  year: number,
  month: number,
): OverviewExportTable {
  const monthLabel = new Date(year, month - 1).toLocaleString('fr-FR', {
    month: 'long',
    year: 'numeric',
  });
  const headers = [
    'Nom',
    'Prénom',
    'Poste',
    'Statut saisie',
    'H. prévues',
    'H. faites',
    'Écart',
    'Conflits absences (jours)',
    'Mois',
  ];
  const records = rows.map((r) => {
    const unit = r.isForfaitJour ? ' j' : ' h';
    return [
      r.employee.last_name,
      r.employee.first_name,
      r.employee.job_title ?? '',
      statusExportLabel(r.rowStatus),
      `${r.heuresPrevues.toFixed(1)}${unit}`,
      `${r.heuresFaites.toFixed(1)}${unit}`,
      `${r.ecart >= 0 ? '+' : ''}${r.ecart.toFixed(1)}${unit}`,
      r.absenceConflictDays.join('; ') || '—',
      monthLabel,
    ];
  });
  return {
    monthLabel,
    filenameBase: `calendriers-${year}-${String(month).padStart(2, '0')}`,
    headers,
    records,
  };
}

function escapeCsvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function exportOverviewCsv(
  rows: EmployeeCalendarOverviewRow[],
  year: number,
  month: number
): void {
  const table = buildOverviewExportTable(rows, year, month);
  const csv = [
    table.headers.map(escapeCsvCell).join(','),
    ...table.records.map((line) => line.map(escapeCsvCell).join(',')),
  ].join('\n');
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  downloadBlob(blob, `${table.filenameBase}.csv`);
}

export async function exportOverviewXlsx(
  rows: EmployeeCalendarOverviewRow[],
  year: number,
  month: number,
): Promise<void> {
  const table = buildOverviewExportTable(rows, year, month);
  const { loadExcelJS } = await import('@/lib/excelReport');
  const ExcelJS = await loadExcelJS();
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet('Calendriers');
  ws.addRow(table.headers);
  table.records.forEach((record) => ws.addRow(record));
  ws.columns.forEach((col) => {
    col.width = 18;
  });
  const buffer = await wb.xlsx.writeBuffer();
  downloadBlob(
    new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }),
    `${table.filenameBase}.xlsx`,
  );
}

export function exportOverviewPdf(
  rows: EmployeeCalendarOverviewRow[],
  year: number,
  month: number,
): void {
  const table = buildOverviewExportTable(rows, year, month);
  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>Calendriers — ${escapeHtml(table.monthLabel)}</title>
  <style>
    body { font-family: system-ui, sans-serif; font-size: 12px; color: #111; margin: 24px; }
    h1 { font-size: 16px; margin: 0 0 12px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
    th { background: #f4f4f4; font-weight: 600; }
  </style>
</head>
<body>
  <h1>Calendriers — ${escapeHtml(table.monthLabel)}</h1>
  <table>
    <thead><tr>${table.headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('')}</tr></thead>
    <tbody>
      ${table.records
        .map((record) => `<tr>${record.map((c) => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`)
        .join('')}
    </tbody>
  </table>
</body>
</html>`;
  const popup = window.open('', '_blank', 'noopener,noreferrer');
  if (!popup) {
    downloadBlob(new Blob([html], { type: 'text/html;charset=utf-8' }), `${table.filenameBase}.html`);
    return;
  }
  popup.document.write(html);
  popup.document.close();
  popup.focus();
  popup.print();
}
