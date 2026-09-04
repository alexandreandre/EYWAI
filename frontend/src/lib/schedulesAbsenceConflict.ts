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

// Types d'absence qui n'écrivent JAMAIS le calendrier (aligné backend) : leurs
// jours restent « travail » par design — ce n'est pas un conflit.
const TYPES_SANS_CALENDRIER = new Set(['jtc', 'sans_solde']);

export function validatedAbsenceDaysInMonth(
  absences: AbsenceRequest[],
  year: number,
  month: number
): number[] {
  const days = new Set<number>();
  const prefix = `${year}-${String(month).padStart(2, '0')}-`;

  for (const a of absences) {
    if (a.status !== 'validated') continue;
    if (TYPES_SANS_CALENDRIER.has(a.type)) continue;
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
    if (type && ABSENCE_CALENDAR_TYPES.has(type)) {
      continue;
    }
    // Jours JAMAIS retypés par la projection (design « bornes calendaires ») :
    // 'repos'/'ferie' quel que soit le jour (temps partiels, fériés) ; le type
    // 'weekend' n'est normal QUE le samedi/dimanche — un jour de semaine typé
    // weekend sous une absence validée reste un vrai conflit.
    const jsDay = new Date(year, month - 1, day).getDay();
    const estSamediDimanche = jsDay === 0 || jsDay === 6;
    if (type === 'repos' || (type === 'weekend' && estSamediDimanche)) {
      continue;
    }
    if (!type && estSamediDimanche) {
      continue;
    }
    conflicts.push(day);
  }
  return conflicts;
}
