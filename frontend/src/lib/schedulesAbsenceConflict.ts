import type { PlannedEventData } from '@/api/calendar';
import type { AbsenceRequest } from '@/api/absences';

// Types calendrier que la validation d'absence peut écrire (aligné sur le
// backend, ABSENCE_TYPE_TO_CALENDAR_TYPE + le cas arrêt).
const ABSENCE_CALENDAR_TYPES = new Set([
  'conge',
  'conges_payes',
  'rtt',
  'arret_maladie',
  'ferie',
]);

// Jours JAMAIS retypés par la projection d'absence (design « bornes
// calendaires » : un arrêt couvre le week-end mais la case reste weekend/repos,
// sinon la paie sur-retiendrait). Leur présence dans selected_days est normale.
const NON_RETYPES = new Set(['weekend', 'repos', 'ferie']);

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
  validatedAbsenceDays: number[],
  year: number,
  month: number
): number[] {
  const conflicts: number[] = [];
  for (const day of validatedAbsenceDays) {
    const row = planned.find((p) => p.jour === day);
    const type = row?.type;
    if (type && (ABSENCE_CALENDAR_TYPES.has(type) || NON_RETYPES.has(type))) {
      continue;
    }
    // Pas de ligne planifiée : un samedi/dimanche d'absence est normal aussi.
    const jsDay = new Date(year, month - 1, day).getDay();
    if (!type && (jsDay === 0 || jsDay === 6)) {
      continue;
    }
    conflicts.push(day);
  }
  return conflicts;
}
