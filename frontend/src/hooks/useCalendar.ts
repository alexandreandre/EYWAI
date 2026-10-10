// src/hooks/useCalendar.ts

import { log } from '@/lib/logger';
import { useState, useEffect, useCallback, useMemo, useRef, type SetStateAction } from 'react';
import { useToast } from "@/components/ui/use-toast";
import * as calendarApi from '@/api/calendar';
import { DayData } from '@/components/ScheduleModal';
import { isForfaitJour } from '@/utils/employeeUtils';
import { applyHolidayHints } from '@/lib/companyCalendarHolidays';
import {
  aDesHeuresPointees,
  computeMonthCompletionStatus,
  moisPrecedent,
} from '@/lib/calendarStats';
import { NON_COPYABLE_DAY_TYPES } from '@/lib/calendarTypes';
import {
  planningWarningsToast,
  summarizePlanningWarnings,
} from '@/lib/planningAbsenceWarnings';
import { useObservedPublicHolidays } from '@/hooks/useObservedPublicHolidays';
import { avecLeReelEnregistre, joursAuxHeuresRetirees, messageHeuresRetirees } from '@/lib/heuresRetireesAuReel';
import { accord, pluriel } from '@/lib/pluriel';
import { modeleSemaineDuSalarie } from '@/lib/modeleSemaine';

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
  options?: {
    enabled?: boolean;
    isForfaitJour?: boolean | null;
    /** Durée hebdomadaire du contrat : sert au modèle de semaine quand rien n'est prévu. */
    dureeHebdomadaire?: number | null;
  },
) {
  const fetchEnabled = options?.enabled !== false;
  const isForfaitJourMode = useMemo(
    () => isForfaitJour(employeeStatut, options?.isForfaitJour),
    [employeeStatut, options?.isForfaitJour],
  );
  const { observedHolidayIds } = useObservedPublicHolidays();

  const [weekTemplate, setWeekTemplateBrut] = useState<WeekTemplate>(() =>
    modeleSemaineDuSalarie({
      prevu: [],
      year: new Date().getFullYear(),
      month: new Date().getMonth() + 1,
      dureeHebdo: options?.dureeHebdomadaire,
      forfaitJour: isForfaitJourMode,
    })
  );
  // Tant que la gestionnaire n'a pas touché au modèle, il suit le salarié.
  const modeleModifie = useRef(false);
  const setWeekTemplate = useCallback((valeur: SetStateAction<WeekTemplate>) => {
    modeleModifie.current = true;
    setWeekTemplateBrut(valeur);
  }, []);

  const { toast } = useToast();

  const [selectedDate, setSelectedDate] = useState({
    month: new Date().getMonth() + 1,
    year: new Date().getFullYear(),
  });

  const [plannedCalendar, setPlannedCalendar] = useState<PlannedEventData[]>([]);
  const [actualHours, setActualHours] = useState<ActualHoursData[]>([]);
  // Jours du mois qui portent des heures alors que le prévu est un arrêt ou une
  // absence : dits par le backend (règle de `conflits_arret`), jamais recalculés ici.
  const [joursEnConflit, setJoursEnConflit] = useState<number[]>([]);
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
  // Heures pointées le mois précédent (que la fenêtre des variables chevauche).
  // Vrai tant qu'on ne sait pas, ou si la lecture échoue : règle stricte.
  const [pointeMoisPrecedent, setPointeMoisPrecedent] = useState(true);

  const selectedMonthKey = `${selectedDate.year}-${selectedDate.month}`;
  const isMonthDataReady =
    loadedMonthKey === selectedMonthKey && plannedCalendar.length > 0;

  // Comme le juge du serveur : un salarié qui ne pointe pas (aucune heure ni ce
  // mois ni le précédent) n'a rien « à saisir », le prévu fait foi.
  const pointe = pointeMoisPrecedent || aDesHeuresPointees(actualHours);

  const monthCompletionStatus = useMemo(() => {
    if (isLoading || !isMonthDataReady) return 'a_saisir' as const;
    return computeMonthCompletionStatus(
      plannedCalendar,
      actualHours,
      selectedDate.year,
      selectedDate.month,
      isForfaitJourMode,
      pointe
    );
  }, [
    plannedCalendar,
    actualHours,
    selectedDate.year,
    selectedDate.month,
    isLoading,
    isMonthDataReady,
    isForfaitJourMode,
    pointe,
  ]);

  /** Le réel du mois précédent a-t-il des heures ? Illisible : oui (règle stricte). */
  const lirePointeMoisPrecedent = useCallback(
    (id: string, year: number, month: number): Promise<boolean> => {
      const precedent = moisPrecedent(year, month);
      return calendarApi
        .getActualHours(id, precedent.year, precedent.month)
        .then((res) => aDesHeuresPointees(res.data.calendrier_reel ?? []))
        .catch(() => true);
    },
    []
  );

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
      setJoursEnConflit([]);
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
    setJoursEnConflit([]);
    setPointeMoisPrecedent(true);

    try {
      const [plannedRes, actualRes, pointeAvant] = await Promise.all([
        calendarApi.getPlannedCalendar(employeeId, year, month),
        calendarApi.getActualHours(employeeId, year, month),
        lirePointeMoisPrecedent(employeeId, year, month),
      ]);
      setPointeMoisPrecedent(pointeAvant);

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
      setJoursEnConflit(actualRes.data.jours_en_conflit ?? []);
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
  }, [
    employeeId,
    selectedDate.year,
    selectedDate.month,
    buildMonthCalendar,
    toast,
    fetchEnabled,
    lirePointeMoisPrecedent,
  ]);

  useEffect(() => {
    let cancelled = false;

    if (!employeeId || !fetchEnabled) {
      setIsLoading(false);
      setLoadError(false);
      setLoadedMonthKey(null);
      setPlannedCalendar([]);
      setActualHours([]);
      setJoursEnConflit([]);
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
    setJoursEnConflit([]);
    setPointeMoisPrecedent(true);

    void (async () => {
      try {
        const [plannedRes, actualRes, pointeAvant] = await Promise.all([
          calendarApi.getPlannedCalendar(employeeId, year, month),
          calendarApi.getActualHours(employeeId, year, month),
          lirePointeMoisPrecedent(employeeId, year, month),
        ]);
        if (cancelled) return;
        setPointeMoisPrecedent(pointeAvant);

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
        setJoursEnConflit(actualRes.data.jours_en_conflit ?? []);
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
  }, [
    employeeId,
    selectedDate.year,
    selectedDate.month,
    buildMonthCalendar,
    toast,
    fetchEnabled,
    lirePointeMoisPrecedent,
  ]);

  useEffect(() => {
    modeleModifie.current = false;
  }, [employeeId]);

  // Le modèle de semaine suit le prévu du salarié une fois son mois chargé.
  useEffect(() => {
    if (modeleModifie.current || loadedMonthKey === null) return;
    setWeekTemplateBrut(
      modeleSemaineDuSalarie({
        prevu: plannedCalendar,
        year: selectedDate.year,
        month: selectedDate.month,
        dureeHebdo: options?.dureeHebdomadaire,
        forfaitJour: isForfaitJourMode,
      })
    );
    // Au chargement d'un mois, pas à chaque retouche du prévu.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedMonthKey, isForfaitJourMode, options?.dureeHebdomadaire]);

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

      // Un jour issu d'une absence validée (origine "absence") est préservé,
      // comme les types ferie/conge/arret_maladie déjà exclus du modèle.
      if (
        dayOfWeek >= 1 &&
        dayOfWeek <= 5 &&
        day.origine !== 'absence' &&
        !['ferie', 'conge', 'arret_maladie'].includes(day.type)
      ) {
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
      const [plannedRes] = await Promise.all([
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

      // Le marquage et le réel affichés suivent ce qui vient d'être enregistré
      // (lecture tolérante) : le serveur remet à 0 les heures d'un jour
      // d'arrêt ou d'absence, l'écran doit le montrer et le dire.
      let heuresRetirees: number[] = [];
      try {
        const relu = await calendarApi.getActualHours(
          employeeId,
          selectedDate.year,
          selectedDate.month
        );
        setJoursEnConflit(relu.data.jours_en_conflit ?? []);
        const reelEnregistre = relu.data.calendrier_reel ?? [];
        heuresRetirees = joursAuxHeuresRetirees(actualHours, reelEnregistre);
        if (heuresRetirees.length > 0) {
          const affiche = avecLeReelEnregistre(actualHours, reelEnregistre);
          setActualHours(affiche);
          setOriginalActual(affiche);
        }
      } catch (erreur) {
        log.error(erreur);
      }
      if (heuresRetirees.length > 0) {
        toast({
          title: 'Heures non gardées sur des jours d’absence',
          description: messageHeuresRetirees(heuresRetirees),
          variant: 'destructive',
        });
      }

      // Défensif : `warnings` est absent tant que le backend ne le renvoie pas.
      // Depuis le chantier calendrier→paie il porte aussi les demandes de
      // congé créées/annulées et les écarts (solde, reprise…) : tout s'affiche.
      const warningsToast = planningWarningsToast(
        summarizePlanningWarnings(plannedRes.data?.warnings)
      );
      if (warningsToast) {
        toast(warningsToast);
      } else if (heuresRetirees.length === 0) {
        toast({
          title: 'Succès',
          description: 'Calendrier et événements de paie sauvegardés et calculés.',
        });
      }
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

      // Un jour du mois cible issu d'une absence validée n'est jamais
      // recouvert par la copie : il reste tel quel.
      const preservedCount = plannedCalendar.filter(
        (day) => day.jour <= daysInMonth && day.origine === 'absence'
      ).length;
      setPlannedCalendar((prev) =>
        prev.map((day) => {
          if (day.jour > daysInMonth) return day;
          if (day.origine === 'absence') return day;
          const fromPrev = prevData.find((p) => p.jour === day.jour);
          if (!fromPrev) return day;
          // Les CP/RTT du mois source viennent de demandes validées : les
          // recopier créerait autant de NOUVELLES demandes validées. Le jour
          // cible garde son état (généralement travail).
          if (NON_COPYABLE_DAY_TYPES.has(fromPrev.type)) return day;
          return {
            ...day,
            type: fromPrev.type,
            heures_prevues: fromPrev.heures_prevues,
          };
        })
      );

      toast({
        title: 'Mois précédent copié',
        description:
          `Planning de ${new Date(prevYear, prevMonth - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' })} appliqué au mois courant.` +
          (preservedCount > 0
            ? ` ${pluriel(preservedCount, 'jour')} d'absence validée ${accord(preservedCount, 'conservé')}.`
            : ''),
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
  }, [employeeId, selectedDate, plannedCalendar, toast]);

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
    joursEnConflit,
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
    /** Le salarié pointe sur la période : sinon, un jour sans réel n'est pas « à saisir ». */
    pointe,
    copyPreviousMonthPlanned,
    copyPlannedToActualForDay,
    copyPlannedToActualForDays,
    bulkCopyPlannedToActual,
    loadError,
    isMonthDataReady,
    refetch: fetchAllCalendarData,
  };
}
