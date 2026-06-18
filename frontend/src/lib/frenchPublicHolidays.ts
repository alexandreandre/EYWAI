/** Jours fériés légaux France métropolitaine (fixes + Pâques, Ascension, Pentecôte). */

function easterSunday(year: number): Date {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(year, month - 1, day);
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

export const FRENCH_PUBLIC_HOLIDAY_IDS = [
  'new_year',
  'easter_monday',
  'labor_day',
  'victory_day',
  'ascension',
  'whit_monday',
  'bastille_day',
  'assumption',
  'all_saints',
  'armistice',
  'christmas',
] as const;

export type FrenchPublicHolidayId = (typeof FRENCH_PUBLIC_HOLIDAY_IDS)[number];

export const LABOR_DAY_HOLIDAY_ID: FrenchPublicHolidayId = 'labor_day';

type HolidayDefinition = {
  label: string;
  fixed?: [month: number, day: number];
  easterOffset?: number;
};

export const FRENCH_PUBLIC_HOLIDAY_DEFINITIONS: Record<
  FrenchPublicHolidayId,
  HolidayDefinition
> = {
  new_year: { label: "Jour de l'An", fixed: [1, 1] },
  easter_monday: { label: 'Lundi de Pâques', easterOffset: 1 },
  labor_day: { label: '1er mai', fixed: [5, 1] },
  victory_day: { label: '8 mai', fixed: [5, 8] },
  ascension: { label: 'Ascension', easterOffset: 39 },
  whit_monday: { label: 'Lundi de Pentecôte', easterOffset: 50 },
  bastille_day: { label: '14 juillet', fixed: [7, 14] },
  assumption: { label: 'Assomption', fixed: [8, 15] },
  all_saints: { label: 'Toussaint', fixed: [11, 1] },
  armistice: { label: '11 novembre', fixed: [11, 11] },
  christmas: { label: 'Noël', fixed: [12, 25] },
};

export type FrenchPublicHolidayInstance = {
  id: FrenchPublicHolidayId;
  label: string;
  month: number;
  day: number;
};

export function isFrenchPublicHolidayId(value: string): value is FrenchPublicHolidayId {
  return (FRENCH_PUBLIC_HOLIDAY_IDS as readonly string[]).includes(value);
}

export function getDefaultObservedHolidayIds(): FrenchPublicHolidayId[] {
  return [...FRENCH_PUBLIC_HOLIDAY_IDS];
}

/** Normalise la liste des fériés chômés (1er mai toujours inclus). */
export function normalizeObservedHolidayIds(
  observedIds?: readonly FrenchPublicHolidayId[] | null
): FrenchPublicHolidayId[] {
  if (!observedIds || observedIds.length === 0) {
    return getDefaultObservedHolidayIds();
  }
  const allowed = new Set<FrenchPublicHolidayId>(
    observedIds.filter(isFrenchPublicHolidayId)
  );
  allowed.add(LABOR_DAY_HOLIDAY_ID);
  return FRENCH_PUBLIC_HOLIDAY_IDS.filter((id) => allowed.has(id));
}

export function getHolidayInstances(year: number): FrenchPublicHolidayInstance[] {
  const easter = easterSunday(year);
  const instances: FrenchPublicHolidayInstance[] = [];

  for (const id of FRENCH_PUBLIC_HOLIDAY_IDS) {
    const def = FRENCH_PUBLIC_HOLIDAY_DEFINITIONS[id];
    if (def.fixed) {
      const [month, day] = def.fixed;
      instances.push({ id, label: def.label, month, day });
      continue;
    }
    if (def.easterOffset != null) {
      const date = addDays(easter, def.easterOffset);
      instances.push({
        id,
        label: def.label,
        month: date.getMonth() + 1,
        day: date.getDate(),
      });
    }
  }

  return instances;
}

/** Numéros de jour (1–31) fériés observés pour un mois donné. */
export function getObservedHolidayDayNumbers(
  year: number,
  month: number,
  observedIds?: readonly FrenchPublicHolidayId[] | null
): Set<number> {
  const normalized = normalizeObservedHolidayIds(observedIds);
  const allowed = new Set(normalized);
  const days = new Set<number>();

  for (const instance of getHolidayInstances(year)) {
    if (instance.month === month && allowed.has(instance.id)) {
      days.add(instance.day);
    }
  }

  return days;
}

/** Ensemble des numéros de jour (1–31) fériés pour un mois donné (11 fériés légaux). */
export function getFrenchPublicHolidayDayNumbers(year: number, month: number): Set<number> {
  return getObservedHolidayDayNumbers(year, month);
}

export function isObservedFrenchPublicHoliday(
  year: number,
  month: number,
  day: number,
  observedIds?: readonly FrenchPublicHolidayId[] | null
): boolean {
  return getObservedHolidayDayNumbers(year, month, observedIds).has(day);
}

export function isFrenchPublicHoliday(year: number, month: number, day: number): boolean {
  return isObservedFrenchPublicHoliday(year, month, day);
}
