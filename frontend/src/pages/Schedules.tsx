import { useState, useEffect, useMemo } from "react";
import apiClient from "@/api/apiClient";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CalendarDayCell } from '@/components/CalendarDayCell';
import { useCalendar, WeekTemplate } from "@/hooks/useCalendar";
import { DayData } from "@/components/ScheduleModal";
import { Loader2, Save, ArrowRight, ChevronLeft, ChevronRight, Grid3x3, CalendarDays } from "lucide-react";
import { cn } from "@/lib/utils";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import * as calendarApi from '@/api/calendar';
import { isForfaitJour } from '@/utils/employeeUtils';

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string;
  statut?: string;
  contract_type?: string;
}

interface DayConfig {
  type: "travail" | "weekend" | "conge" | "ferie" | "arret_maladie";
  hours: number;
}

interface WeekConfig {
  monday: DayConfig;
  tuesday: DayConfig;
  wednesday: DayConfig;
  thursday: DayConfig;
  friday: DayConfig;
  saturday: DayConfig;
  sunday: DayConfig;
}

type WeekNumber = 1 | 2 | 3 | 4 | 5;

const INITIAL_DAY_CONFIG: DayConfig = { type: "travail", hours: 8 };
const WEEKEND_DAY_CONFIG: DayConfig = { type: "weekend", hours: 0 };

const createInitialWeek = (): WeekConfig => ({
  monday: { ...INITIAL_DAY_CONFIG },
  tuesday: { ...INITIAL_DAY_CONFIG },
  wednesday: { ...INITIAL_DAY_CONFIG },
  thursday: { ...INITIAL_DAY_CONFIG },
  friday: { ...INITIAL_DAY_CONFIG },
  saturday: { ...WEEKEND_DAY_CONFIG },
  sunday: { ...WEEKEND_DAY_CONFIG },
});

// Composant pour le formulaire de modèle de semaine
interface WeekTemplateFormProps {
  template: WeekTemplate;
  setTemplate: React.Dispatch<React.SetStateAction<WeekTemplate>>;
  onApply: () => void;
  onApplyAndSave: () => void;
  isSaving: boolean;
  isForfaitJour?: boolean;
}

