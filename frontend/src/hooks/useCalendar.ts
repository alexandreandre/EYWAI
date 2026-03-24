// src/hooks/useCalendar.ts

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useToast } from "@/components/ui/use-toast";
import * as calendarApi from '@/api/calendar';
import { DayData } from '@/components/ScheduleModal';
import { isForfaitJour } from '@/utils/employeeUtils';

// On reprend les types de données depuis notre fichier d'API
type PlannedEventData = calendarApi.PlannedEventData;
type ActualHoursData = calendarApi.ActualHoursData;

/**
 * Hook personnalisé pour gérer toute la logique du calendrier d'un employé.
 * @param employeeId L'ID de l'employé pour lequel charger le calendrier.
 * @param employeeStatut Le statut de l'employé (ex: "Cadre au forfait jour") pour déterminer le mode forfait jour.
 */

export type WeekTemplate = {
  [key: number]: string; // Clé 1-5 pour Lun-Ven, valeur en string pour l'input
};



export function useCalendar(employeeId: string | undefined, employeeStatut?: string) {
  // Calculer si l'employé est en forfait jour
  const isForfaitJourMode = useMemo(() => isForfaitJour(employeeStatut), [employeeStatut]);
  // Initialiser le modèle de semaine selon le mode (forfait jour ou heures)
  const getInitialWeekTemplate = (forfaitJour: boolean): WeekTemplate => {
    return forfaitJour
      ? {
          1: '1', // Lundi : 1 jour travaillé
          2: '1', // Mardi : 1 jour travaillé
          3: '1', // Mercredi : 1 jour travaillé
          4: '1', // Jeudi : 1 jour travaillé
          5: '1', // Vendredi : 1 jour travaillé
        }
      : {
          1: '8', // Lundi : 8 heures
          2: '8', // Mardi : 8 heures
          3: '8', // Mercredi : 8 heures
          4: '8', // Jeudi : 8 heures
          5: '7', // Vendredi : 7 heures
        };
  };

  const [weekTemplate, setWeekTemplate] = useState<WeekTemplate>(() => getInitialWeekTemplate(isForfaitJourMode));
  
  const { toast } = useToast();
  
  // --- ÉTATS ---
  const [selectedDate, setSelectedDate] = useState({ 
    month: new Date().getMonth() + 1, 
    year: new Date().getFullYear() 
  });
  console.log('%c[HOOK RENDER] État de selectedDate au début du rendu:', 'color: orange; font-weight: bold;', selectedDate);

  // On stocke les deux ensembles de données séparément
  const [plannedCalendar, setPlannedCalendar] = useState<PlannedEventData[]>([]);
  const [actualHours, setActualHours] = useState<ActualHoursData[]>([]);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const [editingDay, setEditingDay] = useState<number | null>(null);
  
  // --- NOUVEAUX ÉTATS POUR LA SÉLECTION MULTIPLE ---
  const [selectedDays, setSelectedDays] = useState<number[]>([]);

  // ✅ NOUVEAU : États pour stocker la version originale des données
  const [originalPlanned, setOriginalPlanned] = useState<PlannedEventData[]>([]);
  const [originalActual, setOriginalActual] = useState<ActualHoursData[]>([]);

  // ✅ NOUVEAU : État pour savoir si les données ont été modifiées
  const [isDirty, setIsDirty] = useState(false);

  // ✅ NOUVEL ÉTAT : Un drapeau pour déclencher une sauvegarde après une mise à jour d'état
  const [isSavingAfterApply, setIsSavingAfterApply] = useState(false);

  // --- LOGIQUE D'ACCÈS AUX DONNÉES ---
  
  // Fonction pour charger toutes les données du calendrier depuis l'API
  const fetchAllCalendarData = useCallback(async () => {
    if (!employeeId) return;
    setIsLoading(true);
    setIsDirty(false);
    try {
      const [plannedRes, actualRes] = await Promise.all([
        calendarApi.getPlannedCalendar(employeeId, selectedDate.year, selectedDate.month),
        calendarApi.getActualHours(employeeId, selectedDate.year, selectedDate.month)
      ]);

      const plannedDataFromApi = plannedRes.data.calendrier_prevu;
      const actualDataFromApi = actualRes.data.calendrier_reel;
      
      const daysInMonth = new Date(selectedDate.year, selectedDate.month, 0).getDate();
      
      // 1. On crée un calendrier de base complet pour le mois
      const baseCalendar: PlannedEventData[] = [];
      for (let i = 1; i <= daysInMonth; i++) {
        const date = new Date(selectedDate.year, selectedDate.month - 1, i);
        const isWeekend = date.getDay() === 0 || date.getDay() === 6;
        // Pour le mode forfait jour : initialiser à 1 pour les jours travaillés, 0 pour les weekends
        // Pour le mode normal : initialiser à null (sera rempli par les données de l'API ou le modèle)
        const defaultHeuresPrevues = isForfaitJourMode
          ? (isWeekend ? 0 : 1)
          : null;
        
        baseCalendar.push({ 
            jour: i, 
            type: isWeekend ? 'weekend' : 'travail', 
            heures_prevues: defaultHeuresPrevues
        });
      }

      // 2. On fusionne les données de l'API avec notre base.
      // Si des données existent dans l'API, elles écrasent les valeurs par défaut.
      const finalPlannedCalendar = baseCalendar.map(defaultDay => {
          const apiDay = plannedDataFromApi.find(p => p.jour === defaultDay.jour);
          return apiDay ? { ...defaultDay, ...apiDay } : defaultDay;
      });

      const finalActualHours = baseCalendar.map(defaultDay => {
          const apiDay = actualDataFromApi.find(a => a.jour === defaultDay.jour);
          // On garde le type du calendrier prévu pour la cohérence
          return {
              jour: defaultDay.jour,
              type: defaultDay.type,
              heures_faites: apiDay ? apiDay.heures_faites : null
          };
      });
      

      // 3. On met à jour les états avec des calendriers toujours complets.
      setPlannedCalendar(finalPlannedCalendar);
      setActualHours(finalActualHours);

      setOriginalPlanned(finalPlannedCalendar);
      setOriginalActual(finalActualHours);

    } catch (error) {
      console.error(error);
      toast({ title: "Erreur", description: "Impossible de charger les données du calendrier.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [employeeId, selectedDate, isForfaitJourMode, toast]);
  
  // Effet qui recharge les données chaque fois que l'employé ou la date sélectionnée change
  useEffect(() => {
    fetchAllCalendarData();
  }, [fetchAllCalendarData]);

  // ✅ NOUVEAU : Réinitialiser le modèle de semaine quand le mode forfait jour change
  useEffect(() => {
    setWeekTemplate(getInitialWeekTemplate(isForfaitJourMode));
  }, [isForfaitJourMode]);

  // ✅ Effet pour détecter les changements
  useEffect(() => {
    // On ne vérifie que si on n'est pas en chargement
    if (!isLoading) {
      const plannedChanged = JSON.stringify(plannedCalendar) !== JSON.stringify(originalPlanned);
      const actualChanged = JSON.stringify(actualHours) !== JSON.stringify(originalActual);
      
      setIsDirty(plannedChanged || actualChanged);
    }
  }, [plannedCalendar, actualHours, originalPlanned, originalActual, isLoading]);


  // ✅ Logique pour appliquer le modèle
  const applyWeekTemplate = () => {
    const newPlannedCalendar = plannedCalendar.map(day => {
      const date = new Date(selectedDate.year, selectedDate.month - 1, day.jour);
      const dayOfWeek = date.getDay(); // 0=Dim, 1=Lun, ..., 6=Sam

      // Si c'est un jour de semaine défini dans le modèle (et que ce n'est pas un férié/congé existant)
      if (dayOfWeek >= 1 && dayOfWeek <= 5 && !['ferie', 'conge'].includes(day.type)) {
        const templateValue = weekTemplate[dayOfWeek];
        
        if (isForfaitJourMode) {
          // Mode forfait jour : templateValue est "1" (jour travaillé) ou "0" (jour non travaillé)
          const isWorkDay = templateValue && templateValue.trim() !== '' && parseFloat(templateValue) > 0;
          return {
            ...day,
            type: isWorkDay ? 'travail' : 'weekend',
            heures_prevues: isWorkDay ? 1 : 0,
          };
        } else {
          // Mode normal : templateValue contient un nombre d'heures
          const hours = templateValue && templateValue.trim() !== '' ? parseFloat(templateValue) : null;
          return {
            ...day,
            type: hours !== null && hours > 0 ? 'travail' : 'weekend',
            heures_prevues: hours,
          };
        }
      }

      // Sinon (weekend ou jour déjà marqué), on ne change rien
      return day;
    });

    setPlannedCalendar(newPlannedCalendar);
    toast({ 
      title: "Modèle appliqué", 
      description: isForfaitJourMode 
        ? "Le calendrier prévisionnel a été mis à jour (mode forfait jour)." 
        : "Le calendrier prévisionnel a été mis à jour." 
    });
  };
  
  // --- Fonction pour sauvegarder toutes les modifications en une seule fois ---
  const saveAllCalendarData = useCallback(async () => {
      if (!employeeId) return;

      console.log("%c--- [WORKFLOW-PAIE | Étape 1] Déclenchement Frontend ---", "color: blue; font-weight: bold;");
      setIsSaving(true);
      try {
        console.log("  -> Action: Sauvegarde des données brutes (planned & actual)...");
        await Promise.all([
          calendarApi.updatePlannedCalendar(employeeId, selectedDate.year, selectedDate.month, plannedCalendar),
          calendarApi.updateActualHours(employeeId, selectedDate.year, selectedDate.month, actualHours)
        ]);
        console.log("  -> Succès: Données brutes enregistrées.");

        console.log("%c--- [WORKFLOW-PAIE | Étape 2] Demande de calcul au Backend ---", "color: blue; font-weight: bold;");
        await calendarApi.calculatePayrollEvents(employeeId, selectedDate.year, selectedDate.month);
        console.log("  -> Succès: Le backend a terminé le calcul.");

        setOriginalPlanned(plannedCalendar);
        setOriginalActual(actualHours);
        
        toast({ title: "Succès", description: "Calendrier et événements de paie sauvegardés et calculés." });

      } catch (error) {
        console.error(error);
        toast({ title: "Erreur", description: "La sauvegarde ou le calcul a échoué.", variant: "destructive" });
      } finally {
        setIsSaving(false);
      }
    // ✅ MODIFIÉ : On ajoute les dépendances pour que saveAllCalendarData ait toujours
    // la dernière version des données à sauvegarder.
  }, [employeeId, selectedDate, plannedCalendar, actualHours, toast]);


  // ✅ NOUVEAU : Effet pour sauvegarder automatiquement après une action "Appliquer et Enregistrer"
  useEffect(() => {
    // On ne sauvegarde que si le drapeau est levé ET qu'on n'est pas déjà en train de sauvegarder
    if (isSavingAfterApply && !isSaving) {
      console.log('%c[HOOK] Déclenchement de la sauvegarde différée...', 'color: purple');
      saveAllCalendarData(); // Cette fonction a maintenant les bonnes dépendances
      setIsSavingAfterApply(false); // On réinitialise le drapeau
    }
  }, [isSavingAfterApply, isSaving, saveAllCalendarData]);


  const updateDayData = (updatedDay: Partial<DayData>) => {
      if (updatedDay.jour === undefined) return;
  
      // Mise à jour du calendrier prévisionnel
      setPlannedCalendar(prev =>
          prev.map(p => {
              if (p.jour !== updatedDay.jour) return p;
              // On fusionne uniquement les champs pertinents pour le prévisionnel
              const newPlannedData: Partial<PlannedEventData> = {};
              if (updatedDay.type !== undefined) newPlannedData.type = updatedDay.type;
              if (updatedDay.heures_prevues !== undefined) newPlannedData.heures_prevues = updatedDay.heures_prevues;
              return { ...p, ...newPlannedData };
          })
      );
  
      // Mise à jour des heures réelles (heures_faites et type pour la cohérence)
      setActualHours(prev =>
          prev.map(a => {
              if (a.jour !== updatedDay.jour) return a;
              const newActualData: Partial<ActualHoursData> = {};
              if (updatedDay.type !== undefined) newActualData.type = updatedDay.type;
              if (updatedDay.heures_faites !== undefined) newActualData.heures_faites = updatedDay.heures_faites;
              return { ...a, ...newActualData };
          })
      );
  };
  
  // --- NOUVELLES FONCTIONS POUR LA SÉLECTION MULTIPLE ---

  /**
   * Gère la sélection/désélection d'un jour.
   */
  const handleDaySelection = (dayNumber: number, isCtrlOrMetaKey: boolean) => {
    // La logique de clic individuelle reste la même
    setSelectedDays(prev =>
      prev.includes(dayNumber)
        ? prev.filter(d => d !== dayNumber)
        : [...prev, dayNumber]
    );
  };
  
  // --- ✅ FONCTION AJOUTÉE/MODIFIÉE ---
  // Remplace l'ancienne 'onClearSelection' si tu en avais une.
  // Cette fonction gère maintenant TOUTES les actions de sélection/désélection.
  const updateSelection = (
    mode: 'all' | 'weekdays' | 'none'
  ) => {
    
    if (mode === 'none') {
      // Cas 1: Annuler (comportement par défaut)
      setSelectedDays([]);
      return;
    }

    // Calcule tous les jours du mois
    const year = selectedDate.year;
    const month = selectedDate.month - 1;
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const allDaysInMonth: number[] = [];
    
    for (let day = 1; day <= daysInMonth; day++) {
      allDaysInMonth.push(day);
    }

    if (mode === 'all') {
      // Cas 2: "Tout sélectionner"
      setSelectedDays(allDaysInMonth);
    } else if (mode === 'weekdays') {
      // Cas 3: "Jours ouvrés" (Tout sauf Samedi (6) et Dimanche (0))
      const weekdays = allDaysInMonth.filter(day => {
        const date = new Date(year, month, day);
        const dayOfWeek = date.getDay();
        return dayOfWeek !== 0 && dayOfWeek !== 6;
      });
      setSelectedDays(weekdays);
    }
  };

  /**
   * Applique une mise à jour à tous les jours sélectionnés.
   */
  const bulkUpdateDays = (updateData: Partial<Omit<DayData, 'jour'>>) => {
    if (selectedDays.length === 0) return;

    selectedDays.forEach(dayNumber => {
      updateDayData({ jour: dayNumber, ...updateData });
    });

    toast({
      title: "Mise à jour groupée",
      description: `${selectedDays.length} jours ont été modifiés.`,
    });
    setSelectedDays([]); // On désélectionne après l'action
  };


  // ✅ NOUVEAU : Fonction pour appliquer le modèle ET déclencher une sauvegarde
  const applyWeekTemplateAndSave = () => {
    applyWeekTemplate(); // Applique les changements à l'état local
    setIsSavingAfterApply(true); // Lève le drapeau pour que le useEffect sauvegarde
  };

  // ✅ NOUVEAU : Fonction pour la mise à jour groupée ET déclencher une sauvegarde
  const bulkUpdateDaysAndSave = (updateData: Partial<Omit<DayData, 'jour'>>) => {
    bulkUpdateDays(updateData); // Applique les changements à l'état local
    setIsSavingAfterApply(true); // Lève le drapeau pour que le useEffect sauvegarde
  };


  // --- On expose tous les états et fonctions dont l'interface aura besoin ---
  return {
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    setPlannedCalendar,
    actualHours,
    setActualHours,
    isLoading,
    isSaving,
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
    // ✅ NOUVEAU : Exposer les nouvelles fonctions
    applyWeekTemplateAndSave,
    bulkUpdateDaysAndSave,
    updateSelection,
    // ✅ NOUVEAU : Exposer isForfaitJour pour utilisation dans les composants parents
    isForfaitJour: isForfaitJourMode,
  };
}