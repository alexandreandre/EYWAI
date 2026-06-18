import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { addDays, format, parseISO } from 'date-fns';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import * as calendarApi from '@/api/calendar';
import { applyHolidayHints } from '@/lib/companyCalendarHolidays';
import type { FrenchPublicHolidayId } from '@/lib/frenchPublicHolidays';
import { isForfaitJour } from '@/utils/employeeUtils';

export interface WeekPayrollDay {
  iso: string;
  planned?: PlannedEventData;
  actual?: ActualHoursData;
}

async function loadMonthCalendar(
  employeeId: string,
  year: number,
  month: number,
  forfaitJour: boolean,
  observedHolidayIds: readonly FrenchPublicHolidayId[]
): Promise<{ planned: PlannedEventData[]; actual: ActualHoursData[] }> {
  const [plannedRes, actualRes] = await Promise.all([
    calendarApi.getPlannedCalendar(employeeId, year, month),
    calendarApi.getActualHours(employeeId, year, month),
  ]);

  const plannedDataFromApi = plannedRes.data.calendrier_prevu ?? [];
  const actualDataFromApi = actualRes.data.calendrier_reel ?? [];
  const daysInMonth = new Date(year, month, 0).getDate();

  const baseCalendar: PlannedEventData[] = [];
  for (let i = 1; i <= daysInMonth; i++) {
    const date = new Date(year, month - 1, i);
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    const defaultHeuresPrevues = forfaitJour ? (isWeekend ? 0 : 1) : null;

    baseCalendar.push({
      jour: i,
      type: isWeekend ? 'weekend' : 'travail',
      heures_prevues: defaultHeuresPrevues,
    });
  }

  const planned = applyHolidayHints(
    baseCalendar,
    plannedDataFromApi,
    year,
    month,
    observedHolidayIds
  );
  const actual = planned.map((plannedDay) => {
    const apiDay = actualDataFromApi.find((a) => a.jour === plannedDay.jour);
    return {
      jour: plannedDay.jour,
      type: plannedDay.type,
      heures_faites: apiDay ? apiDay.heures_faites : null,
    };
  });

  return { planned, actual };
}

function weekDayIsos(weekStart: string): string[] {
  const monday = parseISO(weekStart.slice(0, 10));
  return Array.from({ length: 7 }, (_, i) => format(addDays(monday, i), 'yyyy-MM-dd'));
}

function uniqueMonthKeys(isoDays: string[]): string[] {
  const keys = new Set<string>();
  for (const iso of isoDays) {
    const d = parseISO(iso);
    keys.add(`${d.getFullYear()}-${d.getMonth() + 1}`);
  }
  return [...keys];
}

export function dayHasPayrollContent(
  planned: PlannedEventData | undefined,
  iso: string
): boolean {
  if (!planned) return false;
  const dow = parseISO(iso).getDay();
  if (planned.type === 'conge' || planned.type === 'ferie' || planned.type === 'arret_maladie') {
    return true;
  }
  if (dow === 0 || dow === 6) {
    return planned.type !== 'weekend' || planned.heures_prevues != null;
  }
  return planned.heures_prevues !== null && planned.heures_prevues !== undefined;
}

export function useEmployeeWeekPayrollCalendar(
  employeeId: string | undefined,
  weekStart: string,
  employeeStatut?: string,
  enabled = true,
  observedHolidayIds: readonly FrenchPublicHolidayId[] = []
) {
  const forfaitJour = isForfaitJour(employeeStatut);
  const weekDaysIso = useMemo(() => weekDayIsos(weekStart), [weekStart]);
  const holidayKey = observedHolidayIds.join(',');

  const query = useQuery({
    queryKey: ['employee-week-payroll', employeeId, weekStart, forfaitJour, holidayKey],
    queryFn: async (): Promise<WeekPayrollDay[]> => {
      if (!employeeId) return [];

      const monthCalendars = new Map<
        string,
        { planned: PlannedEventData[]; actual: ActualHoursData[] }
      >();

      await Promise.all(
        uniqueMonthKeys(weekDaysIso).map(async (key) => {
          const [yearStr, monthStr] = key.split('-');
          const year = Number(yearStr);
          const month = Number(monthStr);
          monthCalendars.set(
            key,
            await loadMonthCalendar(
              employeeId,
              year,
              month,
              forfaitJour,
              observedHolidayIds
            )
          );
        })
      );

      return weekDaysIso.map((iso) => {
        const d = parseISO(iso);
        const key = `${d.getFullYear()}-${d.getMonth() + 1}`;
        const cal = monthCalendars.get(key);
        const day = d.getDate();
        return {
          iso,
          planned: cal?.planned.find((p) => p.jour === day),
          actual: cal?.actual.find((a) => a.jour === day),
        };
      });
    },
    enabled: enabled && Boolean(employeeId),
    staleTime: 60_000,
  });

  const hasPayrollData = useMemo(
    () => (query.data ?? []).some((d) => dayHasPayrollContent(d.planned, d.iso)),
    [query.data]
  );

  return {
    weekPayrollDays: query.data ?? [],
    hasPayrollData,
    isLoading: query.isLoading,
    isError: query.isError,
    isForfaitJour: forfaitJour,
  };
}
