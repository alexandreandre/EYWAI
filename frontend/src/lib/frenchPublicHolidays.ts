/** Jours fériés France métropolitaine (fixes + Pâques, Ascension, Pentecôte). */

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

/** Ensemble des numéros de jour (1–31) fériés pour un mois donné. */
export function getFrenchPublicHolidayDayNumbers(year: number, month: number): Set<number> {
  const days = new Set<number>();

  const fixed: Array<[number, number]> = [
    [1, 1],
    [5, 1],
    [5, 8],
    [7, 14],
    [8, 15],
    [11, 1],
    [11, 11],
    [12, 25],
  ];

  for (const [m, d] of fixed) {
    if (m === month) days.add(d);
  }

  const easter = easterSunday(year);
  const mobile = [
    addDays(easter, 1),
    addDays(easter, 39),
    addDays(easter, 50),
  ];

  for (const d of mobile) {
    if (d.getMonth() + 1 === month) days.add(d.getDate());
  }

  return days;
}

export function isFrenchPublicHoliday(year: number, month: number, day: number): boolean {
  return getFrenchPublicHolidayDayNumbers(year, month).has(day);
}
