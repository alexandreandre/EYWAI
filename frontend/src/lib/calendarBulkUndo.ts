import * as calendarApi from '@/api/calendar';
import { runCalendarBatch } from './calendarBatch';

export interface CalendarUndoSnapshot {
  id: string;
  companyId: string;
  expectedRevision: string | null;
  planned?: calendarApi.PlannedEventData[];
  actual?: calendarApi.ActualHoursData[];
}

/** Le retour arrière est refusé si une autre saisie a changé le calendrier. */
export async function restoreCalendarSnapshots(snapshots: CalendarUndoSnapshot[], year: number, month: number): Promise<void> {
  await runCalendarBatch(snapshots.map((snapshot) => async () => {
    await calendarApi.saveCalendar(snapshot.id, year, month, {
      expected_revision: snapshot.expectedRevision,
      calendrier_prevu: snapshot.planned, calendrier_reel: snapshot.actual,
    }, { companyId: snapshot.companyId });
  }));
}
