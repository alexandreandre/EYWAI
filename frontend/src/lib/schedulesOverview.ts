import * as calendarApi from '@/api/calendar';
import { getAbsencesForEmployee } from '@/api/absences';
import type { PlannedEventData, ActualHoursData } from '@/api/calendar';
import { runWithConcurrency } from '@/lib/concurrency';
import {
  aDesHeuresPointees,
  computeMonthStats,
  computeEmployeeRowStatus,
  joursASaisir,
  moisPrecedent,
  pointeSurLaPeriode,
  type BornesDuMois,
  type EmployeeRowStatus,
  type JourASaisir,
} from '@/lib/calendarStats';
import { dernierJourDuContratDansLeMois } from '@/lib/employmentStatus';
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
import { statutAvecHeuresSurArret } from './calendrierPilotage';
import { joursAbsentsATyper } from './absentATyper';

export interface DayPatch {
  type?: string;
  heures_prevues?: number | null;
  heures_faites?: number | null;
  /** CP/RTT posé au calendrier : demi-journée (part avec la demande créée). */
  demi_journee?: 'matin' | 'apres_midi' | null;
}

export interface SchedulesEmployeeInput {
  id: string;
  first_name: string;
  last_name: string;
  nom_usage?: string | null;
  job_title?: string | null;
  statut?: string | null;
  is_forfait_jour?: boolean | null;
  contract_type?: string | null;
  team_id?: string | null;
  employment_status?: string | null;
  /** Dernier jour travaillé (sortie la plus récente), même après archivage. */
  exit_last_working_day?: string | null;
  hire_date?: string | null;
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
  /** Jours qui portent des heures réelles alors que le prévu est un arrêt ou une absence (API). */
  joursHeuresSurArret?: number[];
  /** Jours marqués « absent » à l'import, sans type encore : la paie est bloquée. */
  joursAbsentsATyper?: number[];
  loadError: boolean;
  revision?: string | null;
  companyId?: string;
  isForfaitJour: boolean;
  /**
   * Heures pointées le mois précédent (ou mois précédent illisible : règle
   * stricte). Absent : règle stricte. Sert au statut recalculé après une saisie.
   */
  pointeMoisPrecedent?: boolean;
  /**
   * Dernier jour jugé du mois : fin de la fenêtre des variables (les jours
   * d'après sont au mois suivant) ou dernier jour du contrat. `null` : tout le mois.
   */
  dernierJourJuge?: number | null;
  /** Dernier jour du contrat dans le mois (sortie) ; après, rien ne se saisit. */
  dernierJourContrat?: number | null;
  /** Jours qui empêchent la paie, avec la raison : l'alerte les nomme. */
  joursASaisir?: JourASaisir[];
}

/** Fin de la fenêtre des variables du mois affiché (ISO), si elle est connue. */
export interface ContexteDuMois {
  finFenetre?: string | null;
  companyId?: string;
}

/**
 * Les bornes de jugement d'un salarié : fin de la fenêtre des variables
 * (sauf forfait jours, jugé sur le mois civil comme au serveur) et sortie.
 */
