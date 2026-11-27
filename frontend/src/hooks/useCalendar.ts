// src/hooks/useCalendar.ts

import { log } from '@/lib/logger';
import { useState, useEffect, useLayoutEffect, useCallback, useMemo, useRef, type SetStateAction } from 'react';
import { useToast } from "@/components/ui/use-toast";
import { useQueryClient } from '@tanstack/react-query';
import { invaliderApresBulletin } from '@/features/payroll/utils/invalidationsBulletin';
import * as calendarApi from '@/api/calendar';
import { DayData, type SaisieGroupee } from '@/components/ScheduleModal';
import { isForfaitJour } from '@/utils/employeeUtils';
import { applyHolidayHints } from '@/lib/companyCalendarHolidays';
import { saisieGroupeeDuJour, saisieGroupeeLaisseLeJour } from '@/lib/calendarTypes';
import {
  aDesHeuresPointees,
  computeMonthCompletionStatus,
  moisPrecedent,
} from '@/lib/calendarStats';
import {
  planningWarningsToast,
  summarizePlanningWarnings,
} from '@/lib/planningAbsenceWarnings';
import { useObservedPublicHolidays } from '@/hooks/useObservedPublicHolidays';
import { joursAuxHeuresRetirees, messageHeuresRetirees } from '@/lib/heuresRetireesAuReel';
import { copierMoisPrecedent, noteJoursGardes } from '@/lib/copieMoisPrecedent';
import { modeleSemaineDuSalarie } from '@/lib/modeleSemaine';
import {
  jourPrevuDuModele,
  prevuDuModeleEnRepassantEnTravail,
  valeurModelePourLeJour,
} from '@/lib/weekTemplateDays';
import { calendarSaveFailureMessage } from '@/lib/calendarSaveFeedback';
import { horairesAEnvoyer } from '@/lib/horairesDuJour';
import { dernierJourDuContratDansLeMois } from '@/lib/employmentStatus';
import { estAvantLEntree, premierJourDuContratDansLeMois } from '@/lib/joursHorsContrat';

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
    /** Sortie du salarié : le modèle et la copie du prévu ne posent rien après. */
    sortie?: { exit_last_working_day?: string | null; hire_date?: string | null } | null;
  },
) {
  const fetchEnabled = options?.enabled !== false;
  const isForfaitJourMode = useMemo(
    () => isForfaitJour(employeeStatut, options?.isForfaitJour),
    [employeeStatut, options?.isForfaitJour],
  );
  const { activeCompanyId, observedHolidayIds } = useObservedPublicHolidays();

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
  const [saveError, setSaveError] = useState<string | null>(null);
  const [revision, setRevision] = useState<string | null | undefined>(undefined);
  const [loadedCalendarKey, setLoadedCalendarKey] = useState<string | null>(null);
  const loadSequence = useRef(0);
  const copySequence = useRef(0);
  const editRevision = useRef(0);
  const saveInFlight = useRef(false);

  const applySavePending = useRef(false);
  const mounted = useRef(false);
  // Heures pointées le mois précédent (que la fenêtre des variables chevauche).
  // Vrai tant qu'on ne sait pas, ou si la lecture échoue : règle stricte.
  const [pointeMoisPrecedent, setPointeMoisPrecedent] = useState(true);

  const calendarKey = JSON.stringify([activeCompanyId, employeeId, selectedDate.year, selectedDate.month]);
  // Une nouvelle visite du même mois reste un nouveau contexte (A → B → A).
  const context = useMemo(() => ({ active: false, key: calendarKey, enabled: fetchEnabled }), [calendarKey, fetchEnabled]);
  useLayoutEffect(() => {
    context.active = true;
    return () => { context.active = false; };
  }, [context]);
  useLayoutEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const isMonthDataReady =
    fetchEnabled && !isLoading && !loadError && revision !== undefined && loadedCalendarKey === calendarKey && plannedCalendar.length > 0;

  // Des changements non enregistrés : le navigateur demande avant de quitter
  // ou de recharger la page (Lyon, 17/11 : un calendrier laissé sans
  // « Enregistrer » n'arrivait pas au bulletin).
  const nonEnregistre = isMonthDataReady && isDirty;
  useEffect(() => {
    if (!nonEnregistre) return;
    const avantDeQuitter = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', avantDeQuitter);
    return () => window.removeEventListener('beforeunload', avantDeQuitter);
  }, [nonEnregistre]);

  // Comme le juge du serveur : un salarié qui ne pointe pas (aucune heure ni ce
  // mois ni le précédent) n'a rien « à saisir », le prévu fait foi.
  const pointe = pointeMoisPrecedent || aDesHeuresPointees(actualHours);

  // Contrat : rien n'est attendu avant l'entrée ni après la sortie.
  const dernierJourContrat = options?.sortie
    ? dernierJourDuContratDansLeMois(options.sortie, selectedDate.year, selectedDate.month)
    : null;
  const premierJourContrat = options?.sortie
    ? premierJourDuContratDansLeMois(options.sortie, selectedDate.year, selectedDate.month)
    : null;

  const monthCompletionStatus = useMemo(() => {
    if (isLoading || !isMonthDataReady) return 'a_saisir' as const;
    return computeMonthCompletionStatus(
      plannedCalendar,
      actualHours,
      selectedDate.year,
      selectedDate.month,
      isForfaitJourMode,
      pointe,
      { premierJour: premierJourContrat, dernierJour: dernierJourContrat }
    );
  }, [
    premierJourContrat,
    dernierJourContrat,
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
    (id: string, year: number, month: number, requestContext: calendarApi.CalendarRequestContext): Promise<boolean> => {
      const precedent = moisPrecedent(year, month);
      return calendarApi
        .getActualHours(id, precedent.year, precedent.month, requestContext)
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
          // Arrivée et départ : affichés dans la case ; l'arrivée est renvoyée
          // telle quelle (cf. `horairesAEnvoyer`).
          ...(apiDay?.debut ? { debut: apiDay.debut } : {}),
          ...(apiDay?.fin ? { fin: apiDay.fin } : {}),
        };
      });

      return { finalPlannedCalendar, finalActualHours };
    },
    [isForfaitJourMode, observedHolidayIds]
  );

  const fetchAllCalendarData = useCallback(async () => {
    if (!context.active) return;
    const request = ++loadSequence.current;
    const isCurrent = () => context.active && request === loadSequence.current;
    ++editRevision.current;
    setRevision(undefined);
    setSaveError(null);
    setSelectedDays([]);
    setEditingDay(null);
    setIsSavingAfterApply(false);
    applySavePending.current = false;
    setIsCopyingPrevMonth(false);
    if (!employeeId || !fetchEnabled) {
      setIsLoading(false);
      setLoadError(false);
      setLoadedCalendarKey(null);
      setPlannedCalendar([]);
      setActualHours([]);
      setOriginalPlanned([]);
      setOriginalActual([]);
      setIsDirty(false);
      setJoursEnConflit([]);
      return;
    }

    const year = selectedDate.year;
    const month = selectedDate.month;
    const requestContext = { companyId: activeCompanyId };

    setIsLoading(true);
    setIsDirty(false);
    setLoadError(false);
    setLoadedCalendarKey(null);
    setPlannedCalendar([]);
    setActualHours([]);
    setJoursEnConflit([]);
    setPointeMoisPrecedent(true);

    try {
      const [snapshot, pointeAvant] = await Promise.all([
        calendarApi.getCalendarSnapshot(employeeId, year, month, requestContext),
        lirePointeMoisPrecedent(employeeId, year, month, requestContext),
      ]);
      if (!isCurrent()) return;
      if (snapshot.data.revision === undefined || snapshot.data.busy) throw new Error('Calendrier en cours d’enregistrement ou révision indisponible.');
      setRevision(snapshot.data.revision);
      setPointeMoisPrecedent(pointeAvant);

      const plannedDataFromApi = snapshot.data.calendrier_prevu ?? [];
      const actualDataFromApi = snapshot.data.calendrier_reel ?? [];
      const { finalPlannedCalendar, finalActualHours } = buildMonthCalendar(
        year,
        month,
        plannedDataFromApi,
        actualDataFromApi
      );

      setPlannedCalendar(finalPlannedCalendar);
      setActualHours(finalActualHours);
      setJoursEnConflit(snapshot.data.jours_en_conflit ?? []);
      setOriginalPlanned(finalPlannedCalendar);
      setOriginalActual(finalActualHours);
      setLoadedCalendarKey(calendarKey);
      setLoadError(false);
    } catch (error) {
      if (!isCurrent()) return;
      log.error(error);
      setLoadError(true);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger les données du calendrier.',
        variant: 'destructive',
      });
    } finally {
      if (isCurrent()) setIsLoading(false);
    }
  }, [
    employeeId,
    selectedDate.year,
    selectedDate.month,
    buildMonthCalendar,
    toast,
    fetchEnabled,
    lirePointeMoisPrecedent,
    context,
    calendarKey,
    activeCompanyId,
  ]);

  useEffect(() => {
    void fetchAllCalendarData();
  }, [fetchAllCalendarData]);

  useEffect(() => {
    modeleModifie.current = false;
  }, [employeeId, activeCompanyId]);

  // Le modèle de semaine suit le prévu du salarié une fois son mois chargé.
  useEffect(() => {
    if (modeleModifie.current || loadedCalendarKey !== calendarKey) return;
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
  }, [loadedCalendarKey, calendarKey, isForfaitJourMode, options?.dureeHebdomadaire]);

  useEffect(() => {
    if (isMonthDataReady) {
      const plannedChanged =
        JSON.stringify(plannedCalendar) !== JSON.stringify(originalPlanned);
      const actualChanged =
        JSON.stringify(actualHours) !== JSON.stringify(originalActual);
      setIsDirty(plannedChanged || actualChanged);
    }
  }, [plannedCalendar, actualHours, originalPlanned, originalActual, isMonthDataReady]);

  const applyWeekTemplate = useCallback(() => {
    if (!context.active || !isMonthDataReady) return;
    ++editRevision.current;
    const newPlannedCalendar = plannedCalendar.map((day) => {
      // Après la sortie : jour à 0 h, rien du modèle (retour du 10/11).
      if (dernierJourContrat != null && day.jour > dernierJourContrat && day.origine !== 'absence') {
        return { ...day, type: 'repos', heures_prevues: 0 };
      }
      // Avant l'entrée : hors contrat, le modèle ne pose rien.
      if (estAvantLEntree(day.jour, premierJourContrat)) return day;
      const date = new Date(selectedDate.year, selectedDate.month - 1, day.jour);
      const dayOfWeek = date.getDay();

      // Un jour issu d'une absence validée (origine "absence") est préservé,
      // comme les types ferie/conge/arret_maladie déjà exclus du modèle.
      // Le week-end n'est touché que si le modèle y dit quelque chose.
      const templateValue = valeurModelePourLeJour(weekTemplate, dayOfWeek);
      if (
        templateValue !== undefined &&
        day.origine !== 'absence' &&
        !['ferie', 'conge', 'arret_maladie'].includes(day.type)
      ) {

        // Case vide = 0 h, jour non travaillé (retour du 10/11) : jamais un
        // jour laissé « à saisir » ni une valeur par défaut.
        return { ...day, ...jourPrevuDuModele(templateValue, isForfaitJourMode) };
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
  }, [plannedCalendar, selectedDate, weekTemplate, isForfaitJourMode, toast, dernierJourContrat, premierJourContrat, context, isMonthDataReady]);

  const queryClient = useQueryClient();
  const saveAllCalendarData = useCallback(async () => {
    if (!employeeId || !context.active || !isMonthDataReady || revision === undefined || saveInFlight.current) return false;

    saveInFlight.current = true;
    setIsSaving(true);
    const loadAtStart = loadSequence.current;
    const revisionAtStart = editRevision.current;
    const isCurrent = () => context.active && loadAtStart === loadSequence.current;
    const requestContext = { companyId: activeCompanyId };
    setSaveError(null);
    try {
      const saved = await calendarApi.saveCalendar(employeeId, selectedDate.year, selectedDate.month, {
        expected_revision: revision, calendrier_prevu: plannedCalendar,
        calendrier_reel: horairesAEnvoyer(actualHours), recalculate_payroll: true,
      }, requestContext);
      if (!isCurrent()) return false;
      const snapshot = saved.data;
      const { finalPlannedCalendar, finalActualHours } = buildMonthCalendar(
        selectedDate.year, selectedDate.month, snapshot.calendrier_prevu, snapshot.calendrier_reel,
      );
      const heuresRetirees = joursAuxHeuresRetirees(actualHours, snapshot.calendrier_reel);
      // Le serveur a marqué les bulletins touchés « à recalculer » : les écrans
      // de paie le montrent tout de suite, pas après 5 minutes de cache.
      void invaliderApresBulletin(queryClient, activeCompanyId, employeeId);
      setRevision(snapshot.revision);
      setJoursEnConflit(snapshot.jours_en_conflit ?? []);
      setOriginalPlanned(finalPlannedCalendar);
      setOriginalActual(finalActualHours);
      if (revisionAtStart === editRevision.current) {
        setPlannedCalendar(finalPlannedCalendar);
        setActualHours(finalActualHours);
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
        summarizePlanningWarnings(saved.data.warnings)
      );
      if (warningsToast) {
        toast(warningsToast);
      } else if (heuresRetirees.length === 0) {
        toast({
          title: 'Succès',
          description: 'Calendrier et événements de paie sauvegardés et calculés.',
        });
      }
      return true;
    } catch (error) {
      log.error(error);
      if (isCurrent()) {
        const message = calendarSaveFailureMessage(error);
        setSaveError(message);
        toast({ title: 'Enregistrement incomplet', description: message, variant: 'destructive' });
      }
      return false;
    } finally {
      saveInFlight.current = false;
      if (mounted.current) setIsSaving(false);
    }
  }, [employeeId, selectedDate, plannedCalendar, actualHours, toast, context, isMonthDataReady, activeCompanyId, revision, buildMonthCalendar, queryClient]);

  useEffect(() => {
    if (isSavingAfterApply && !isSaving && applySavePending.current) {
      // Consommer avant tout effet de sauvegarde : une réponse immédiate ou
      // une notification synchrone peut déclencher un rendu supplémentaire.
      applySavePending.current = false;
      setIsSavingAfterApply(false);
      void saveAllCalendarData();
    }
  }, [isSavingAfterApply, isSaving, saveAllCalendarData]);

  const updateDayData = (
    updatedDay: Partial<DayData> & {
      demi_journee?: 'matin' | 'apres_midi' | null;
      /** « Vider ce jour » : le jour reste vide, sans les heures du modèle. */
      vider?: boolean;
    }
  ) => {
    if (!context.active || !isMonthDataReady || updatedDay.jour === undefined) return;
    ++editRevision.current;

    setPlannedCalendar((prev) =>
      prev.map((p) => {
        if (p.jour !== updatedDay.jour) return p;
        const newPlannedData: Partial<PlannedEventData> = {};
        if (updatedDay.type !== undefined) newPlannedData.type = updatedDay.type;
        // Demi-journée d'un CP/RTT posé ici : part avec la demande créée.
        if (updatedDay.demi_journee !== undefined)
          newPlannedData.demi_journee = updatedDay.demi_journee;
        if ((updatedDay.type ?? p.type) === 'repos') newPlannedData.heures_prevues = 0;
        else if (updatedDay.heures_prevues !== undefined)
          newPlannedData.heures_prevues = updatedDay.heures_prevues;
        // Un congé (0 h prévue) repassé en « Travail » reprend les heures du
        // modèle de semaine, jour isolé ou saisie groupée (A6, 18/11).
        const prevu = newPlannedData.heures_prevues !== undefined ? newPlannedData.heures_prevues : p.heures_prevues;
        const apresLaSortie = dernierJourContrat != null && p.jour > dernierJourContrat;
        const repasseEnTravail = p.type !== 'travail' || p.heures_prevues == null;
        if (updatedDay.type === 'travail' && !updatedDay.vider && repasseEnTravail && !apresLaSortie && !(Number(prevu) > 0)) {
          const duModele = prevuDuModeleEnRepassantEnTravail(
            weekTemplate,
            new Date(selectedDate.year, selectedDate.month - 1, p.jour),
            isForfaitJourMode,
          );
          if (duModele !== undefined) newPlannedData.heures_prevues = duModele;
        }
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
        // Vidé : arrivée et départ partent vides, le serveur les efface.
        if (updatedDay.vider) return { ...a, ...newActualData, debut: null, fin: null };
        return { ...a, ...newActualData };
      })
    );
  };

  const copyPlannedToActualForDays = useCallback(
    (dayNumbers: number[]) => {
      if (!context.active || !isMonthDataReady || dayNumbers.length === 0) return;
      ++editRevision.current;

      setActualHours((prev) =>
        prev.map((a) => {
          if (!dayNumbers.includes(a.jour)) return a;
          if (dernierJourContrat != null && a.jour > dernierJourContrat) return a;
          const planned = plannedCalendar.find((p) => p.jour === a.jour);
          if (!planned) return a;
          // Un jour d'activité partielle reste chômé : recopier ses heures
          // prévues en réel en ferait un jour travaillé (Lyon, 17/11).
          if (planned.type === 'activite_partielle') return a;
          // Au forfait jours, le réel se pose en jours, même si le prévu est
          // en heures (retour du 10/11).
          const heures =
            isForfaitJourMode && typeof planned.heures_prevues === 'number'
              ? planned.heures_prevues > 0
                ? 1
                : 0
              : planned.heures_prevues;
          return {
            ...a,
            type: planned.type,
            heures_faites: heures,
          };
        })
      );

      toast({
        title: 'Prévu copié en réel',
        description: `${dayNumbers.length} jour${dayNumbers.length > 1 ? 's' : ''} mis à jour.`,
      });
    },
    [plannedCalendar, toast, isForfaitJourMode, dernierJourContrat, context, isMonthDataReady]
  );

  const copyPlannedToActualForDay = useCallback(
    (dayNumber: number) => copyPlannedToActualForDays([dayNumber]),
    [copyPlannedToActualForDays]
  );

  const copyPreviousMonthPlanned = useCallback(async () => {
    if (!employeeId || !context.active || !isMonthDataReady) return;
    const request = ++copySequence.current;
    const loadAtStart = loadSequence.current;
    const revisionAtStart = editRevision.current;
    const isCurrent = () => context.active && request === copySequence.current && loadAtStart === loadSequence.current;

    let prevMonth = selectedDate.month - 1;
    let prevYear = selectedDate.year;
    if (prevMonth < 1) {
      prevMonth = 12;
      prevYear -= 1;
    }

    setIsCopyingPrevMonth(true);
    try {
      const res = await calendarApi.getPlannedCalendar(employeeId, prevYear, prevMonth, { companyId: activeCompanyId });
      if (!isCurrent()) return;
      if (revisionAtStart !== editRevision.current) {
        toast({ title: 'Copie non appliquée', description: 'Le calendrier a été modifié pendant le chargement. Relancez la copie si nécessaire.' });
        return;
      }
      ++editRevision.current;
      const prevData: PlannedEventData[] = res.data.calendrier_prevu ?? [];
      const daysInMonth = new Date(selectedDate.year, selectedDate.month, 0).getDate();

      // Chaque jour reçoit le jour type du même jour de la semaine au mois
      // précédent ; les fériés et les absences du mois affiché restent tels
      // quels (les CP/RTT du mois source ne sont jamais recopiés : ce seraient
      // de NOUVELLES demandes validées).
      const copie = copierMoisPrecedent({
        source: prevData,
        anneeSource: prevYear,
        moisSource: prevMonth,
        cible: plannedCalendar,
        annee: selectedDate.year,
        mois: selectedDate.month,
      });
      setPlannedCalendar((prev) =>
        prev.map((day) => {
          if (day.jour > daysInMonth) return day;
          const copieDuJour = copie.jours.find((j) => j.jour === day.jour);
          if (!copieDuJour || copieDuJour === day) return day;
          return {
            ...day,
            type: copieDuJour.type,
            heures_prevues: copieDuJour.heures_prevues,
          };
        })
      );

      toast({
        title: 'Mois précédent copié',
        description:
          `Chaque jour reprend le même jour de la semaine de ${new Date(prevYear, prevMonth - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' })}.` +
          noteJoursGardes(copie.feriesGardes, copie.absencesGardees),
      });
    } catch (error) {
      if (!isCurrent()) return;
      log.error(error);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger le mois précédent.',
        variant: 'destructive',
      });
    } finally {
      if (isCurrent()) setIsCopyingPrevMonth(false);
    }
  }, [employeeId, selectedDate, plannedCalendar, toast, context, isMonthDataReady, activeCompanyId]);

  const handleDaySelection = (dayNumber: number) => {
    if (!context.active || !isMonthDataReady) return;
    setSelectedDays((prev) =>
      prev.includes(dayNumber) ? prev.filter((d) => d !== dayNumber) : [...prev, dayNumber]
    );
  };

  const updateSelection = (mode: 'all' | 'weekdays' | 'none') => {
    if (!context.active || !isMonthDataReady) return;
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

  const bulkUpdateDays = (updateData: SaisieGroupee) => {
    if (!context.active || !isMonthDataReady || selectedDays.length === 0) return;

    let laisses = 0;
    selectedDays.forEach((dayNumber) => {
      const ancienType = plannedCalendar.find((p) => p.jour === dayNumber)?.type;
      if (saisieGroupeeLaisseLeJour(updateData, ancienType)) {
        laisses += 1;
        return;
      }
      updateDayData({ jour: dayNumber, ...saisieGroupeeDuJour(updateData, ancienType) });
    });

    const modifies = selectedDays.length - laisses;
    toast({
      title: 'Mise à jour groupée',
      description:
        `${modifies} ${modifies > 1 ? 'jours modifiés' : 'jour modifié'}.` +
        (laisses > 0
          ? ` ${laisses} ${laisses > 1 ? 'jours gardent leur' : 'jour garde son'} type (congé, férié, école…) : ` +
            'saisissez-y les heures jour par jour.'
          : ''),
    });
    setSelectedDays([]);
  };

  const applyWeekTemplateAndSave = () => {
    if (!context.active || !isMonthDataReady || saveInFlight.current) return;
    applyWeekTemplate();
    applySavePending.current = true;
    setIsSavingAfterApply(true);
  };

  const bulkUpdateDaysAndSave = (updateData: SaisieGroupee) => {
    if (!context.active || !isMonthDataReady || saveInFlight.current || selectedDays.length === 0) return;
    bulkUpdateDays(updateData);
    applySavePending.current = true;
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
    plannedCalendar: isMonthDataReady ? plannedCalendar : [],
    setPlannedCalendar,
    actualHours: isMonthDataReady ? actualHours : [],
    setActualHours,
    joursEnConflit: isMonthDataReady ? joursEnConflit : [],
    isLoading: fetchEnabled && Boolean(employeeId) && (isLoading || (loadedCalendarKey !== calendarKey && !loadError)),
    isSaving,
    isCopyingPrevMonth,
    saveAllCalendarData,
    updateDayData,
    weekTemplate,
    setWeekTemplate,
    applyWeekTemplate,
    editingDay,
    setEditingDay,
    selectedDays: isMonthDataReady ? selectedDays : [],
    setSelectedDays,
    handleDaySelection,
    bulkUpdateDays,
    isDirty: isMonthDataReady && isDirty,
    applyWeekTemplateAndSave,
    bulkUpdateDaysAndSave,
    updateSelection,
    isForfaitJour: isForfaitJourMode,
    monthCompletionStatus,
    /** Le salarié pointe sur la période : sinon, un jour sans réel n'est pas « à saisir ». */
    pointe,
    /** Entrée dans le mois affiché : avant, « Hors contrat ». */
    premierJourContrat,
    /** Sortie dans le mois affiché : après, rien à saisir. */
    dernierJourContrat,
    copyPreviousMonthPlanned,
    copyPlannedToActualForDay,
    copyPlannedToActualForDays,
    bulkCopyPlannedToActual,
    loadError,
    saveError,
    isMonthDataReady,
    refetch: fetchAllCalendarData,
  };
}
