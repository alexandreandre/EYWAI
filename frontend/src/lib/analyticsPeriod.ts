export type PeriodGranularity = "weekly" | "monthly" | "annual";

export const MONTH_NAMES_FR = [
  "Janvier",
  "Février",
  "Mars",
  "Avril",
  "Mai",
  "Juin",
  "Juillet",
  "Août",
  "Septembre",
  "Octobre",
  "Novembre",
  "Décembre",
] as const;

export type PeriodBounds = {
  start: string;
  end: string;
  label: string;
  exportKey: string;
  payrollYear: number;
  payrollMonth: number;
};

export type PeriodSelection = {
  granularity: PeriodGranularity;
  year: number;
  month: number;
  week: number;
};

function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatShortDate(d: Date): string {
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

/** Semaine ISO (année + numéro) pour une date locale. */
export function getISOWeekInfo(date: Date): { isoYear: number; week: number } {
  const d = new Date(date);
  d.setHours(12, 0, 0, 0);
  const dayNr = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - dayNr + 3);
  const isoYear = d.getFullYear();
  const jan4 = new Date(isoYear, 0, 4);
  jan4.setHours(12, 0, 0, 0);
  const jan4Day = (jan4.getDay() + 6) % 7;
  const week1Monday = new Date(jan4);
  week1Monday.setDate(jan4.getDate() - jan4Day);
  const diffDays = Math.round((d.getTime() - week1Monday.getTime()) / 86400000);
  const week = Math.floor(diffDays / 7) + 1;
  return { isoYear, week: Math.max(week, 1) };
}

export function weeksInISOYear(isoYear: number): number {
  return getISOWeekInfo(new Date(isoYear, 11, 28)).week;
}

/** Lundi–dimanche de la semaine ISO (semaine 1 = semaine contenant le 4 janvier). */
export function getISOWeekRange(
  isoYear: number,
  week: number,
): { start: Date; end: Date } {
  const jan4 = new Date(isoYear, 0, 4);
  jan4.setHours(12, 0, 0, 0);
  const day = jan4.getDay() || 7;
  const mondayWeek1 = new Date(jan4);
  mondayWeek1.setDate(jan4.getDate() - day + 1);
  const start = new Date(mondayWeek1);
  start.setDate(mondayWeek1.getDate() + (week - 1) * 7);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return { start, end };
}

export function formatMonthFr(month: number): string {
  return MONTH_NAMES_FR[month - 1] ?? String(month);
}

export function defaultPeriodSelection(now = new Date()): PeriodSelection {
  const { isoYear, week } = getISOWeekInfo(now);
  return {
    granularity: "monthly",
    year: now.getFullYear(),
    month: now.getMonth() + 1,
    week,
  };
}

export function buildPeriodBounds(selection: PeriodSelection): PeriodBounds {
  const { granularity, year, month, week } = selection;

  if (granularity === "monthly") {
    const start = new Date(year, month - 1, 1);
    const end = new Date(year, month, 0);
    const label = `${formatMonthFr(month)} ${year}`;
    const ym = `${year}-${String(month).padStart(2, "0")}`;
    return {
      start: toISODate(start),
      end: toISODate(end),
      label,
      exportKey: ym,
      payrollYear: year,
      payrollMonth: month,
    };
  }

  if (granularity === "weekly") {
    const maxWeek = weeksInISOYear(year);
    const w = Math.min(Math.max(week, 1), maxWeek);
    const { start, end } = getISOWeekRange(year, w);
    const label = `Semaine ${w} · ${formatShortDate(start)} – ${formatShortDate(end)} ${year}`;
    return {
      start: toISODate(start),
      end: toISODate(end),
      label,
      exportKey: `${year}-S${String(w).padStart(2, "0")}`,
      payrollYear: start.getFullYear(),
      payrollMonth: start.getMonth() + 1,
    };
  }

  const start = new Date(year, 0, 1);
  const end = new Date(year, 11, 31);
  const now = new Date();
  const payrollMonth =
    year === now.getFullYear() ? now.getMonth() + 1 : 12;

  return {
    start: toISODate(start),
    end: toISODate(end),
    label: `Année ${year}`,
    exportKey: String(year),
    payrollYear: year,
    payrollMonth,
  };
}

export function weekOptionsForYear(isoYear: number): Array<{
  week: number;
  label: string;
}> {
  const n = weeksInISOYear(isoYear);
  return Array.from({ length: n }, (_, i) => {
    const week = i + 1;
    const { start, end } = getISOWeekRange(isoYear, week);
    return {
      week,
      label: `S${week} · ${formatShortDate(start)} – ${formatShortDate(end)}`,
    };
  });
}

export function yearOptions(count = 6, anchor = new Date()): number[] {
  const y = anchor.getFullYear();
  return Array.from({ length: count }, (_, i) => y - i);
}

export function clampWeekForYear(isoYear: number, week: number): number {
  return Math.min(Math.max(week, 1), weeksInISOYear(isoYear));
}

/** Presets rapides alignés sur la période courante. */
export function presetThisWeek(now = new Date()): PeriodSelection {
  const { isoYear, week } = getISOWeekInfo(now);
  return { granularity: "weekly", year: isoYear, month: now.getMonth() + 1, week };
}

export function presetThisMonth(now = new Date()): PeriodSelection {
  const { week } = getISOWeekInfo(now);
  return {
    granularity: "monthly",
    year: now.getFullYear(),
    month: now.getMonth() + 1,
    week,
  };
}

export function presetThisYear(now = new Date()): PeriodSelection {
  const { week } = getISOWeekInfo(now);
  return {
    granularity: "annual",
    year: now.getFullYear(),
    month: now.getMonth() + 1,
    week,
  };
}

export function shiftPeriod(
  selection: PeriodSelection,
  delta: -1 | 1,
): PeriodSelection {
  const { granularity, year, month, week } = selection;

  if (granularity === "monthly") {
    let m = month + delta;
    let y = year;
    if (m < 1) {
      m = 12;
      y -= 1;
    } else if (m > 12) {
      m = 1;
      y += 1;
    }
    return { ...selection, year: y, month: m };
  }

  if (granularity === "weekly") {
    let w = week + delta;
    let y = year;
    const max = weeksInISOYear(y);
    if (w < 1) {
      y -= 1;
      w = weeksInISOYear(y);
    } else if (w > max) {
      y += 1;
      w = 1;
    }
    return { ...selection, year: y, week: w };
  }

  return { ...selection, year: year + delta };
}

export function isCurrentPeriodPreset(
  selection: PeriodSelection,
  now = new Date(),
): boolean {
  if (selection.granularity === "weekly") {
    const p = presetThisWeek(now);
    return p.year === selection.year && p.week === selection.week;
  }
  if (selection.granularity === "monthly") {
    const p = presetThisMonth(now);
    return p.year === selection.year && p.month === selection.month;
  }
  const p = presetThisYear(now);
  return p.year === selection.year;
}

export function currentPeriodPreset(
  granularity: PeriodGranularity,
  now = new Date(),
): PeriodSelection {
  if (granularity === "weekly") return presetThisWeek(now);
  if (granularity === "monthly") return presetThisMonth(now);
  return presetThisYear(now);
}
