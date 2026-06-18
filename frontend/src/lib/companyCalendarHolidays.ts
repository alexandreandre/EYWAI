import type { PlannedEventData } from '@/api/calendar';
import {
  getObservedHolidayDayNumbers,
  type FrenchPublicHolidayId,
} from '@/lib/frenchPublicHolidays';

export function applyHolidayHints(
  baseCalendar: PlannedEventData[],
  plannedDataFromApi: PlannedEventData[],
  year: number,
  month: number,
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null
): PlannedEventData[] {
  const holidayDays = getObservedHolidayDayNumbers(year, month, observedHolidayIds);

  return baseCalendar.map((defaultDay) => {
    const apiDay = plannedDataFromApi.find((p) => p.jour === defaultDay.jour);
    let merged = apiDay ? { ...defaultDay, ...apiDay } : defaultDay;

    if (holidayDays.has(defaultDay.jour)) {
      const date = new Date(year, month - 1, defaultDay.jour);
      const isWeekend = date.getDay() === 0 || date.getDay() === 6;
      if (!isWeekend && !apiDay) {
        merged = { ...merged, type: 'ferie', heures_prevues: null };
      }
    }

    return merged;
  });
}

export function buildBasePlannedCalendarWithHolidays(
  year: number,
  month: number,
  isForfaitJourMode: boolean,
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null
): PlannedEventData[] {
  const daysInMonth = new Date(year, month, 0).getDate();
  const holidayDays = getObservedHolidayDayNumbers(year, month, observedHolidayIds);
  const base: PlannedEventData[] = [];

  for (let i = 1; i <= daysInMonth; i++) {
    const date = new Date(year, month - 1, i);
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    const defaultHeuresPrevues = isForfaitJourMode ? (isWeekend ? 0 : 1) : null;
    let type = isWeekend ? 'weekend' : 'travail';
    let heures_prevues: number | null = defaultHeuresPrevues;

    if (holidayDays.has(i) && !isWeekend) {
      type = 'ferie';
      heures_prevues = null;
    }

    base.push({ jour: i, type, heures_prevues });
  }

  return base;
}

export function shouldShowHolidayHint(
  year: number,
  month: number,
  day: number,
  plannedType: string,
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null
): boolean {
  if (plannedType !== 'ferie') {
    return false;
  }
  return getObservedHolidayDayNumbers(year, month, observedHolidayIds).has(day);
}

export function isObservedHolidayHeaderDay(
  year: number,
  month: number,
  day: number,
  observedHolidayIds?: readonly FrenchPublicHolidayId[] | null
): boolean {
  return getObservedHolidayDayNumbers(year, month, observedHolidayIds).has(day);
}