export function bornesDuSalarie(
  employee: SchedulesEmployeeInput,
  year: number,
  month: number,
  forfait: boolean,
  contexte: ContexteDuMois = {},
): { bornes: BornesDuMois; dernierJourContrat: number | null } {
  const dernierJourContrat = dernierJourDuContratDansLeMois(employee, year, month);
  const prefixe = `${year}-${String(month).padStart(2, '0')}`;
  const fin = contexte.finFenetre?.slice(0, 10);
  const finFenetre =
    !forfait && fin && fin.startsWith(prefixe) ? Number(fin.slice(8, 10)) : null;
  const candidats = [finFenetre, dernierJourContrat].filter(
    (j): j is number => typeof j === 'number'
  );
  return {
    bornes: { dernierJour: candidats.length > 0 ? Math.min(...candidats) : null },
    dernierJourContrat,
  };
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
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null,
  contexte: ContexteDuMois = {}
): Promise<EmployeeCalendarOverviewRow> {
  const forfait = isForfaitJour(employee.statut, employee.is_forfait_jour);
  const { bornes, dernierJourContrat } = bornesDuSalarie(
    employee,
    year,
    month,
    forfait,
    contexte
  );

  try {
    const precedent = moisPrecedent(year, month);
    const [snapshot, absencesRes, reelMoisPrecedent] = await Promise.all([
      calendarApi.getCalendarSnapshot(employee.id, year, month, { companyId: contexte.companyId }),
      getAbsencesForEmployee(employee.id),
      // Lecture annexe : illisible, on garde la règle stricte (jamais d'erreur de ligne).
      calendarApi
        .getActualHours(employee.id, precedent.year, precedent.month)
        .then((res): ActualHoursData[] => res.data.calendrier_reel ?? [])
        .catch((): null => null),
    ]);

    if (snapshot.data.busy || snapshot.data.revision === undefined) throw new Error('Calendrier indisponible.');
    const plannedFromApi: PlannedEventData[] =
      snapshot.data.calendrier_prevu ?? [];
    const actualFromApi: ActualHoursData[] =
      snapshot.data.calendrier_reel ?? [];

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
    const pointeMoisPrecedent =
      reelMoisPrecedent === null || aDesHeuresPointees(reelMoisPrecedent);
    const joursHeuresSurArret: number[] = snapshot.data.jours_en_conflit ?? [];
    const joursAbsents = joursAbsentsATyper(planned);
    const pointe = pointeSurLaPeriode(actual, reelMoisPrecedent);
    const rowStatus = statutAvecHeuresSurArret(
      computeEmployeeRowStatus(planned, actual, year, month, forfait, pointe, bornes),
      joursHeuresSurArret
    );

    const validatedDays = validatedAbsenceDaysInMonth(
      absencesRes.data ?? [],
      year,
      month
    );
    const absenceConflictDays = detectAbsenceConflictDays(
      planned,
      validatedDays,
      year,
      month
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
      joursHeuresSurArret,
      joursAbsentsATyper: joursAbsents,
      loadError: false,
      revision: snapshot.data.revision,
      companyId: contexte.companyId,
      isForfaitJour: forfait,
      pointeMoisPrecedent,
      dernierJourJuge: bornes.dernierJour ?? null,
      dernierJourContrat,
      joursASaisir: joursASaisir(planned, actual, year, month, forfait, pointe, bornes),
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
      joursHeuresSurArret: [],
      loadError: true,
      isForfaitJour: forfait,
      dernierJourJuge: bornes.dernierJour ?? null,
      dernierJourContrat,
    };
  }
}

export async function fetchAllEmployeesOverview(
  employees: SchedulesEmployeeInput[],
  year: number,
  month: number,
  concurrency = 5,
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null,
  contexte: ContexteDuMois = {}
): Promise<EmployeeCalendarOverviewRow[]> {
  const tasks = employees.map(
    (emp) => () => fetchEmployeeOverview(emp, year, month, observedHolidayIds, contexte)
  );
  return runWithConcurrency(tasks, concurrency);
}

export interface GlobalOverviewKpis {
  total: number;
  saisis: number;
  aSaisir: number;
  avecEcart: number;
  /** Calendriers qui portent des heures sur un jour d'arrêt (génération refusée). */
  avecHeuresSurArret: number;
  /** Salariés avec au moins un jour « absent » sans type (génération refusée). */
  avecAbsentsATyper: number;
  conflitsAbsences: number;
  heuresPrevuesTotal: number;
  heuresFaitesTotal: number;
  /** Saisis et sans heures sur un jour d'arrêt : prêts pour la paie. */
  prets: number;
  /** Prêts parce que, sans aucune heure pointée, la paie reprend le prévu (hors forfait jours). */
  pretsSansHeuresPointees: number;
  progressPercent: number;
}

