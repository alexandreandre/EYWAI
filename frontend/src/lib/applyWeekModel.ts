import type { ActualHoursData, PlannedEventData } from '@/api/calendar';

export type ApplyModelDayConfig = { type: string; hours: number };

export type ApplyModelWeekConfig = {
  monday: ApplyModelDayConfig;
  tuesday: ApplyModelDayConfig;
  wednesday: ApplyModelDayConfig;
  thursday: ApplyModelDayConfig;
  friday: ApplyModelDayConfig;
  saturday: ApplyModelDayConfig;
  sunday: ApplyModelDayConfig;
};

export type WeekConfigMap = Record<1 | 2 | 3 | 4 | 5, ApplyModelWeekConfig>;

export type ApplyModelTarget = 'planned' | 'actual' | 'both';

const DAY_KEYS = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

/** Lundi = 0 … dimanche = 6, comme `datetime.date.weekday()` côté serveur. */
function pythonWeekday(year: number, month: number, day: number): number {
  const jsSundayZero = new Date(year, month - 1, day).getDay();
  return (jsSundayZero + 6) % 7;
}

/**
 * Numéro de semaine du mois (1–5) identique à `apply_schedule_model`.
 * Semaine 1 = celle qui contient le 1er du mois, pas la semaine ISO.
 */
export function weekNumberForMonthDay(
  year: number,
  month: number,
  day: number,
): 1 | 2 | 3 | 4 | 5 {
  const firstWeekday = pythonWeekday(year, month, 1);
  const weekOfMonth = Math.floor((day + firstWeekday - 1) / 7) + 1;
  return Math.min(weekOfMonth, 5) as 1 | 2 | 3 | 4 | 5;
}

function isWorkDay(type: string): boolean {
  return type === 'work' || type === 'travail';
}

function hoursForDay(
  config: ApplyModelDayConfig,
  isForfaitJour: boolean,
): number {
  const work = isWorkDay(config.type);
  if (isForfaitJour) return work ? 1 : 0;
  return work ? config.hours : 0;
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function fallbackType(year: number, month: number, day: number): string {
  return pythonWeekday(year, month, day) >= 5 ? 'weekend' : 'travail';
}

function shouldPreserveAbsence(planned?: PlannedEventData): boolean {
  return planned?.origine === 'absence';
}

export function sameWeekConfigAllMonth(
  config: ApplyModelWeekConfig,
): WeekConfigMap {
  return { 1: config, 2: config, 3: config, 4: config, 5: config };
}

export function buildActualEntriesFromWeekConfig(
  year: number,
  month: number,
  weekConfig: ApplyModelWeekConfig,
  isForfaitJour: boolean,
  options?: {
    existing?: ActualHoursData[];
    planned?: PlannedEventData[];
    onlyDays?: number[];
  },
): ActualHoursData[] {
  const existingByDay = new Map(
    (options?.existing ?? []).map((d) => [d.jour, d]),
  );
  const plannedByDay = new Map(
    (options?.planned ?? []).map((d) => [d.jour, d]),
  );
  const onlyDays = options?.onlyDays ? new Set(options.onlyDays) : null;
  const entries: ActualHoursData[] = [];
  const lastDay = daysInMonth(year, month);

  for (let day = 1; day <= lastDay; day += 1) {
    const planned = plannedByDay.get(day);
    const existing = existingByDay.get(day);

    if (onlyDays && !onlyDays.has(day)) {
      entries.push(
        existing ?? {
          jour: day,
          type: planned?.type ?? fallbackType(year, month, day),
          heures_faites: null,
        },
      );
      continue;
    }

    if (shouldPreserveAbsence(planned)) {
      entries.push({
        jour: day,
        type: existing?.type ?? planned?.type ?? 'travail',
        heures_faites: existing?.heures_faites ?? 0,
      });
      continue;
    }

    const dayKey = DAY_KEYS[pythonWeekday(year, month, day)];
    const dayConfig = weekConfig[dayKey];
    entries.push({
      jour: day,
      type: dayConfig.type,
      heures_faites: hoursForDay(dayConfig, isForfaitJour),
    });
  }

  return entries;
}

export function buildPlannedEntriesFromWeekConfig(
  year: number,
  month: number,
  weekConfig: ApplyModelWeekConfig,
  isForfaitJour: boolean,
  options?: {
    existing?: PlannedEventData[];
    onlyDays?: number[];
  },
): PlannedEventData[] {
  const existingByDay = new Map(
    (options?.existing ?? []).map((d) => [d.jour, d]),
  );
  const onlyDays = options?.onlyDays ? new Set(options.onlyDays) : null;
  const entries: PlannedEventData[] = [];
  const lastDay = daysInMonth(year, month);

  for (let day = 1; day <= lastDay; day += 1) {
    const existing = existingByDay.get(day);

    if (onlyDays && !onlyDays.has(day)) {
      entries.push(
        existing ?? {
          jour: day,
          type: fallbackType(year, month, day),
          heures_prevues: null,
        },
      );
      continue;
    }

    if (shouldPreserveAbsence(existing)) {
      entries.push(existing);
      continue;
    }

    const dayKey = DAY_KEYS[pythonWeekday(year, month, day)];
    const dayConfig = weekConfig[dayKey];
    entries.push({
      jour: day,
      type: dayConfig.type,
      heures_prevues: hoursForDay(dayConfig, isForfaitJour),
    });
  }

  return entries;
}

