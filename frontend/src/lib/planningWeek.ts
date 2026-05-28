import { format, startOfWeek } from 'date-fns';

/** Lundi de la semaine courante (aligné sur Planning.tsx). */
export function currentWeekStartIso(): string {
  return format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd');
}