export function computeGlobalKpis(
  rows: EmployeeCalendarOverviewRow[]
): GlobalOverviewKpis {
  const total = rows.length;
  const saisis = rows.filter((r) => !r.loadError && r.rowStatus !== 'a_saisir').length;
  const aSaisir = rows.filter((r) => r.loadError || r.rowStatus === 'a_saisir').length;
  const avecEcart = rows.filter((r) => r.rowStatus === 'saisi_avec_ecart').length;
  const avecHeuresSurArret = rows.filter(
    (r) => (r.joursHeuresSurArret?.length ?? 0) > 0
  ).length;
  const avecAbsentsATyper = rows.filter(
    (r) => (r.joursAbsentsATyper?.length ?? 0) > 0
  ).length;
  const conflitsAbsences = rows.filter(
    (r) => r.absenceConflictDays.length > 0
  ).length;
  const heuresPrevuesTotal = rows.reduce((s, r) => s + r.heuresPrevues, 0);
  const heuresFaitesTotal = rows.reduce((s, r) => s + r.heuresFaites, 0);
  // Prêt = saisi, sans heures sur un jour d'arrêt ni jour absent sans type
  // (la génération serait refusée).
  const bloque = (r: EmployeeCalendarOverviewRow) =>
    r.loadError || (r.joursHeuresSurArret?.length ?? 0) > 0 || (r.joursAbsentsATyper?.length ?? 0) > 0;
  const prets = rows.filter((r) => r.rowStatus !== 'a_saisir' && !bloque(r)).length;
  const progressPercent = total > 0 ? Math.round((prets / total) * 100) : 0;
  const pretsSansHeuresPointees = rows.filter(
    (r) =>
      r.rowStatus !== 'a_saisir' &&
      !bloque(r) &&
      !r.isForfaitJour &&
      !aDesHeuresPointees(r.actual)
  ).length;

  return {
    total,
    saisis,
    aSaisir,
    avecEcart,
    avecHeuresSurArret,
    avecAbsentsATyper,
    conflitsAbsences,
    heuresPrevuesTotal,
    heuresFaitesTotal,
    prets,
    pretsSansHeuresPointees,
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
      ...(patch.demi_journee !== undefined ? { demi_journee: patch.demi_journee } : {}),
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
  const pointe = (row.pointeMoisPrecedent ?? true) || aDesHeuresPointees(newActual);
  const bornes: BornesDuMois = { dernierJour: row.dernierJourJuge ?? null };
  const rowStatus = statutAvecHeuresSurArret(
    computeEmployeeRowStatus(
      newPlanned,
      newActual,
      year,
      month,
      row.isForfaitJour,
      pointe,
      bornes
    ),
    row.joursHeuresSurArret
  );

  return {
    ...row,
    planned: newPlanned,
    actual: newActual,
    heuresPrevues: stats.heuresPrevues,
    heuresFaites: stats.heuresFaites,
    ecart: row.isForfaitJour ? stats.ecartJours : stats.ecart,
    rowStatus,
    joursAbsentsATyper: joursAbsentsATyper(newPlanned),
    joursASaisir: joursASaisir(
      newPlanned,
      newActual,
      year,
      month,
      row.isForfaitJour,
      pointe,
      bornes
    ),
  };
}

export async function persistEmployeeMonth(
  employeeId: string, year: number, month: number,
  planned: PlannedEventData[], actual: ActualHoursData[],
  context: calendarApi.CalendarRequestContext,
): Promise<calendarApi.CalendarSaveResult> {
  if (context.expectedRevision === undefined) throw new Error('Rechargez le calendrier avant de l’enregistrer.');
  const saved = await calendarApi.saveCalendar(employeeId, year, month, {
    expected_revision: context.expectedRevision, calendrier_prevu: planned, calendrier_reel: actual,
  }, context);
  return saved.data;
}

export function rowFromCalendarSnapshot(row: EmployeeCalendarOverviewRow, snapshot: calendarApi.CalendarSnapshot, year: number, month: number): EmployeeCalendarOverviewRow {
  const planned = mergePlannedCalendar(row.planned, snapshot.calendrier_prevu);
  const actual = planned.map((day) => ({
    jour: day.jour, type: day.type,
    heures_faites: snapshot.calendrier_reel.find((d) => d.jour === day.jour)?.heures_faites ?? null,
  }));
  return applyDayPatchToRow({ ...row, planned, actual, revision: snapshot.revision,
    joursHeuresSurArret: snapshot.jours_en_conflit ?? [], loadError: false,
  }, -1, {}, year, month);
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
