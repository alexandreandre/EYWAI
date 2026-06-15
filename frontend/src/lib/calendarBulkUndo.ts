import * as calendarApi from '@/api/calendar';
import { runWithConcurrency } from './concurrency';

export interface PlannedSnapshot {
  id: string;
  planned: calendarApi.PlannedEventData[];
}

export interface ActualSnapshot {
  id: string;
  actual: calendarApi.ActualHoursData[];
}

/**
 * Restaure le calendrier prévu de plusieurs employés à partir d'instantanés
 * capturés avant une action en masse.
 */
export async function restorePlannedSnapshots(
  snapshots: PlannedSnapshot[],
  year: number,
  month: number
): Promise<void> {
  const tasks = snapshots.map(
    (snap) => () =>
      calendarApi.updatePlannedCalendar(snap.id, year, month, snap.planned)
  );
  await runWithConcurrency(tasks, 5);
}

/**
 * Restaure les heures réelles de plusieurs employés à partir d'instantanés
 * capturés avant une action en masse.
 */
export async function restoreActualSnapshots(
  snapshots: ActualSnapshot[],
  year: number,
  month: number
): Promise<void> {
  const tasks = snapshots.map(
    (snap) => () =>
      calendarApi.updateActualHours(snap.id, year, month, snap.actual)
  );
  await runWithConcurrency(tasks, 5);
}