function WeekTemplateForm({
  template,
  setTemplate,
  onApply,
  onApplyAndSave,
  isSaving,
  isForfaitJour = false
}: WeekTemplateFormProps) {
  const days = [
    { label: 'Lundi', key: 1 }, { label: 'Mardi', key: 2 }, { label: 'Mercredi', key: 3 },
    { label: 'Jeudi', key: 4 }, { label: 'Vendredi', key: 5 },
  ];

  const handleInputChange = (dayKey: number, value: string) => {
    setTemplate(prev => ({ ...prev, [dayKey]: value }));
  };

  const handleCheckboxChange = (dayKey: number, checked: boolean) => {
    // Pour le mode forfait jour : convertir le booléen en string "1" ou "0"
    setTemplate(prev => ({ ...prev, [dayKey]: checked ? '1' : '0' }));
  };

  return (
    <Card className="mb-4 bg-muted/40">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Modèle de semaine type</CardTitle>
        <CardDescription className="text-xs">
          {isForfaitJour 
            ? "Cochez les jours prévus, puis appliquez-les à tout le mois."
            : "Définissez les heures prévues, puis appliquez-les à tout le mois."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col md:flex-row items-center gap-4">
        <div className="grid grid-cols-5 gap-3 flex-grow">
          {days.map(day => (
            <div key={day.key} className="grid gap-1.5">
              <Label htmlFor={`template-day-${day.key}`} className="text-xs">{day.label}</Label>
              {isForfaitJour ? (
                // Mode forfait jour : Checkbox pour jour travaillé
                <div className="flex items-center gap-2 h-9 px-3 border rounded-md bg-background">
                  <Checkbox
                    id={`template-day-${day.key}`}
                    checked={template[day.key] === '1'}
                    onCheckedChange={(checked) => handleCheckboxChange(day.key, checked === true)}
                    className="h-4 w-4"
                  />
                  <label 
                    htmlFor={`template-day-${day.key}`}
                    className="text-xs cursor-pointer flex-1"
                  >
                    Jour travaillé
                  </label>
                </div>
              ) : (
                // Mode normal : Input numérique pour les heures
                <Input
                  id={`template-day-${day.key}`} 
                  type="number" 
                  placeholder="h"
                  value={template[day.key] || ''}
                  onChange={(e) => handleInputChange(day.key, e.target.value)}
                  className="h-9"
                />
              )}
            </div>
          ))}
        </div>

        <Button
          onClick={onApplyAndSave}
          disabled={isSaving}
          className="w-full md:w-auto mt-4 md:mt-0 bg-green-600 text-white hover:bg-green-700"
        >
          {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin"/> : <Save className="mr-2 h-4 w-4"/>}
          Appliquer et Enregistrer
        </Button>
        <Button onClick={onApply} disabled={isSaving} className="w-full md:w-auto mt-4 md:mt-0">
          <ArrowRight className="mr-2 h-4 w-4"/>
          Appliquer au mois
        </Button>
      </CardContent>
    </Card>
  );
}

// Panneau d'actions groupées
interface BulkActionPanelProps {
  selectedCount: number;
  onBulkUpdate: (data: Partial<Omit<DayData, 'jour'>>) => void;
  updateSelection: (mode: 'all' | 'weekdays' | 'none') => void;
  onBulkUpdateAndSave: (data: Partial<Omit<DayData, 'jour'>>) => void;
  isSaving: boolean;
  /** IDs des employés concernés par la mise à jour (pour détecter forfait jour / cas mixte) */
  selectedEmployeeIds?: Set<string>;
  /** Liste des employés avec statut (pour détecter forfait jour) */
  employees?: Employee[];
}

function BulkActionPanel({
  selectedCount,
  onBulkUpdate,
  updateSelection,
  onBulkUpdateAndSave,
  isSaving,
  selectedEmployeeIds = new Set(),
  employees = []
}: BulkActionPanelProps) {
  const [type, setType] = useState('');
  const [plannedHours, setPlannedHours] = useState('');
  const [actualHours, setActualHours] = useState('');
  const [actualHoursForfaitJour, setActualHoursForfaitJour] = useState('');

  // Détecter si les employés sélectionnés sont en forfait jour
  const selectedEmployees = useMemo(
    () => employees.filter(e => selectedEmployeeIds.has(e.id)),
    [employees, selectedEmployeeIds]
  );
  const forfaitJourCount = useMemo(
    () => selectedEmployees.filter(e => isForfaitJour(e.statut)).length,
    [selectedEmployees]
  );
  const allSelectedAreForfaitJour = selectedEmployees.length > 0 && forfaitJourCount === selectedEmployees.length;
  const someButNotAllForfaitJour = forfaitJourCount > 0 && forfaitJourCount < selectedEmployees.length;
  const hasMixedForfaitJour = someButNotAllForfaitJour;

  const buildUpdateDataAndCall = (
    callback: (data: Partial<Omit<DayData, 'jour'>>) => void
  ) => {
    const updateData: Partial<Omit<DayData, 'jour'>> = {};
    let hasUpdate = false;

    if (type) {
      updateData.type = type;
      if (type !== 'travail') {
        updateData.heures_prevues = null;
      }
      hasUpdate = true;
    }

    if (allSelectedAreForfaitJour) {
      // Mode forfait jour : heures_prevues = 1 (jour prévu) ou 0 (jour non prévu)
      const parsedPlanned = plannedHours.trim() !== '' ? parseFloat(plannedHours) : NaN;
      if (!isNaN(parsedPlanned)) {
        updateData.heures_prevues = parsedPlanned > 0 ? 1 : 0;
        if (type === '' && parsedPlanned > 0) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    } else {
      // Mode normal : nombre d'heures
      const parsedPlanned = parseFloat(plannedHours);
      if (!isNaN(parsedPlanned)) {
        updateData.heures_prevues = parsedPlanned;
        if (type === '' && parsedPlanned > 0) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    }

    if (allSelectedAreForfaitJour) {
      // Mode forfait jour : heures_faites = 1 (jour travaillé) ou 0 (jour non travaillé)
      const parsedActual = actualHoursForfaitJour.trim() !== '' ? parseFloat(actualHoursForfaitJour) : NaN;
      if (!isNaN(parsedActual)) {
        updateData.heures_faites = parsedActual > 0 ? 1 : 0;
        if (type === '' && parsedActual > 0 && !updateData.type) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    } else {
      // Mode normal : nombre d'heures
      const parsedActual = parseFloat(actualHours);
      if (!isNaN(parsedActual)) {
        updateData.heures_faites = parsedActual;
        if (type === '' && parsedActual > 0 && !updateData.type) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    }

    if (hasUpdate) {
      callback(updateData);
    }
  };

  const bulkDisabled = isSaving || hasMixedForfaitJour;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-card p-3 border rounded-lg shadow-2xl flex items-center gap-4 animate-in fade-in-90 slide-in-from-bottom-10">
      
      <div className="flex flex-col pr-4 border-r">
        <p className="text-sm font-medium">{selectedCount} jours sélectionnés</p>
        <div className="flex items-center gap-1.5 mt-1">
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => updateSelection('all')}>
            Tout
          </Button>
          <span className="text-xs text-muted-foreground">|</span>
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => updateSelection('weekdays')}>
            Ouvrés
          </Button>
          <span className="text-xs text-muted-foreground">|</span>
          <Button variant="link" size="sm" className="h-auto p-0 text-xs text-destructive hover:text-destructive" onClick={() => updateSelection('none')}>
            Désélectionner
          </Button>
        </div>
      </div>

      {hasMixedForfaitJour && (
        <p className="text-xs text-amber-600 max-w-[200px]">
          Cas mixte (forfait jour / heures) : sélectionnez un seul employé pour la mise à jour groupée.
        </p>
      )}
      
      <div className={cn("flex items-center gap-3", hasMixedForfaitJour && "opacity-60")}>
        <Label htmlFor="bulk-type" className="text-xs">Marquer comme:</Label>
        <Select value={type} onValueChange={setType} disabled={bulkDisabled}>
          <SelectTrigger id="bulk-type" className="h-8 w-[130px] text-xs"><SelectValue placeholder="Type..." /></SelectTrigger>
          <SelectContent>
            <SelectItem value="travail">Travail</SelectItem>
            <SelectItem value="conge">Congé</SelectItem>
            <SelectItem value="ferie">Férié</SelectItem>
            <SelectItem value="arret_maladie">Arrêt Maladie</SelectItem>
            <SelectItem value="weekend">Weekend</SelectItem>
          </SelectContent>
        </Select>
        <Label htmlFor="bulk-planned-hours" className="text-xs">
          {allSelectedAreForfaitJour ? "J. prévus:" : "H. prévues:"}
        </Label>
        {allSelectedAreForfaitJour ? (
          <Select
            value={plannedHours === '1' ? '1' : plannedHours === '0' ? '0' : ''}
            onValueChange={setPlannedHours}
            disabled={bulkDisabled}
          >
            <SelectTrigger id="bulk-planned-hours" className="h-8 w-[100px] text-xs">
              <SelectValue placeholder="–" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Jour prévu</SelectItem>
              <SelectItem value="0">Jour non prévu</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <Input id="bulk-planned-hours" type="number" value={plannedHours} onChange={e => setPlannedHours(e.target.value)} placeholder="ex: 8" className="h-8 w-20 text-xs" disabled={bulkDisabled} />
        )}
        <Label htmlFor="bulk-actual-hours" className="text-xs">
          {allSelectedAreForfaitJour ? "J. travaillés:" : "H. faites:"}
        </Label>
        {allSelectedAreForfaitJour ? (
          <Select
            value={actualHoursForfaitJour === '1' ? '1' : actualHoursForfaitJour === '0' ? '0' : ''}
            onValueChange={setActualHoursForfaitJour}
            disabled={bulkDisabled}
          >
            <SelectTrigger id="bulk-actual-hours" className="h-8 w-[100px] text-xs">
              <SelectValue placeholder="–" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Jour travaillé</SelectItem>
              <SelectItem value="0">Jour non travaillé</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <Input id="bulk-actual-hours" type="number" value={actualHours} onChange={e => setActualHours(e.target.value)} placeholder="ex: 7.5" className="h-8 w-20 text-xs" disabled={bulkDisabled} />
        )}
      </div>

      <Button
        size="sm"
        onClick={() => buildUpdateDataAndCall(onBulkUpdateAndSave)}
        disabled={bulkDisabled}
        className="bg-green-600 text-white hover:bg-green-700"
      >
        {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin"/> : <Save className="mr-2 h-4 w-4"/>}
        Appliquer et Enregistrer
      </Button>
      <Button size="sm" onClick={() => buildUpdateDataAndCall(onBulkUpdate)} disabled={bulkDisabled}>
        Appliquer
      </Button>
      <Button size="sm" variant="ghost" onClick={() => updateSelection('none')} disabled={isSaving}>
        Annuler
      </Button>
    </div>
  );
}

export default function Schedules() {
  const currentDate = new Date();
  const [selectedMonth, setSelectedMonth] = useState<number>(
    currentDate.getMonth() + 1
  );
  const [selectedYear, setSelectedYear] = useState<number>(
    currentDate.getFullYear()
  );

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<Set<string>>(
    new Set()
  );
  const [searchQuery, setSearchQuery] = useState("");

  const [useForAllWeeks, setUseForAllWeeks] = useState<boolean>(true);
  const [activeWeekTab, setActiveWeekTab] = useState<WeekNumber>(1);

  const [weekConfigs, setWeekConfigs] = useState<Record<WeekNumber, WeekConfig>>({
    1: createInitialWeek(),
    2: createInitialWeek(),
    3: createInitialWeek(),
    4: createInitialWeek(),
    5: createInitialWeek(),
  });

  const [isApplying, setIsApplying] = useState(false);

  // État pour l'onglet des calendriers individuels
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);

  useEffect(() => {
    async function fetchEmployees() {
      try {
        const response = await apiClient.get("/api/employees");
        if (response.data) setEmployees(response.data);
      } catch (error) {
        console.error("Erreur lors du chargement des employés:", error);
      }
    }
    fetchEmployees();
  }, []);

  const filteredEmployees = useMemo(() => {
    if (!searchQuery) return employees;
    const q = searchQuery.toLowerCase();
    return employees.filter(
      (e) =>
        e.first_name.toLowerCase().includes(q) ||
        e.last_name.toLowerCase().includes(q) ||
        e.job_title?.toLowerCase().includes(q)
    );
  }, [employees, searchQuery]);

  const toggleEmployee = (id: string) => {
    const newSet = new Set(selectedEmployeeIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedEmployeeIds(newSet);
  };

  const toggleSelectAll = () => {
    if (selectedEmployeeIds.size === filteredEmployees.length)
      setSelectedEmployeeIds(new Set());
    else setSelectedEmployeeIds(new Set(filteredEmployees.map((e) => e.id)));
  };

  const updateDayConfig = (
    week: WeekNumber,
    day: keyof WeekConfig,
    field: "type" | "hours",
    value: any
  ) => {
    setWeekConfigs((prev) => ({
      ...prev,
      [week]: {
        ...prev[week],
        [day]: { ...prev[week][day], [field]: value },
      },
    }));
  };

  const previewCalendar = useMemo(() => {
    const daysInMonth = new Date(selectedYear, selectedMonth, 0).getDate();
    const firstDayOfMonth = new Date(selectedYear, selectedMonth - 1, 1);
    const calendar: any[] = [];

    for (let d = 1; d <= daysInMonth; d++) {
      const date = new Date(selectedYear, selectedMonth - 1, d);
      const dayOfWeek = date.getDay();
      const weekOfMonth = Math.floor((d + firstDayOfMonth.getDay() - 1) / 7) + 1;
      const weekNumber = Math.min(weekOfMonth, 5) as WeekNumber;
      const config = useForAllWeeks ? weekConfigs[1] : weekConfigs[weekNumber];
      const dayKeys: (keyof WeekConfig)[] = [
        "sunday",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
      ];
      const dayConfig = config[dayKeys[dayOfWeek]];
      calendar.push({
        date: d,
        type: dayConfig.type,
        heures_prevues: dayConfig.type === "travail" ? dayConfig.hours : 0,
      });
    }
    return calendar;
  }, [selectedMonth, selectedYear, weekConfigs, useForAllWeeks]);

  const handleApplyModel = async () => {
    if (selectedEmployeeIds.size === 0) return;
    setIsApplying(true);
    try {
      const modelToApply = useForAllWeeks
        ? { 1: weekConfigs[1], 2: weekConfigs[1], 3: weekConfigs[1], 4: weekConfigs[1], 5: weekConfigs[1] }
        : weekConfigs;

      const res = await apiClient.post("/api/schedules/apply-model", {
        employee_ids: Array.from(selectedEmployeeIds),
        year: selectedYear,
        month: selectedMonth,
        week_configs: modelToApply,
      });
      if (res.status === 200) {
        alert(`Modèle appliqué à ${selectedEmployeeIds.size} employé(s).`);
        setSelectedEmployeeIds(new Set());
      }
    } catch (err: any) {
      alert(`Erreur : ${err.response?.data?.detail || "Une erreur est survenue"}`);
    } finally {
      setIsApplying(false);
    }
  };

  const isApplyDisabled =
    selectedEmployeeIds.size === 0 || !selectedMonth || !selectedYear;

  const renderCalendar = () => {
    const daysInMonth = new Date(selectedYear, selectedMonth, 0).getDate();
    const firstDayOfMonth = new Date(selectedYear, selectedMonth - 1, 1);
    const start = (firstDayOfMonth.getDay() + 6) % 7;
    const days = [];

    for (let i = 0; i < start; i++)
      days.push(<div key={`empty-${i}`} className="h-20 bg-transparent" />);

    for (let d = 1; d <= daysInMonth; d++) {
      const info = previewCalendar.find((x) => x.date === d);
      const bg =
        info?.type === "travail"
          ? "bg-primary/10 border-primary/30"
          : info?.type === "ferie"
          ? "bg-purple-100 border-purple-300"
          : info?.type === "conge"
          ? "bg-blue-100 border-blue-300"
          : info?.type === "arret_maladie"
          ? "bg-red-100 border-red-300"
          : "bg-muted";
      days.push(
        <div
          key={d}
          className={`h-20 border rounded-lg p-2 text-center ${bg}`}
        >
          <div className="font-semibold text-sm">{d}</div>
          {info?.type === "travail" && (
            <div className="text-xs text-muted-foreground">
              {info.heures_prevues}h
            </div>
          )}
        </div>
      );
    }
    return days;
  };

  // ✅ Composant pour la vue annuelle
  // -----------------------------------------------------------------------------
  type PlannedEventData = { jour: number; type: string | null; heures_prevues: number | null };
  type ActualHoursData = { jour: number; heures_faites: number | null };

  interface YearCalendarViewProps {
    year: number;
    employeeId: string;
  }

  function YearCalendarView({ year, employeeId }: YearCalendarViewProps) {
    const [yearData, setYearData] = useState<{
      [month: number]: {
        planned: PlannedEventData[];
        actual: ActualHoursData[];
      };
    }>({});
    const [isLoadingYear, setIsLoadingYear] = useState(true);

    const monthNames = [
      "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
      "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ];

    // Charger les données de tous les mois de l'année
    useEffect(() => {
      const loadYearData = async () => {
        setIsLoadingYear(true);
        try {
          const promises = Array.from({ length: 12 }, async (_, monthIndex) => {
            const month = monthIndex + 1;
            const [plannedRes, actualRes] = await Promise.all([
              calendarApi.getPlannedCalendar(employeeId, year, month),
              calendarApi.getActualHours(employeeId, year, month)
            ]);

            const plannedDataFromApi = plannedRes.data.calendrier_prevu || [];
            const actualDataFromApi = actualRes.data.calendrier_reel || [];

            const daysInMonth = new Date(year, month, 0).getDate();

            // Créer un calendrier de base complet pour le mois
            const baseCalendar: PlannedEventData[] = [];
            for (let i = 1; i <= daysInMonth; i++) {
              const date = new Date(year, month - 1, i);
              const isWeekend = date.getDay() === 0 || date.getDay() === 6;
              baseCalendar.push({
                jour: i,
                type: isWeekend ? 'weekend' : 'travail',
                heures_prevues: null
              });
            }

            const finalPlannedCalendar = baseCalendar.map(defaultDay => {
              const apiDay = plannedDataFromApi.find((p: PlannedEventData) => p.jour === defaultDay.jour);
              return apiDay ? { ...defaultDay, ...apiDay } : defaultDay;
            });

            const finalActualHours = baseCalendar.map(defaultDay => {
              const apiDay = actualDataFromApi.find((a: ActualHoursData) => a.jour === defaultDay.jour);
              return apiDay ? { jour: defaultDay.jour, heures_faites: apiDay.heures_faites } : { jour: defaultDay.jour, heures_faites: null };
            });

            return {
              month,
              planned: finalPlannedCalendar,
              actual: finalActualHours
            };
          });

          const results = await Promise.all(promises);
          const dataByMonth: typeof yearData = {};
          results.forEach(result => {
            dataByMonth[result.month] = {
              planned: result.planned,
              actual: result.actual
            };
          });
          setYearData(dataByMonth);
        } catch (error) {
          console.error("Erreur lors du chargement des données annuelles", error);
        } finally {
          setIsLoadingYear(false);
        }
      };

      loadYearData();
    }, [year, employeeId]);

    const getTypeColor = (type: string | null | undefined) => {
      switch (type) {
        case 'travail': return 'bg-sky-100 text-sky-700';
        case 'conge': return 'bg-amber-100 text-amber-700';
        case 'ferie': return 'bg-purple-100 text-purple-700';
        case 'arret_maladie': return 'bg-red-100 text-red-700';
        case 'weekend': return 'bg-slate-100 text-slate-600';
        default: return 'bg-gray-50 text-gray-500';
      }
    };

    const isAbsence = (type: string | null | undefined) => {
      return type === 'conge' || type === 'ferie' || type === 'arret_maladie';
    };

    const renderMonth = (monthIndex: number) => {
      const month = monthIndex + 1;
      const monthData = yearData[month];

      if (!monthData) {
        return (
          <Card key={monthIndex} className="p-3">
            <CardTitle className="text-sm font-semibold mb-2 text-center">
              {monthNames[monthIndex]}
            </CardTitle>
            <div className="flex items-center justify-center h-32">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          </Card>
        );
      }

      const firstDay = new Date(year, monthIndex, 1);
      const lastDay = new Date(year, monthIndex + 1, 0);
      const startDay = (firstDay.getDay() + 6) % 7;
      const daysInMonth = lastDay.getDate();

      const days = [];

      // Cases vides avant le premier jour
      for (let i = 0; i < startDay; i++) {
        days.push(<div key={`empty-${i}`} className="aspect-square" />);
      }

      // Jours du mois
      for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(year, monthIndex, day);
        const isToday = date.toDateString() === new Date().toDateString();

        // Trouver les données pour ce jour dans les tableaux
        const dayData = monthData.planned.find(d => d.jour === day);
        const actualData = monthData.actual.find(d => d.jour === day);

        const typeColor = getTypeColor(dayData?.type);
        const hasAbsence = isAbsence(dayData?.type);

        days.push(
          <div
            key={day}
            className={cn(
              "aspect-square rounded-md flex items-center justify-center text-xs font-medium transition-colors",
              typeColor,
              isToday && 'ring-2 ring-primary',
              hasAbsence && 'ring-2 ring-rose-400'
            )}
            title={`${day} ${monthNames[monthIndex]}: ${dayData?.type || 'non défini'}${dayData?.heures_prevues ? ` - ${dayData.heures_prevues}h prévues` : ''}${actualData?.heures_faites ? ` - ${actualData.heures_faites}h faites` : ''}`}
          >
            {day}
          </div>
        );
      }

      return (
        <Card key={monthIndex} className="p-3">
          <CardTitle className="text-sm font-semibold mb-2 text-center">
            {monthNames[monthIndex]}
          </CardTitle>
          <div className="grid grid-cols-7 gap-0.5 text-[10px] text-center text-muted-foreground mb-1">
            {["L", "M", "M", "J", "V", "S", "D"].map((d, i) => (
              <div key={i} className="font-medium">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-0.5">
            {days}
          </div>
        </Card>
      );
    };

    if (isLoadingYear) {
      return (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-12 w-12 animate-spin" />
        </div>
      );
    }

    return (
      <div className="space-y-4 p-4">
        {/* Légende */}
        <Card className="p-4 bg-muted/40">
          <div className="flex flex-wrap gap-x-6 gap-y-2 justify-center text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-sky-100 border border-sky-200"></div>
              <span className="text-sky-700">Travail</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-amber-100 border border-amber-200"></div>
              <span className="text-amber-700">Congé</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-purple-100 border border-purple-200"></div>
              <span className="text-purple-700">Férié</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-red-100 border border-red-200"></div>
              <span className="text-red-700">Arrêt Maladie</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-slate-100 border border-slate-200"></div>
              <span className="text-slate-600">Weekend</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-amber-100 border border-amber-200 ring-2 ring-rose-400"></div>
              <span className="text-rose-600">Absence</span>
            </div>
          </div>
        </Card>

        {/* Grille des mois */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 12 }, (_, i) => renderMonth(i))}
        </div>
      </div>
    );
  }
  // -----------------------------------------------------------------------------

  // Composant pour afficher le calendrier d'un employé
  const EmployeeCalendarView = ({ employeeId, employeeName, onBack }: { employeeId: string; employeeName: string; onBack: () => void }) => {
    // Récupérer l'employé sélectionné depuis la liste (l'API GET /api/employees retourne statut et contract_type via .select("*"))
    const employee = employees.find(e => e.id === employeeId);
    const employeeStatut = employee?.statut;

    const {
      selectedDate,
      setSelectedDate,
      plannedCalendar,
      actualHours,
      isLoading: isCalendarLoading,
      isSaving,
      saveAllCalendarData,
      updateDayData,
      weekTemplate,
      setWeekTemplate,
      applyWeekTemplate,
      selectedDays,
      setSelectedDays,
      handleDaySelection,
      bulkUpdateDays,
      isDirty,
      applyWeekTemplateAndSave,
      bulkUpdateDaysAndSave,
      updateSelection,
      isForfaitJour
    } = useCalendar(employeeId, employeeStatut);

    // ✅ État pour la vue (mensuelle/annuelle)
    const [calendarView, setCalendarView] = useState<'month' | 'year'>('month');

    const handlePreviousMonth = () => {
      if (calendarView === 'month') {
        const newMonth = selectedDate.month === 1 ? 12 : selectedDate.month - 1;
        const newYear = selectedDate.month === 1 ? selectedDate.year - 1 : selectedDate.year;
        setSelectedDate({ month: newMonth, year: newYear });
      } else {
        setSelectedDate({ month: selectedDate.month, year: selectedDate.year - 1 });
      }
    };

    const handleNextMonth = () => {
      if (calendarView === 'month') {
        const newMonth = selectedDate.month === 12 ? 1 : selectedDate.month + 1;
        const newYear = selectedDate.month === 12 ? selectedDate.year + 1 : selectedDate.year;
        setSelectedDate({ month: newMonth, year: newYear });
      } else {
        setSelectedDate({ month: selectedDate.month, year: selectedDate.year + 1 });
      }
    };

    return (
      <div className="space-y-4">
        <Button variant="outline" onClick={onBack}>
          ← Retour à la liste
        </Button>

        <Card>
          <CardHeader className="flex flex-row justify-between items-center">
            <div className="flex items-center gap-4">
              <div>
                <CardTitle>Calendrier de {employeeName}</CardTitle>
                <CardDescription className="flex items-center gap-3 mt-3">

                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-gray-600 hover:text-primary transition"
                    onClick={handlePreviousMonth}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>

                  <span className="text-base font-medium capitalize text-foreground/90 tracking-wide">
                    {calendarView === 'month'
                      ? new Date(selectedDate.year, selectedDate.month - 1).toLocaleString("fr-FR", {
                          month: "long",
                          year: "numeric",
                        })
                      : selectedDate.year
                    }
                  </span>

                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-gray-600 hover:text-primary transition"
                    onClick={handleNextMonth}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </CardDescription>

              </div>

              {/* ✅ Toggle pour basculer entre vue mensuelle et annuelle */}
              <ToggleGroup
                type="single"
                value={calendarView}
                onValueChange={(value) => value && setCalendarView(value as 'month' | 'year')}
                className="border rounded-lg p-1"
              >
                <ToggleGroupItem value="month" aria-label="Vue mensuelle" className="gap-2">
                  <CalendarDays className="h-4 w-4" />
                  <span className="hidden sm:inline">Mois</span>
                </ToggleGroupItem>
                <ToggleGroupItem value="year" aria-label="Vue annuelle" className="gap-2">
                  <Grid3x3 className="h-4 w-4" />
                  <span className="hidden sm:inline">Année</span>
                </ToggleGroupItem>
              </ToggleGroup>
            </div>

            <Button
              onClick={saveAllCalendarData}
              disabled={isSaving || !isDirty}
              className={cn(
                "transition-all",
                "bg-green-600 text-white",
                isDirty && !isSaving ? "hover:bg-green-700" : "",
              )}
            >
              {isSaving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin"/>
              ) : (
                <Save className="mr-2 h-4 w-4"/>
              )}
              {isSaving ? "Enregistrement..." : isDirty ? "Enregistrer" : "Enregistré"}
            </Button>
          </CardHeader>

          <CardContent className="p-0 md:p-2">
            {/* ✅ WeekTemplateForm uniquement en vue mensuelle */}
            {calendarView === 'month' && (
              <WeekTemplateForm
                template={weekTemplate}
                setTemplate={setWeekTemplate}
                onApply={applyWeekTemplate}
                onApplyAndSave={applyWeekTemplateAndSave}
                isSaving={isSaving}
                isForfaitJour={isForfaitJour}
              />
            )}

            {isCalendarLoading ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin" />
              </div>
            ) : (
              <>
                {calendarView === 'month' ? (
                  <div className="flex flex-col gap-4 p-2">
                <div className="grid grid-cols-7 text-center text-sm font-medium text-muted-foreground">
                  {["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].map((d) => (
                    <div key={d}>{d}</div>
                  ))}
                </div>

                <div className="grid grid-cols-7 gap-2 sm:gap-3">
                  {(() => {
                    const year = selectedDate.year;
                    const month = selectedDate.month - 1;
                    const firstDay = new Date(year, month, 1);
                    const lastDay = new Date(year, month + 1, 0);
                    const startDay = (firstDay.getDay() + 6) % 7;
                    const daysInMonth = lastDay.getDate();

                    const days = [];
                    for (let i = 0; i < startDay; i++) days.push(<div key={`empty-${i}`} />);
                    for (let day = 1; day <= daysInMonth; day++) {
                      const date = new Date(year, month, day);
                      const isToday = date.toDateString() === new Date().toDateString();
                      const arg = { date, dayNumberText: String(day), isToday } as any;

                      days.push(
                        <div
                          key={day}
                          className="aspect-square rounded-2xl bg-white dark:bg-slate-900/40 shadow-sm hover:shadow-md transition-all"
                        >
                          <CalendarDayCell
                            arg={arg}
                            plannedCalendar={plannedCalendar}
                            actualHours={actualHours}
                            updateDayData={updateDayData}
                            selectedDays={selectedDays}
                            onDaySelect={handleDaySelection}
                            selectedDate={selectedDate}
                            isForfaitJour={isForfaitJour}
                          />
                        </div>
                      );
                    }
                    return days;
                  })()}
                </div>
                  </div>
                ) : (
                  <YearCalendarView
                    year={selectedDate.year}
                    employeeId={employeeId}
                  />
                )}
              </>
            )}
          </CardContent>
        </Card>

        {selectedDays.length > 0 && (
          <BulkActionPanel
            selectedCount={selectedDays.length}
            onBulkUpdate={bulkUpdateDays}
            updateSelection={updateSelection}
            onBulkUpdateAndSave={bulkUpdateDaysAndSave}
            isSaving={isSaving}
            selectedEmployeeIds={new Set([employeeId])}
            employees={employees}
          />
        )}
      </div>
    );
  };

  // Composant pour afficher la liste des employés avec leurs infos calendrier
  const EmployeeCalendarList = () => {
    const [calendarStats, setCalendarStats] = useState<Record<string, { heuresPrevues: number; heuresFaites: number }>>({});

    // Utiliser le mois en cours
    const currentMonth = currentDate.getMonth() + 1;
    const currentYear = currentDate.getFullYear();

    useEffect(() => {
      async function fetchCalendarStats() {
        const stats: Record<string, { heuresPrevues: number; heuresFaites: number }> = {};
        for (const emp of employees) {
          try {
            const [plannedRes, actualRes] = await Promise.all([
              apiClient.get(`/api/employees/${emp.id}/calendar/planned?year=${currentYear}&month=${currentMonth}`),
              apiClient.get(`/api/employees/${emp.id}/calendar/actual?year=${currentYear}&month=${currentMonth}`)
            ]);

            const heuresPrevues = plannedRes.data.calendrier_prevu.reduce((sum: number, day: any) =>
              sum + (day.heures_prevues || 0), 0);
            const heuresFaites = actualRes.data.calendrier_reel.reduce((sum: number, day: any) =>
              sum + (day.heures_faites || 0), 0);

            stats[emp.id] = { heuresPrevues, heuresFaites };
          } catch (error) {
            stats[emp.id] = { heuresPrevues: 0, heuresFaites: 0 };
          }
        }
        setCalendarStats(stats);
      }

      if (employees.length > 0) {
        fetchCalendarStats();
      }
    }, [employees, currentMonth, currentYear]);

    if (selectedEmployeeId) {
      const selectedEmployee = employees.find(e => e.id === selectedEmployeeId);
      return (
        <EmployeeCalendarView
          employeeId={selectedEmployeeId}
          employeeName={selectedEmployee ? `${selectedEmployee.first_name} ${selectedEmployee.last_name}` : ''}
          onBack={() => setSelectedEmployeeId(null)}
        />
      );
    }

    return (
      <div className="space-y-4">
        <Input
          placeholder="Rechercher un employé..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />

        <ScrollArea className="h-[calc(100vh-300px)]">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredEmployees.map((employee) => {
              const stats = calendarStats[employee.id] || { heuresPrevues: 0, heuresFaites: 0 };
              return (
                <Card
                  key={employee.id}
                  className="cursor-pointer hover:shadow-lg transition-shadow"
                  onClick={() => setSelectedEmployeeId(employee.id)}
                >
                  <CardHeader>
                    <CardTitle className="text-lg">
                      {employee.first_name} {employee.last_name}
                    </CardTitle>
                    <CardDescription>{employee.job_title}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Heures prévues ({currentMonth}/{currentYear}):</span>
                        <span className="font-semibold">{stats.heuresPrevues.toFixed(1)}h</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Heures faites ({currentMonth}/{currentYear}):</span>
                        <span className="font-semibold">{stats.heuresFaites.toFixed(1)}h</span>
                      </div>
                      {stats.heuresFaites > 0 && (
                        <div className="flex justify-between pt-2 border-t">
                          <span className="text-muted-foreground">Écart:</span>
                          <span className={cn(
                            "font-semibold",
                            stats.heuresFaites - stats.heuresPrevues > 0 ? "text-green-600" : "text-red-600"
                          )}>
                            {(stats.heuresFaites - stats.heuresPrevues).toFixed(1)}h
                          </span>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold text-foreground">Gestion des calendriers</h1>

      <Tabs defaultValue="gestion" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="gestion">Gestion des Calendriers</TabsTrigger>
          <TabsTrigger value="calendriers">Calendriers</TabsTrigger>
        </TabsList>

        <TabsContent value="gestion" className="mt-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* === PANNEAU 1 : CIBLE === */}
        <Card className="glass-card border-0 shadow-soft">
          <CardHeader>
            <CardTitle className="text-blue-600">Cible (Qui & Quand)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Mois</Label>
                <Select
                  value={String(selectedMonth)}
                  onValueChange={(v) => setSelectedMonth(Number(v))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {[
                      "Janvier","Février","Mars","Avril","Mai","Juin",
                      "Juillet","Août","Septembre","Octobre","Novembre","Décembre",
                    ].map((m, i) => (
                      <SelectItem key={i} value={String(i + 1)}>
                        {m}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Année</Label>
                <Select
                  value={String(selectedYear)}
                  onValueChange={(v) => setSelectedYear(Number(v))}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {[2024, 2025, 2026, 2027].map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label>Employés</Label>
              <Input
                placeholder="Rechercher un employé..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />

              <div className="flex items-center gap-2 mt-2">
                <Checkbox
                  checked={
                    selectedEmployeeIds.size === filteredEmployees.length &&
                    filteredEmployees.length > 0
                  }
                  onCheckedChange={toggleSelectAll}
                />
                <span className="text-sm text-muted-foreground">
                  Tout sélectionner
                </span>
              </div>

              <ScrollArea className="h-[380px] mt-2 rounded-md border p-2">
                {filteredEmployees.map((e) => (
                  <div
                    key={e.id}
                    onClick={() => toggleEmployee(e.id)}
                    className={`flex items-start gap-3 p-3 rounded-md cursor-pointer transition ${
                      selectedEmployeeIds.has(e.id)
                        ? "bg-primary/10 border border-primary/20"
                        : "hover:bg-accent"
                    }`}
                  >
                    <Checkbox
                      checked={selectedEmployeeIds.has(e.id)}
                      onCheckedChange={() => {}}
                    />
                    <div className="flex flex-col">
                      <span className="font-medium">
                        {e.first_name} {e.last_name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {e.job_title}
                      </span>
                    </div>
                  </div>
                ))}
              </ScrollArea>

              <p className="text-xs text-muted-foreground mt-2">
                {selectedEmployeeIds.size} employé(s) sélectionné(s)
              </p>
            </div>
          </CardContent>
        </Card>

        {/* === PANNEAU 2 : MODÈLE === */}
        <Card className="glass-card border-0 shadow-soft">
          <CardHeader>
            <CardTitle className="text-emerald-600">Modèle de planning</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2">
              <Checkbox
                checked={useForAllWeeks}
                onCheckedChange={(v) => setUseForAllWeeks(!!v)}
              />
              <span className="text-sm text-muted-foreground">
                Utiliser ce modèle pour toutes les semaines
              </span>
            </div>

            <div className="overflow-x-auto">
              <Tabs
                value={String(activeWeekTab)}
                onValueChange={(v) => setActiveWeekTab(Number(v) as WeekNumber)}
                className="w-max min-w-full"
              >
                <TabsList className="flex gap-2 w-max">
                  {[1, 2, 3, 4, 5].map((w) => (
                    <TabsTrigger
                      key={w}
                      value={String(w)}
                      disabled={useForAllWeeks && w !== 1}
                      className="whitespace-nowrap"
                    >
                      Semaine {w}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            </div>


            {(["monday","tuesday","wednesday","thursday","friday","saturday","sunday"] as (keyof WeekConfig)[]).map(
              (day) => {
                const label = {
                  monday: "Lundi",
                  tuesday: "Mardi",
                  wednesday: "Mercredi",
                  thursday: "Jeudi",
                  friday: "Vendredi",
                  saturday: "Samedi",
                  sunday: "Dimanche",
                }[day];
                const current = useForAllWeeks ? 1 : activeWeekTab;
                const conf = weekConfigs[current][day];
                const disabled = useForAllWeeks && activeWeekTab !== 1;

                return (
                  <div key={day} className="grid grid-cols-3 gap-3 items-center">
                    <Label>{label}</Label>
                    <Select
                      value={conf.type}
                      onValueChange={(v) =>
                        updateDayConfig(current, day, "type", v)
                      }
                      disabled={disabled}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="travail">Travail</SelectItem>
                        <SelectItem value="conge">Congé</SelectItem>
                        <SelectItem value="ferie">Férié</SelectItem>
                        <SelectItem value="arret_maladie">Arrêt Maladie</SelectItem>
                        <SelectItem value="weekend">Weekend</SelectItem>
                      </SelectContent>
                    </Select>

                    <Input
                      type="number"
                      min="0"
                      max="24"
                      step="0.5"
                      value={conf.hours}
                      onChange={(e) =>
                        updateDayConfig(current, day, "hours", Number(e.target.value))
                      }
                      disabled={disabled || conf.type !== "travail"}
                    />
                  </div>
                );
              }
            )}
          </CardContent>
        </Card>

        {/* === PANNEAU 3 : APERÇU === */}
        <Card className="glass-card border-0 shadow-soft">
          <CardHeader>
            <CardTitle className="text-indigo-600">Aperçu</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-center mb-4">
              <p className="text-lg font-medium text-foreground">
                {
                  [
                    "Janvier","Février","Mars","Avril","Mai","Juin","Juillet",
                    "Août","Septembre","Octobre","Novembre","Décembre",
                  ][selectedMonth - 1]
                }{" "}
                {selectedYear}
              </p>
            </div>
            <div className="grid grid-cols-7 text-xs font-semibold text-muted-foreground mb-2 text-center">
              {["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"].map((d) => (
                <div key={d}>{d}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">{renderCalendar()}</div>

            <div className="mt-4 space-y-2 text-sm">
              <p className="font-medium">Légende :</p>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-primary/10 border border-primary/30 rounded" />
                <span>Travail</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-100 border border-blue-300 rounded" />
                <span>Congé</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-purple-100 border border-purple-300 rounded" />
                <span>Férié</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-red-100 border border-red-300 rounded" />
                <span>Arrêt Maladie</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-muted rounded" />
                <span>Weekend</span>
              </div>
            </div>
          </CardContent>
        </Card>
          </div>

          <div className="flex justify-center mt-6">
            <Button
              onClick={handleApplyModel}
              disabled={isApplyDisabled || isApplying}
              variant="default"
              className="px-8"
            >
              {isApplying
                ? "Application en cours..."
                : `Appliquer le modèle à ${selectedEmployeeIds.size} employé(s)`}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="calendriers" className="mt-6">
          <EmployeeCalendarList />
        </TabsContent>
      </Tabs>
    </div>
  );
}
