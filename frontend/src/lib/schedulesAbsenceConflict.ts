import type { PlannedEventData } from '@/api/calendar';
import type { AbsenceRequest } from '@/api/absences';

const ABSENCE_CALENDAR_TYPES = new Set(['conge', 'arret_maladie', 'ferie']);

export function validatedAbsenceDaysInMonth(
  absences: AbsenceRequest[],
  year: number,
  month: number
): number[] {
  const days = new Set<number>();
  const prefix = `${year}-${String(month).padStart(2, '0')}-`;

  for (const a of absences) {
    if (a.status !== 'validated') continue;
    for (const iso of a.selected_days ?? []) {
      if (iso.startsWith(prefix)) {
        const day = parseInt(iso.slice(8, 10), 10);
        if (!Number.isNaN(day)) days.add(day);
      }
    }
  }

  return [...days].sort((a, b) => a - b);
}

/** Jours avec absence validée non reflétée dans le calendrier paie. */
export function detectAbsenceConflictDays(
  planned: PlannedEventData[],
  validatedAbsenceDays: number[]
): number[] {
  const conflicts: number[] = [];
  for (const day of validatedAbsenceDays) {
    const row = planned.find((p) => p.jour === day);
    const type = row?.type;
    if (!type || !ABSENCE_CALENDAR_TYPES.has(type)) {
      conflicts.push(day);
    }
  }
  return conflicts;
}
