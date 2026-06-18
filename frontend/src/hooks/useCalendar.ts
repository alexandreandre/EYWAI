// src/hooks/useCalendar.ts

import { log } from '@/lib/logger';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useToast } from "@/components/ui/use-toast";
import * as calendarApi from '@/api/calendar';
import { DayData } from '@/components/ScheduleModal';
import { isForfaitJour } from '@/utils/employeeUtils';
import { applyHolidayHints } from '@/lib/companyCalendarHolidays';
import { computeMonthCompletionStatus } from '@/lib/calendarStats';
import { useObservedPublicHolidays } from '@/hooks/useObservedPublicHolidays';

type PlannedEventData = calendarApi.PlannedEventData;
type ActualHoursData = calendarApi.ActualHoursData;

/**
 * Hook personnalisé pour gérer toute la logique du calendrier d'un employé.
 */
export type WeekTemplate = {
  [key: number]: string;
};

export function useCalendar(
  employeeId: string | undefined,
  employeeStatut?: string,
  options?: { enabled?: boolean },
) {
  const fetchEnabled = options?.enabled !== false;
  const isForfaitJourMode = useMemo(() => isForfaitJour(employeeStatut), [employeeStatut]);
  const { observedHolidayIds } = useObservedPublicHolidays();

  const getInitialWeekTemplate = (forfaitJour: boolean): WeekTemplate =>
    forfaitJour
      ? { 1: '1', 2: '1', 3: '1', 4: '1', 5: '1' }
      : { 1: '8', 2: '8', 3: '8', 4: '8', 5: '7' };

  const [weekTemplate, setWeekTemplate] = useState<WeekTemplate>(() =>
    getInitialWeekTemplate(isForfaitJourMode)
  );

  const { toast } = useToast();

  const [selectedDate, setSelectedDate] = useState({
    month: new Date().getMonth() + 1,
    year: new Date().getFullYear(),
  });

  const [plannedCalendar, setPlannedCalendar] = useState<PlannedEventData[]>([]);
  const [actualHours, setActualHours] = useState<ActualHoursData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [editingDay, setEditingDay] = useState<number | null>(null);
  const [selectedDays, setSelectedDays] = useState<number[]>([]);
  const [originalPlanned, setOriginalPlanned] = useState<PlannedEventData[]>([]);
  const [originalActual, setOriginalActual] = useState<ActualHoursData[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [isSavingAfterApply, setIsSavingAfterApply] = useState(false);
  const [isCopyingPrevMonth, setIsCopyingPrevMonth] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [loadedMonthKey, setLoadedMonthKey] = useState<string | null>(null);

  const selectedMonthKey = `${selectedDate.year}-${selectedDate.month}`;
  const isMonthDataReady =
    loadedMonthKey === selectedMonthKey && plannedCalendar.length > 0;

  const monthCompletionStatus = useMemo(() => {
    if (isLoading || !isMonthDataReady) return 'a_saisir' as const;
    return computeMonthCompletionStatus(
      plannedCalendar,
      actualHours,
      selectedDate.year,
      selectedDate.month,
      isForfaitJourMode
    );
  }, [
    plannedCalendar,
    actualHours,
    selectedDate.year,
    selectedDate.month,
    isLoading,
    isMonthDataReady,
    isForfaitJourMode,
  ]);

  const buildMonthCalendar = useCallback(
    (
      year: number,
      month: number,
      plannedDataFromApi: PlannedEventData[],
      actualDataFromApi: ActualHoursData[]
    ) => {
      const daysInMonth = new Date(year, month, 0).getDate();

      const baseCalendar: PlannedEventData[] = [];
      for (let i = 1; i <= daysInMonth; i++) {
        const date = new Date(year, month - 1, i);
        const isWeekend = date.getDay() === 0 || date.getDay() === 6;
        const defaultHeuresPrevues = isForfaitJourMode ? (isWeekend ? 0 : 1) : null;

        baseCalendar.push({
          jour: i,
          type: isWeekend ? 'weekend' : 'travail',
          heures_prevues: defaultHeuresPrevues,
        });
      }

      const finalPlannedCalendar = applyHolidayHints(
        baseCalendar,
        plannedDataFromApi,
        year,
        month,
        observedHolidayIds
      );

      const finalActualHours = finalPlannedCalendar.map((plannedDay) => {
        const apiDay = actualDataFromApi.find((a) => a.jour === plannedDay.jour);
        return {
          jour: plannedDay.jour,
          type: plannedDay.type,
          heures_faites: apiDay ? apiDay.heures_faites : null,
        };
      });

      return { finalPlannedCalendar, finalActualHours };
    },
    [isForfaitJourMode, observedHolidayIds]
  );

  const fetchAllCalendarData = useCallback(async () => {
    if (!employeeId || !fetchEnabled) {
      setIsLoading(false);
      setLoadError(false);
      setLoadedMonthKey(null);
      setPlannedCalendar([]);
      setActualHours([]);
      return;
    }

    const year = selectedDate.year;
    const month = selectedDate.month;
    const monthKey = `${year}-${month}`;

    setIsLoading(true);
    setIsDirty(false);
    setLoadError(false);
    setLoadedMonthKey(null);
    setPlannedCalendar([]);
    setActualHours([]);

    try {
      const [plannedRes, actualRes] = await Promise.all([
        calendarApi.getPlannedCalendar(employeeId, year, month),
        calendarApi.getActualHours(employeeId, year, month),
      ]);

      const plannedDataFromApi = plannedRes.data.calendrier_prevu ?? [];
      const actualDataFromApi = actualRes.data.calendrier_reel ?? [];
      const { finalPlannedCalendar, finalActualHours } = buildMonthCalendar(
        year,
        month,
        plannedDataFromApi,
        actualDataFromApi
      );

      setPlannedCalendar(finalPlannedCalendar);
      setActualHours(finalActualHours);
      setOriginalPlanned(finalPlannedCalendar);
      setOriginalActual(finalActualHours);
      setLoadedMonthKey(monthKey);
      setLoadError(false);
    } catch (error) {
      log.error(error);
      setLoadError(true);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger les données du calendrier.',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [employeeId, selectedDate.year, selectedDate.month, buildMonthCalendar, toast, fetchEnabled]);

  useEffect(() => {
    let cancelled = false;

    if (!employeeId || !fetchEnabled) {
      setIsLoading(false);
      setLoadError(false);
      setLoadedMonthKey(null);
      setPlannedCalendar([]);
      setActualHours([]);
      return;
    }

    const year = selectedDate.year;
    const month = selectedDate.month;
    const monthKey = `${year}-${month}`;

    setIsLoading(true);
    setIsDirty(false);
    setLoadError(false);
    setLoadedMonthKey(null);
    setPlannedCalendar([]);
    setActualHours([]);

    void (async () => {
      try {
        const [plannedRes, actualRes] = await Promise.all([
          calendarApi.getPlannedCalendar(employeeId, year, month),
          calendarApi.getActualHours(employeeId, year, month),
        ]);
        if (cancelled) return;

        const plannedDataFromApi = plannedRes.data.calendrier_prevu ?? [];
        const actualDataFromApi = actualRes.data.calendrier_reel ?? [];
        const { finalPlannedCalendar, finalActualHours } = buildMonthCalendar(
          year,
          month,
          plannedDataFromApi,
          actualDataFromApi
        );

        setPlannedCalendar(finalPlannedCalendar);
        setActualHours(finalActualHours);
        setOriginalPlanned(finalPlannedCalendar);
        setOriginalActual(finalActualHours);
        setLoadedMonthKey(monthKey);
        setLoadError(false);
      } catch (error) {
        if (cancelled) return;
        log.error(error);
        setLoadError(true);
        toast({
          title: 'Erreur',
          description: 'Impossible de charger les données du calendrier.',
          variant: 'destructive',
        });
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [employeeId, selectedDate.year, selectedDate.month, buildMonthCalendar, toast, fetchEnabled]);

  useEffect(() => {
    setWeekTemplate(getInitialWeekTemplate(isForfaitJourMode));
  }, [isForfaitJourMode]);

  useEffect(() => {
    if (!isLoading) {
      const plannedChanged =
        JSON.stringify(plannedCalendar) !== JSON.stringify(originalPlanned);
      const actualChanged =
        JSON.stringify(actualHours) !== JSON.stringify(originalActual);
      setIsDirty(plannedChanged || actualChanged);
    }
  }, [plannedCalendar, actualHours, originalPlanned, originalActual, isLoading]);

  const applyWeekTemplate = useCallback(() => {
    const newPlannedCalendar = plannedCalendar.map((day) => {
      const date = new Date(selectedDate.year, selectedDate.month - 1, day.jour);
      const dayOfWeek = date.getDay();

      if (dayOfWeek >= 1 && dayOfWeek <= 5 && !['ferie', 'conge', 'arret_maladie'].includes(day.type)) {
        const templateValue = weekTemplate[dayOfWeek];

        if (isForfaitJourMode) {
          const isWorkDay =
            templateValue && templateValue.trim() !== '' && parseFloat(templateValue) > 0;
          return {
            ...day,
            type: isWorkDay ? 'travail' : 'weekend',
            heures_prevues: isWorkDay ? 1 : 0,
          };
        }

        const hours =
          templateValue && templateValue.trim() !== '' ? parseFloat(templateValue) : null;
        return {
          ...day,
          type: hours !== null && hours > 0 ? 'travail' : 'weekend',
          heures_prevues: hours,
        };
      }

      return day;
    });

    setPlannedCalendar(newPlannedCalendar);
    toast({
      title: 'Modèle appliqué',
      description: isForfaitJourMode
        ? 'Le calendrier prévisionnel a été mis à jour (mode forfait jour).'
        : 'Le calendrier prévisionnel a été mis à jour.',
    });
  }, [plannedCalendar, selectedDate, weekTemplate, isForfaitJourMode, toast]);

  const saveAllCalendarData = useCallback(async () => {
    if (!employeeId) return;

    setIsSaving(true);
    try {
      await Promise.all([
        calendarApi.updatePlannedCalendar(
          employeeId,
          selectedDate.year,
          selectedDate.month,
          plannedCalendar
        ),
        calendarApi.updateActualHours(
          employeeId,
          selectedDate.year,
          selectedDate.month,
          actualHours
        ),
      ]);

      await calendarApi.calculatePayrollEvents(
        employeeId,
        selectedDate.year,
        selectedDate.month
      );

      setOriginalPlanned(plannedCalendar);
      setOriginalActual(actualHours);

      toast({
        title: 'Succès',
        description: 'Calendrier et événements de paie sauvegardés et calculés.',
      });
    } catch (error) {
      log.error(error);
      toast({
        title: 'Erreur',
        description: 'La sauvegarde ou le calcul a échoué.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  }, [employeeId, selectedDate, plannedCalendar, actualHours, toast]);

  useEffect(() => {
    if (isSavingAfterApply && !isSaving) {
      saveAllCalendarData();
      setIsSavingAfterApply(false);
    }
  }, [isSavingAfterApply, isSaving, saveAllCalendarData]);

  const updateDayData = (updatedDay: Partial<DayData>) => {
    if (updatedDay.jour === undefined) return;

    setPlannedCalendar((prev) =>
      prev.map((p) => {
        if (p.jour !== updatedDay.jour) return p;
        const newPlannedData: Partial<PlannedEventData> = {};
        if (updatedDay.type !== undefined) newPlannedData.type = updatedDay.type;
        if (updatedDay.heures_prevues !== undefined)
          newPlannedData.heures_prevues = updatedDay.heures_prevues;
        return { ...p, ...newPlannedData };
      })
    );

    setActualHours((prev) =>
      prev.map((a) => {
        if (a.jour !== updatedDay.jour) return a;
        const newActualData: Partial<ActualHoursData> = {};
        if (updatedDay.type !== undefined) newActualData.type = updatedDay.type;
        if (updatedDay.heures_faites !== undefined)
          newActualData.heures_faites = updatedDay.heures_faites;
        return { ...a, ...newActualData };
      })
    );
  };

  const copyPlannedToActualForDays = useCallback(
    (dayNumbers: number[]) => {
      if (dayNumbers.length === 0) return;

      setActualHours((prev) =>
        prev.map((a) => {
          if (!dayNumbers.includes(a.jour)) return a;
          const planned = plannedCalendar.find((p) => p.jour === a.jour);
          if (!planned) return a;
          return {
            ...a,
            type: planned.type,
            heures_faites: planned.heures_prevues,
          };
        })
      );

      toast({
        title: 'Prévu copié en réel',
        description: `${dayNumbers.length} jour${dayNumbers.length > 1 ? 's' : ''} mis à jour.`,
      });
    },
    [plannedCalendar, toast]
  );

  const copyPlannedToActualForDay = useCallback(
    (dayNumber: number) => copyPlannedToActualForDays([dayNumber]),
    [copyPlannedToActualForDays]
  );

  const copyPreviousMonthPlanned = useCallback(async () => {
    if (!employeeId) return;

    let prevMonth = selectedDate.month - 1;
    let prevYear = selectedDate.year;
    if (prevMonth < 1) {
      prevMonth = 12;
      prevYear -= 1;
    }

    setIsCopyingPrevMonth(true);
    try {
      const res = await calendarApi.getPlannedCalendar(employeeId, prevYear, prevMonth);
      const prevData: PlannedEventData[] = res.data.calendrier_prevu ?? [];
      const daysInMonth = new Date(selectedDate.year, selectedDate.month, 0).getDate();

      setPlannedCalendar((prev) =>
        prev.map((day) => {
          if (day.jour > daysInMonth) return day;
          const fromPrev = prevData.find((p) => p.jour === day.jour);
          if (!fromPrev) return day;
          return {
            ...day,
            type: fromPrev.type,
            heures_prevues: fromPrev.heures_prevues,
          };
        })
      );

      toast({
        title: 'Mois précédent copié',
        description: `Planning de ${new Date(prevYear, prevMonth - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' })} appliqué au mois courant.`,
      });
    } catch (error) {
      log.error(error);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger le mois précédent.',
        variant: 'destructive',
      });
    } finally {
      setIsCopyingPrevMonth(false);
    }
  }, [employeeId, selectedDate, toast]);

  const handleDaySelection = (dayNumber: number) => {
    setSelectedDays((prev) =>
      prev.includes(dayNumber) ? prev.filter((d) => d !== dayNumber) : [...prev, dayNumber]
    );
  };

  const updateSelection = (mode: 'all' | 'weekdays' | 'none') => {
    if (mode === 'none') {
      setSelectedDays([]);
      return;
    }

    const year = selectedDate.year;
    const month = selectedDate.month - 1;
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const allDaysInMonth: number[] = [];
    for (let day = 1; day <= daysInMonth; day++) allDaysInMonth.push(day);

    if (mode === 'all') {
      setSelectedDays(allDaysInMonth);
    } else if (mode === 'weekdays') {
      const weekdays = allDaysInMonth.filter((day) => {
        const date = new Date(year, month, day);
        return date.getDay() !== 0 && date.getDay() !== 6;
      });
      setSelectedDays(weekdays);
    }
  };

  const bulkUpdateDays = (updateData: Partial<Omit<DayData, 'jour'>>) => {
    if (selectedDays.length === 0) return;

    selectedDays.forEach((dayNumber) => {
      updateDayData({ jour: dayNumber, ...updateData });
    });

    toast({
      title: 'Mise à jour groupée',
      description: `${selectedDays.length} jours ont été modifiés.`,
    });
    setSelectedDays([]);
  };

  const applyWeekTemplateAndSave = () => {
    applyWeekTemplate();
    setIsSavingAfterApply(true);
  };

  const bulkUpdateDaysAndSave = (updateData: Partial<Omit<DayData, 'jour'>>) => {
    bulkUpdateDays(updateData);
    setIsSavingAfterApply(true);
  };

  const bulkCopyPlannedToActual = () => {
    if (selectedDays.length === 0) return;
    copyPlannedToActualForDays([...selectedDays]);
    setSelectedDays([]);
  };

  return {
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    setPlannedCalendar,
    actualHours,
    setActualHours,
    isLoading,
    isSaving,
    isCopyingPrevMonth,
    saveAllCalendarData,
    updateDayData,
    weekTemplate,
    setWeekTemplate,
    applyWeekTemplate,
    editingDay,
    setEditingDay,
    selectedDays,
    setSelectedDays,
    handleDaySelection,
    bulkUpdateDays,
    isDirty,
    applyWeekTemplateAndSave,
    bulkUpdateDaysAndSave,
    updateSelection,
    isForfaitJour: isForfaitJourMode,
    monthCompletionStatus,
    copyPreviousMonthPlanned,
    copyPlannedToActualForDay,
    copyPlannedToActualForDays,
    bulkCopyPlannedToActual,
    loadError,
    isMonthDataReady,
    refetch: fetchAllCalendarData,
  };
}
