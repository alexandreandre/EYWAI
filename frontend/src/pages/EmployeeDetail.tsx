// src/pages/EmployeeDetail.tsx 

import React, { useCallback, useState, useEffect } from "react";
import { useParams, Link, useNavigate, useLocation } from "react-router-dom";
import apiClient from "@/api/apiClient";

// --- Notre hook et notre modal ---
import { DayData } from "@/components/ScheduleModal";
import * as calendarApi from '@/api/calendar';

// --- Imports UI & Icônes ---
import { CalendarDayCell } from '@/components/CalendarDayCell';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { SaisieModal } from "@/components/SaisieModal";
import { Download, Calendar as CalendarIcon, FileText, Loader2, ArrowLeft, Save, ClipboardEdit, ChevronLeft, ChevronRight, UserPlus, Grid3x3, CalendarDays, Edit, MessageSquare, Play, CheckCircle, FileText as FileTextIcon, FileDown, Eye, TrendingUp, Plus, Trash2, ArrowRight, Stethoscope } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"; // prettier-ignore
import * as saisiesApi from "@/api/saisies"; // ✅ On importe le nouveau type
import { useCalendar, WeekTemplate } from "@/hooks/useCalendar"; // ✅ On importe le nouveau type
import { Input } from "@/components/ui/input"; // ✅ On importe l'Input
import { Label } from "@/components/ui/label";   // ✅ On importe le Label
import { Checkbox } from "@/components/ui/checkbox"; // ✅ On importe Checkbox pour le mode forfait jour
import { isForfaitJour } from '@/utils/employeeUtils';
import { toast } from "@/components/ui/use-toast";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ResidencePermitBadge } from "@/components/ResidencePermitBadge";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
import * as annualReviewsApi from "@/api/annualReviews";
import * as collectiveAgreementsApi from "@/api/collectiveAgreements";
import { PromotionModal } from "@/components/PromotionModal";
import { PromotionBadge } from "@/components/PromotionBadge";
import { EmployeeCSEBlock } from "@/components/EmployeeCSEBlock";
import { getEmployeePromotions } from "@/api/promotions";
import type { PromotionListItem } from "@/api/promotions";
import { getMedicalSettings, getObligationsForEmployee, type ObligationListItem } from "@/api/medicalFollowUp";


// --- Imports FullCalendar ---
// import FullCalendar, { DayCellContentArg } from '@fullcalendar/react';
// import dayGridPlugin from '@fullcalendar/daygrid';
// import frLocale from '@fullcalendar/core/locales/fr';


// --- Interfaces ---
interface Employee { 
  id: string; 
  first_name: string; 
  last_name: string; 
  job_title: string; 
  contract_type: string; 
  statut: string; 
  hire_date: string;
  // Titre de séjour (données calculées par le backend)
  is_subject_to_residence_permit?: boolean | null;
  residence_permit_status?: "valid" | "to_renew" | "expired" | "to_complete" | null;
  residence_permit_expiry_date?: string | null;
  residence_permit_days_remaining?: number | null;
  residence_permit_data_complete?: boolean | null;
  residence_permit_type?: string | null;
  residence_permit_number?: string | null;
  // Entretien courant (données calculées par le backend)
  annual_review_current_status?: string | null;
  annual_review_current_year?: number | null;
  annual_review_current_planned_date?: string | null;
  annual_review_current_completed_date?: string | null;
  collective_agreement_id?: string | null;
}
interface Payslip { id: string; name: string; url: string; month: number; year: number; }

// ✅ MODIFIÉ : Le formulaire pour le modèle de semaine
// -----------------------------------------------------------------------------
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
                    Jour prévu
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
        
        {/* ✅ NOUVEAU : Bouton "Appliquer et Enregistrer" */}
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
// -----------------------------------------------------------------------------

// ✅ MODIFIÉ : Panneau d'actions groupées
// -----------------------------------------------------------------------------
interface BulkActionPanelProps {
  selectedCount: number;
  onBulkUpdate: (data: Partial<Omit<DayData, 'jour'>>) => void;
  updateSelection: (mode: 'all' | 'weekdays' | 'none') => void;
  onBulkUpdateAndSave: (data: Partial<Omit<DayData, 'jour'>>) => void;
  isSaving: boolean;
  isForfaitJour?: boolean;
}

function BulkActionPanel({ 
  selectedCount, 
  onBulkUpdate, 
  updateSelection,
  onBulkUpdateAndSave, 
  isSaving,
  isForfaitJour = false
}: BulkActionPanelProps) {
  const [type, setType] = useState('');
  const [plannedHours, setPlannedHours] = useState('');
  const [actualHours, setActualHours] = useState('');
  const [actualHoursForfaitJour, setActualHoursForfaitJour] = useState('');

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

    if (isForfaitJour) {
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

    if (isForfaitJour) {
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

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-card p-3 border rounded-lg shadow-2xl flex items-center gap-4 animate-in fade-in-90 slide-in-from-bottom-10">
      
      {/* --- ✅ DÉBUT DE LA MODIFICATION DE L'UI --- */}
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
      {/* --- FIN DE LA MODIFICATION DE L'UI --- */}

      <div className="flex items-center gap-3">
        <Label htmlFor="bulk-type" className="text-xs">Marquer comme:</Label>
        <Select value={type} onValueChange={setType}>
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
          {isForfaitJour ? "J. prévus:" : "H. prévues:"}
        </Label>
        {isForfaitJour ? (
          <Select
            value={plannedHours === '1' ? '1' : plannedHours === '0' ? '0' : ''}
            onValueChange={setPlannedHours}
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
          <Input id="bulk-planned-hours" type="number" value={plannedHours} onChange={e => setPlannedHours(e.target.value)} placeholder="ex: 8" className="h-8 w-20 text-xs" />
        )}
        <Label htmlFor="bulk-actual-hours" className="text-xs">
          {isForfaitJour ? "J. travaillés:" : "H. faites:"}
        </Label>
        {isForfaitJour ? (
          <Select
            value={actualHoursForfaitJour === '1' ? '1' : actualHoursForfaitJour === '0' ? '0' : ''}
            onValueChange={setActualHoursForfaitJour}
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
          <Input id="bulk-actual-hours" type="number" value={actualHours} onChange={e => setActualHours(e.target.value)} placeholder="ex: 7.5" className="h-8 w-20 text-xs" />
        )}
      </div>

      <Button 
        size="sm" 
        onClick={() => buildUpdateDataAndCall(onBulkUpdateAndSave)}
        disabled={isSaving}
        className="bg-green-600 text-white hover:bg-green-700"
      >
        {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin"/> : <Save className="mr-2 h-4 w-4"/>}
        Appliquer et Enregistrer
      </Button>
      <Button size="sm" onClick={() => buildUpdateDataAndCall(onBulkUpdate)} disabled={isSaving}>
        Appliquer
      </Button>
      <Button size="sm" variant="ghost" onClick={() => updateSelection('none')} disabled={isSaving}>
        Annuler
      </Button>
    </div>
  );
}
// -----------------------------------------------------------------------------

// ✅ NOUVEAU : Composant pour la vue annuelle (calendrier)
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
        console.error("Erreur lors du chargement des données annuelles (calendrier)", error);
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


export default function EmployeeDetail() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  // --- États spécifiques à la page (hors calendrier) ---
  const [employee, setEmployee] = useState<Employee | null>(null);

  // ✅ MODIFIÉ : Le hook gère toute la logique du calendrier
  // Récupérer le statut de l'employé pour déterminer le mode forfait jour
  const employeeStatut = employee?.statut;
  
  const {
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    setPlannedCalendar,
    actualHours,
    setActualHours,
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
    // ✅ NOUVEAU : On récupère les nouvelles fonctions
    applyWeekTemplateAndSave,
    bulkUpdateDaysAndSave,
    updateSelection,
    isForfaitJour,
  } = useCalendar(employeeId, employeeStatut);
  const [payslips, setPayslips] = useState<Payslip[]>([]);
  const [contractUrl, setContractUrl] = useState<string | null>(null);
  const [identityDocumentUrl, setIdentityDocumentUrl] = useState<string | null>(null);
  const [credentialsPdfUrl, setCredentialsPdfUrl] = useState<string | null>(null);
  const [isPageLoading, setIsPageLoading] = useState(true);
  const [saisieModalOpen, setSaisieModalOpen] = useState(false);

  const [isLoadingSaisies, setIsLoadingSaisies] = useState(true);
  const [employeeSaisies, setEmployeeSaisies] = useState<any[]>([]);

  // ✅ NOUVEAU : État pour la vue calendrier (mensuelle/annuelle)
  const [calendarView, setCalendarView] = useState<'month' | 'year'>('month');
  
  // État pour l'onglet actif (détecte depuis l'URL si on vient de la fiche entretien)
  const [activeTab, setActiveTab] = useState<string>(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get('tab') || 'calendrier';
    // Rediriger l'ancien onglet "bulletins" vers "documents"
    return tabParam === 'bulletins' ? 'documents' : tabParam;
  });
  
  // Mettre à jour l'onglet actif quand l'URL change
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get('tab');
    if (tabParam) {
      // Rediriger l'ancien onglet "bulletins" vers "documents"
      setActiveTab(tabParam === 'bulletins' ? 'documents' : tabParam);
    }
  }, [location.search]);

  // Entretiens
  const [annualReviews, setAnnualReviews] = useState<import("@/api/annualReviews").AnnualReview[]>([]);
  const [planningModalOpen, setPlanningModalOpen] = useState(false);
  const [planningDate, setPlanningDate] = useState("");
  const [editingReview, setEditingReview] = useState<import("@/api/annualReviews").AnnualReview | null>(null);
  const [editStatus, setEditStatus] = useState<string>("");
  const [editPlannedDate, setEditPlannedDate] = useState<string>("");
  const [editCompletedDate, setEditCompletedDate] = useState<string>("");
  const [companyAgreements, setCompanyAgreements] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]>([]);
  const [collectiveAgreementId, setCollectiveAgreementId] = useState<string | null>(null);
  const [isSavingCC, setIsSavingCC] = useState(false);

  // Promotions
  const [promotions, setPromotions] = useState<PromotionListItem[]>([]);
  const [promotionModalOpen, setPromotionModalOpen] = useState(false);

  // Suivi médical (module optionnel)
  const [medicalModuleEnabled, setMedicalModuleEnabled] = useState(false);
  const [medicalObligations, setMedicalObligations] = useState<ObligationListItem[]>([]);

  const fetchAnnualReviews = useCallback(async () => {
    if (!employeeId) return;
    try {
      const res = await annualReviewsApi.getEmployeeAnnualReviews(employeeId);
      setAnnualReviews(res.data || []);
    } catch (err) {
      console.error("Erreur chargement entretiens", err);
    }
  }, [employeeId]);

  useEffect(() => {
    if (employeeId) fetchAnnualReviews();
  }, [employeeId, fetchAnnualReviews]);

  // Charger les promotions de l'employé
  const fetchPromotions = useCallback(async () => {
    if (!employeeId) return;
    try {
      const res = await getEmployeePromotions(employeeId);
      setPromotions(res.data || []);
    } catch (err) {
      console.error("Erreur chargement promotions", err);
      setPromotions([]);
    }
  }, [employeeId]);

  useEffect(() => {
    if (employeeId) fetchPromotions();
  }, [employeeId, fetchPromotions]);

  useEffect(() => {
    getMedicalSettings().then((r) => setMedicalModuleEnabled(r.enabled)).catch(() => setMedicalModuleEnabled(false));
  }, []);
  useEffect(() => {
    if (!medicalModuleEnabled || !employeeId) return;
    getObligationsForEmployee(employeeId).then(setMedicalObligations).catch(() => setMedicalObligations([]));
  }, [medicalModuleEnabled, employeeId]);

  useEffect(() => {
    collectiveAgreementsApi.getMyCompanyAgreements()
      .then(res => setCompanyAgreements(res.data || []))
      .catch(() => setCompanyAgreements([]));
  }, []);

  useEffect(() => {
    if (employee?.collective_agreement_id !== undefined) {
      setCollectiveAgreementId(employee.collective_agreement_id || null);
    }
  }, [employee?.collective_agreement_id]);

  const handleSaveCollectiveAgreement = async () => {
    if (!employeeId) return;
    setIsSavingCC(true);
    try {
      await apiClient.put(`/api/employees/${employeeId}`, { collective_agreement_id: collectiveAgreementId });
      toast({ title: "Enregistré", description: "Convention collective mise à jour." });
      const employeeRes = await apiClient.get(`/api/employees/${employeeId}`);
      setEmployee(employeeRes.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erreur";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    } finally {
      setIsSavingCC(false);
    }
  };

  const handlePlanAnnualReview = async () => {
    if (!employeeId) return;
    try {
      // Calculer l'année automatiquement : depuis la date prévue ou année courante
      const year = planningDate 
        ? new Date(planningDate).getFullYear()
        : new Date().getFullYear();
      
      await annualReviewsApi.createAnnualReview({
        employee_id: employeeId,
        year: year,
        planned_date: planningDate ? planningDate : null,
      });
      toast({ title: "Entretien planifié", description: "L'entretien a été créé." });
      setPlanningModalOpen(false);
      setPlanningDate("");
      fetchAnnualReviews();
      // Rafraîchir l'employé pour mettre à jour le badge
      const employeeRes = await apiClient.get(`/api/employees/${employeeId}`);
      setEmployee(employeeRes.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erreur";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    }
  };

  const handleEditReview = (review: import("@/api/annualReviews").AnnualReview) => {
    setEditingReview(review);
    setEditStatus(review.status);
    setEditPlannedDate(review.planned_date ? review.planned_date.split('T')[0] : "");
    setEditCompletedDate(review.completed_date ? review.completed_date.split('T')[0] : "");
  };

  const handleUpdateReview = async () => {
    if (!editingReview) return;
    try {
      await annualReviewsApi.updateAnnualReview(editingReview.id, {
        status: editStatus as import("@/api/annualReviews").AnnualReviewStatus,
        planned_date: editPlannedDate || null,
        completed_date: editCompletedDate || null,
      });
      toast({ title: "Entretien mis à jour", description: "Les modifications ont été enregistrées." });
      setEditingReview(null);
      setEditStatus("");
      setEditPlannedDate("");
      setEditCompletedDate("");
      fetchAnnualReviews();
      // Rafraîchir l'employé pour mettre à jour le badge
      if (employeeId) {
        const employeeRes = await apiClient.get(`/api/employees/${employeeId}`);
        setEmployee(employeeRes.data);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erreur";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    }
  };


  const handleMarkCompleted = async (reviewId: string) => {
    try {
      await annualReviewsApi.markAsCompleted(reviewId);
      toast({ title: "Entretien marqué comme réalisé", description: "Vous pouvez maintenant remplir la fiche." });
      fetchAnnualReviews();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erreur";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    }
  };

  const handleViewPdf = async (reviewId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const blob = await annualReviewsApi.downloadAnnualReviewPdf(reviewId);
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
      // Ne pas révoquer immédiatement l'URL pour permettre l'ouverture dans un nouvel onglet
      setTimeout(() => window.URL.revokeObjectURL(url), 100);
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error?.response?.data?.detail || "Impossible d'ouvrir le PDF.",
        variant: "destructive",
      });
    }
  };

  const handleDownloadPdf = async (reviewId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const blob = await annualReviewsApi.downloadAnnualReviewPdf(reviewId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `entretien_${reviewId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast({
        title: "PDF téléchargé",
        description: "Le PDF de l'entretien a été téléchargé avec succès.",
      });
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error?.response?.data?.detail || "Impossible de télécharger le PDF.",
        variant: "destructive",
      });
    }
  };

  const fetchSaisies = useCallback(async () => {
    if (!employeeId) return;
    const { year, month } = selectedDate;
    setIsLoadingSaisies(true);
    try {
      const res = await saisiesApi.getEmployeeMonthlyInputs(employeeId, year, month);
      setEmployeeSaisies(res.data || []);
    } catch (err) {
      console.error("❌ Erreur lors du chargement des saisies :", err);
    } finally {
      setIsLoadingSaisies(false);
    }
  }, [employeeId, selectedDate.year, selectedDate.month]); // Utilisation des primitives pour les dépendances

  const handleDeleteSaisie = async (id: string) => {
    if (!window.confirm("Supprimer cette saisie ?")) return;
    try {
      await saisiesApi.deleteEmployeeMonthlyInput(employeeId!, id);
      toast({ title: "Supprimée", description: "La saisie a été supprimée." });
      fetchSaisies();
    } catch (error) {
      toast({ title: "Erreur", description: "Impossible de supprimer la saisie.", variant: "destructive" });
    }
  };

  // Charger les saisies à chaque changement de mois ou employé
  useEffect(() => {
    if (employeeId) fetchSaisies();
  }, [fetchSaisies]); // fetchSaisies est maintenant stable grâce à useCallback et ses dépendances primitives



  

  // Effet pour charger les données générales de la page (infos employé, bulletins...)
  useEffect(() => {

    if (!employeeId) return;
    const fetchPageData = async () => {
      setIsPageLoading(true);
      try {
        const [employeeRes, payslipsRes, contractRes, identityDocRes, credentialsPdfRes] = await Promise.all([
          apiClient.get(`/api/employees/${employeeId}`),
          apiClient.get(`/api/employees/${employeeId}/payslips`),
          apiClient.get(`/api/employees/${employeeId}/contract`),
          apiClient.get(`/api/employees/${employeeId}/identity-document`),
          apiClient.get(`/api/employees/${employeeId}/credentials-pdf`),
        ]);
        setEmployee(employeeRes.data);
        setPayslips(payslipsRes.data);

        // 'contractRes.data.url' EST déjà l'URL signée complète et fonctionnelle.
        // On l'utilise directement.
        if (contractRes.data.url) {
          setContractUrl(contractRes.data.url);
        } else {
          setContractUrl(null); // Gère le cas où aucun contrat n'est trouvé
        }

        // Pièce d'identité (carte d'identité, passeport ou titre de séjour)
        if (identityDocRes.data.url) {
          setIdentityDocumentUrl(identityDocRes.data.url);
        } else {
          setIdentityDocumentUrl(null);
        }

        // PDF de création de compte
        if (credentialsPdfRes.data.url) {
          setCredentialsPdfUrl(credentialsPdfRes.data.url);
        } else {
          setCredentialsPdfUrl(null);
        }

      } catch (err) {
        console.error("Erreur lors du chargement des données de la page", err);
      } finally {
        setIsPageLoading(false);
      }
    };
    fetchPageData();
  }, [employeeId]);

  const handleDeleteEmployee = async () => {
    if (!employeeId) return;
    try {
      await apiClient.delete(`/api/employees/${employeeId}`);
      toast({
        title: "Collaborateur supprimé",
        description: "Le collaborateur et son compte utilisateur ont été supprimés avec succès.",
      });
      navigate("/employees");
    } catch (error: any) {
      console.error("Erreur lors de la suppression du collaborateur", error);
      const errorMessage = error.response?.data?.detail || "Une erreur est survenue.";
      toast({ title: "Erreur de suppression", description: errorMessage, variant: "destructive" });
    }
  };


  
  // AJOUTER CETTE FONCTION
  const handleSaveSaisie = async (data: any[]) => { // Le type 'any' est temporaire pour correspondre au modal
      try {
        // Le modal envoie un tableau de payloads, un pour chaque employé sélectionné
        await saisiesApi.createMonthlyInputs(data);
        toast({ title: "Succès", description: "Saisie(s) enregistrée(s) avec succès." });
        fetchSaisies(); // Recharger la liste
      } catch (err) {
        toast({ title: "Erreur", description: "Échec de l'enregistrement.", variant: "destructive" });
      }
  };

  // --- Handler pour le rendu personnalisé des cellules ---
  // const renderDayCell = useCallback((arg: DayCellContentArg) => {
  //   // Le rendu de la cellule est maintenant dépendant de la sélection
  //   return React.cloneElement(
  //     <CalendarDayCell 
  //       arg={arg}
  //       plannedCalendar={plannedCalendar}
  //       actualHours={actualHours}
  //       updateDayData={updateDayData}
  //       selectedDate={selectedDate}
  //     />, { selectedDays, onDaySelect: handleDaySelection }
  //   );
  // }, [plannedCalendar, actualHours, updateDayData, selectedDate, selectedDays, handleDaySelection]);

  if (isPageLoading) return <div className="flex items-center justify-center h-screen"><Loader2 className="h-12 w-12 animate-spin"/></div>;
  if (!employee) return <div className="text-center p-8">Employé non trouvé.</div>;

  
  return (
    <div className="space-y-6">
      {/* --- AJOUT DE STYLE POUR FULLCALENDAR --- */}
      {/* <style>{`
        .fc-daygrid-day-frame {
          height: 100%;
        }
        .fc .fc-daygrid-day-cushion {
          padding: 0 !important;
        }
      `}</style> */}
      <Link to="/employees" className="flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste des collaborateurs
      </Link>

      <Card>
        {/* ... (CardHeader avec infos employé) ... */}
        <CardHeader className="flex flex-row items-center gap-4">
          <Avatar className="h-16 w-16"><AvatarFallback className="text-xl">{employee.first_name.charAt(0)}{employee.last_name.charAt(0)}</AvatarFallback></Avatar>
          <div>
            <CardTitle className="text-2xl">{employee.first_name} {employee.last_name}</CardTitle>
            <CardDescription>{employee.job_title}</CardDescription>
          </div>
          <div className="ml-auto flex gap-2">
            {credentialsPdfUrl && (
              <Button
                variant="outline"
                size="sm"
                asChild
                className="border-blue-500/50 text-blue-600 hover:bg-blue-50 hover:text-blue-700">
                <a
                  href={credentialsPdfUrl}
                  download={`Compte_${employee.first_name}_${employee.last_name}.pdf`}>
                  <UserPlus className="mr-2 h-4 w-4" />
                  Télécharger création de compte
                </a>
              </Button>
            )}
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-destructive/50 text-destructive hover:bg-destructive/10 hover:text-destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Supprimer le collaborateur
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Êtes-vous absolument certain ?</AlertDialogTitle>
                  <AlertDialogDescription>Cette action est irréversible. Elle supprimera définitivement le collaborateur, son compte utilisateur, et toutes les données associées (bulletins, plannings, etc.).</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Annuler</AlertDialogCancel>
                  <AlertDialogAction onClick={handleDeleteEmployee} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Confirmer la suppression</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardHeader>
        <CardContent>
            <div className="text-sm text-muted-foreground flex flex-wrap items-center gap-x-6 gap-y-2">
                <div><strong>Type de contrat:</strong> {employee.contract_type}</div>
                <div><strong>Statut:</strong> {employee.statut}</div>
                <div><strong>Date d'entrée:</strong> {new Date(employee.hire_date).toLocaleDateString('fr-FR')}</div>
                <ResidencePermitBadge 
                  data={{
                    is_subject_to_residence_permit: employee.is_subject_to_residence_permit ?? false,
                    residence_permit_status: employee.residence_permit_status ?? null,
                    residence_permit_expiry_date: employee.residence_permit_expiry_date ?? null,
                    residence_permit_days_remaining: employee.residence_permit_days_remaining ?? null,
                    residence_permit_data_complete: employee.residence_permit_data_complete ?? null,
                  }}
                />
                <div className="flex items-center gap-2 flex-shrink-0">
                  <strong>Convention collective:</strong>
                  <Select value={collectiveAgreementId ?? "__aucune__"} onValueChange={(v) => setCollectiveAgreementId(v === "__aucune__" ? null : v)}>
                    <SelectTrigger className="w-[240px]">
                      <SelectValue placeholder="Aucune" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__aucune__">Aucune</SelectItem>
                      {companyAgreements.map(a => (
                        <SelectItem key={a.id} value={a.collective_agreement_id}>
                          {a.agreement_details?.name || a.agreement_details?.idcc || 'Convention'} (IDCC {a.agreement_details?.idcc})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button size="sm" onClick={handleSaveCollectiveAgreement} disabled={isSavingCC || collectiveAgreementId === (employee.collective_agreement_id ?? null)}>
                    {isSavingCC ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  </Button>
                </div>
            </div>
        </CardContent>
      </Card>

      {/* Bloc CSE - Affiché uniquement si l'employé est élu */}
      {employeeId && <EmployeeCSEBlock employeeId={employeeId} />}
      
      <Tabs value={activeTab} onValueChange={setActiveTab} defaultValue="calendrier" className="w-full">
        <TabsList className={cn("grid w-full", medicalModuleEnabled ? "grid-cols-6" : "grid-cols-5")}>
          <TabsTrigger value="documents"><FileText className="mr-2 h-4 w-4"/>Documents</TabsTrigger>
          <TabsTrigger value="saisie"><ClipboardEdit className="mr-2 h-4 w-4"/>Saisie du mois</TabsTrigger>
          <TabsTrigger value="entretiens"><MessageSquare className="mr-2 h-4 w-4"/>Entretiens</TabsTrigger>
          <TabsTrigger value="promotions"><TrendingUp className="mr-2 h-4 w-4"/>Promotions</TabsTrigger>
          {medicalModuleEnabled && <TabsTrigger value="suivi_medical"><Stethoscope className="mr-2 h-4 w-4"/>Suivi médical</TabsTrigger>}
          <TabsTrigger value="calendrier"><CalendarIcon className="mr-2 h-4 w-4"/>Calendrier</TabsTrigger>
        </TabsList>

        {/* --- Onglet Documents : Contrat, Pièce d'Identité et Bulletins de Paie --- */}
        <TabsContent value="documents" className="mt-4 space-y-4">
          {/* Section Contrat de Travail */}
          <Card>
            <CardHeader>
              <CardTitle>Contrat de Travail</CardTitle>
            </CardHeader>
            <CardContent>
              {isPageLoading ? (
                <p className="text-sm text-muted-foreground p-3">Chargement...</p>
              ) : contractUrl ? (
                <ul className="space-y-1">
                  <li className="flex items-center justify-between p-3 rounded-md hover:bg-muted">
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-muted-foreground" />
                      <p className="font-medium">Contrat de travail.pdf</p>
                    </div>
                    <Button variant="ghost" size="icon" asChild>
                      <a 
                        href={contractUrl} 
                        download={`Contrat_${employee?.first_name}_${employee?.last_name}.pdf`}
                      >
                        <Download className="h-4 w-4" />
                      </a>
                    </Button>
                  </li>
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground p-3">Aucun fichier de contrat trouvé.</p>
              )}
            </CardContent>
          </Card>

          {/* Section Pièce d'Identité / Titre de séjour */}
          <Card>
            <CardHeader>
              <CardTitle>Pièce d'identité ou Titre de séjour</CardTitle>
            </CardHeader>
            <CardContent>
              {isPageLoading ? (
                <p className="text-sm text-muted-foreground p-3">Chargement...</p>
              ) : identityDocumentUrl ? (
                <ul className="space-y-2">
                  <li className="flex items-center justify-between p-3 rounded-md hover:bg-muted">
                    <div className="flex flex-col gap-1 flex-1">
                      <div className="flex items-center gap-3">
                        <FileText className="h-5 w-5 text-muted-foreground" />
                        <p className="font-medium">
                          {employee?.is_subject_to_residence_permit 
                            ? "Titre de séjour" 
                            : "Carte d'identité / Passeport"}
                        </p>
                      </div>
                      {employee?.is_subject_to_residence_permit && employee?.residence_permit_type && (
                        <p className="text-sm text-muted-foreground ml-8">
                          Type: {employee.residence_permit_type}
                          {employee.residence_permit_number && ` • N° ${employee.residence_permit_number}`}
                        </p>
                      )}
                      {employee?.is_subject_to_residence_permit && employee?.residence_permit_expiry_date && (
                        <p className="text-sm text-muted-foreground ml-8">
                          Expire le: {new Date(employee.residence_permit_expiry_date).toLocaleDateString('fr-FR')}
                        </p>
                      )}
                    </div>
                    <Button variant="ghost" size="icon" asChild>
                      <a 
                        href={identityDocumentUrl} 
                        download={`${employee?.is_subject_to_residence_permit ? 'Titre_sejour' : 'Piece_identite'}_${employee?.first_name}_${employee?.last_name}`}
                      >
                        <Download className="h-4 w-4" />
                      </a>
                    </Button>
                  </li>
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground p-3">
                  {employee?.is_subject_to_residence_permit 
                    ? "Aucun titre de séjour trouvé." 
                    : "Aucune pièce d'identité trouvée."}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Section Bulletins de Paie */}
          <Card>
            <CardHeader>
              <CardTitle>Bulletins de Paie</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {payslips.length > 0 ? payslips.map(p => (
                  <li key={p.id} className="flex justify-between items-center p-2 rounded-md hover:bg-muted">
                    <span className="capitalize">
                      {new Date(p.year, p.month - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' })}
                    </span>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" asChild>
                        <Link to={`/payslips/${p.id}/edit`}>
                          <Edit className="mr-2 h-4 w-4"/> Modifier
                        </Link>
                      </Button>
                      <Button variant="outline" size="sm" asChild>
                        <a href={p.url} download={p.name}><Download className="mr-2 h-4 w-4"/> Télécharger</a>
                      </Button>
                    </div>
                  </li>
                )) : <p className="text-sm text-muted-foreground">Aucun bulletin de paie trouvé.</p>}
              </ul>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="saisie" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row justify-between items-center">
              <div>
                <CardTitle>Saisies de {new Date(selectedDate.year, selectedDate.month - 1).toLocaleString("fr-FR", { month: "long" })}</CardTitle>
                <CardDescription>Primes, acomptes et autres variables pour la paie de ce mois.</CardDescription>
              </div>
              <Button onClick={() => setSaisieModalOpen(true)}>+ Ajouter une saisie</Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Montant</TableHead>
                    <TableHead>Soumis à cotisations</TableHead>
                    <TableHead>Soumis à impôt</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoadingSaisies ? (
                    <TableRow><TableCell colSpan={5} className="text-center h-24"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></TableCell></TableRow>
                  ) : employeeSaisies.length > 0 ? employeeSaisies.map((saisie) => (
                    <TableRow key={saisie.id}>
                      <TableCell className="font-medium">{saisie.name}</TableCell>
                      <TableCell>{saisie.amount.toFixed(2)} €</TableCell>
                      <TableCell>{saisie.is_socially_taxed ? 'Oui' : 'Non'}</TableCell>
                      <TableCell>{saisie.is_taxable ? 'Oui' : 'Non'}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" onClick={() => handleDeleteSaisie(saisie.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center h-24">Aucune saisie pour ce mois.</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="entretiens" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row justify-between items-center">
              <div>
                <CardTitle>Entretiens</CardTitle>
                <CardDescription>Historique et suivi des entretiens de {employee.first_name} {employee.last_name}.</CardDescription>
              </div>
              <Button onClick={() => { setPlanningDate(""); setPlanningModalOpen(true); }}>
                + Planifier un entretien
              </Button>
            </CardHeader>
            <CardContent>
              {annualReviews.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4">Aucun entretien enregistré.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead className="w-[100px]">PDF</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {annualReviews.map((r) => {
                      const displayDate = r.completed_date 
                        ? new Date(r.completed_date).toLocaleDateString("fr-FR")
                        : r.planned_date 
                        ? new Date(r.planned_date).toLocaleDateString("fr-FR")
                        : r.year;
                      
                      return (
                        <TableRow 
                          key={r.id}
                          className="cursor-pointer hover:bg-muted/50 transition-colors"
                          onClick={() => navigate(`/annual-reviews/${r.id}?returnTo=employee&employeeId=${employeeId}&tab=entretiens`)}
                        >
                          <TableCell>{displayDate}</TableCell>
                          <TableCell>
                            <AnnualReviewBadge status={r.status} compact />
                          </TableCell>
                          <TableCell onClick={(e) => e.stopPropagation()}>
                            {r.status === "cloture" ? (
                              <div className="flex items-center gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => handleViewPdf(r.id, e)}
                                  className="h-8 w-8 p-0"
                                  title="Voir le PDF"
                                >
                                  <Eye className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => handleDownloadPdf(r.id, e)}
                                  className="h-8 w-8 p-0"
                                  title="Télécharger le PDF"
                                >
                                  <FileDown className="h-4 w-4" />
                                </Button>
                              </div>
                            ) : (
                              <span className="text-muted-foreground text-xs">—</span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="promotions" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row justify-between items-center">
              <div>
                <CardTitle>Promotions</CardTitle>
                <CardDescription>
                  Historique des promotions et évolutions de carrière de {employee.first_name} {employee.last_name}.
                </CardDescription>
              </div>
              <Button onClick={() => setPromotionModalOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Nouvelle promotion
              </Button>
            </CardHeader>
            <CardContent>
              {promotions.length === 0 ? (
                <div className="text-center py-8">
                  <TrendingUp className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="text-sm text-muted-foreground mb-4">
                    Aucune promotion enregistrée.
                  </p>
                  <Button onClick={() => setPromotionModalOpen(true)} variant="outline">
                    <Plus className="mr-2 h-4 w-4" />
                    Créer une promotion
                  </Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Évolution</TableHead>
                      <TableHead>Date d'effet</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead className="w-[100px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {promotions.map((promo) => {
                      const evolutionText = [
                        promo.new_job_title,
                        promo.new_salary
                          ? `${promo.new_salary.valeur.toLocaleString("fr-FR")} ${promo.new_salary.devise || "EUR"}`
                          : null,
                        promo.new_statut,
                      ]
                        .filter(Boolean)
                        .join(" • ") || "—";

                      return (
                        <TableRow
                          key={promo.id}
                          className="cursor-pointer hover:bg-muted/50 transition-colors"
                          onClick={() =>
                            navigate(
                              `/promotions/${promo.id}?returnTo=employee&employeeId=${employeeId}&tab=promotions`
                            )
                          }
                        >
                          <TableCell>
                            <PromotionBadge
                              type={promo.promotion_type}
                              variant="type"
                              compact
                            />
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {evolutionText}
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {new Date(promo.effective_date).toLocaleDateString("fr-FR", {
                              day: "2-digit",
                              month: "short",
                              year: "numeric",
                            })}
                          </TableCell>
                          <TableCell>
                            <PromotionBadge status={promo.status} compact />
                          </TableCell>
                          <TableCell onClick={(e) => e.stopPropagation()}>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                navigate(
                                  `/promotions/${promo.id}?returnTo=employee&employeeId=${employeeId}&tab=promotions`
                                )
                              }
                              className="h-8 w-8 p-0"
                              title="Voir les détails"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {medicalModuleEnabled && (
        <TabsContent value="suivi_medical" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Stethoscope className="h-5 w-5 text-teal-600" /> Suivi médical</CardTitle>
              <CardDescription>Prochaine obligation et historique des visites médicales.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {medicalObligations.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune obligation de suivi médical pour le moment.</p>
              ) : (
                <>
                  <div>
                    <h4 className="text-sm font-medium mb-2">Prochaine obligation</h4>
                    {(() => {
                      const next = medicalObligations.find((o) => o.status !== "realisee");
                      if (!next) {
                        return <p className="text-sm text-muted-foreground">Toutes les obligations sont réalisées.</p>;
                      }
                      const typeLabel = { aptitude_sir_avant_affectation: "Aptitude SIR", vip_avant_affectation_mineur_nuit: "VIP avant affectation", reprise: "Reprise", vip: "VIP", sir: "SIR", mi_carriere_45: "Mi-carrière 45 ans", demande: "À la demande" }[next.visit_type] ?? next.visit_type;
                      const statusLabel = { a_faire: "À faire", planifiee: "Planifiée", realisee: "Réalisée", annulee: "Annulée" }[next.status] ?? next.status;
                      const isOverdue = next.due_date && new Date(next.due_date) < new Date() && next.status !== "realisee";
                      return (
                        <div className={cn("rounded-lg border p-4", isOverdue && "border-red-500 bg-red-500/5")}>
                          <div className="flex justify-between items-start">
                            <div>
                              <p className="font-medium">{typeLabel}</p>
                              <p className="text-sm text-muted-foreground">Date limite : {next.due_date ? new Date(next.due_date).toLocaleDateString("fr-FR") : "—"}</p>
                              <p className="text-sm">Statut : {statusLabel}</p>
                              {next.justification && <p className="text-sm text-muted-foreground mt-1">{next.justification}</p>}
                            </div>
                            {isOverdue && <span className="text-xs font-medium text-red-600 bg-red-100 px-2 py-1 rounded">En retard</span>}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                  <div>
                    <h4 className="text-sm font-medium mb-2">Historique</h4>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Type</TableHead>
                          <TableHead>Date limite</TableHead>
                          <TableHead>Statut</TableHead>
                          <TableHead>Planifiée</TableHead>
                          <TableHead>Réalisée</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {medicalObligations.map((o) => {
                          const typeLabel = { aptitude_sir_avant_affectation: "Aptitude SIR", vip_avant_affectation_mineur_nuit: "VIP avant affectation", reprise: "Reprise", vip: "VIP", sir: "SIR", mi_carriere_45: "Mi-carrière 45 ans", demande: "À la demande" }[o.visit_type] ?? o.visit_type;
                          const statusLabel = { a_faire: "À faire", planifiee: "Planifiée", realisee: "Réalisée", annulee: "Annulée" }[o.status] ?? o.status;
                          return (
                            <TableRow key={o.id}>
                              <TableCell>{typeLabel}</TableCell>
                              <TableCell>{o.due_date ? new Date(o.due_date).toLocaleDateString("fr-FR") : "—"}</TableCell>
                              <TableCell>{statusLabel}</TableCell>
                              <TableCell>{o.planned_date ? new Date(o.planned_date).toLocaleDateString("fr-FR") : "—"}</TableCell>
                              <TableCell>{o.completed_date ? new Date(o.completed_date).toLocaleDateString("fr-FR") : "—"}</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        )}

        <TabsContent value="calendrier" className="mt-4">
          <Card className="mt-3">
             <CardHeader className="flex flex-row justify-between items-center">
                <div className="flex items-center gap-4">
                  <div>
                    <CardTitle className="text-xl font-semibold text-foreground">
                      Calendrier de {employee.first_name} {employee.last_name}
                    </CardTitle>

                    <CardDescription className="flex items-center gap-3 mt-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-gray-600 hover:text-primary transition"
                        onClick={() => {
                          if (calendarView === 'month') {
                            const newMonth = selectedDate.month === 1 ? 12 : selectedDate.month - 1;
                            const newYear = selectedDate.month === 1 ? selectedDate.year - 1 : selectedDate.year;
                            setSelectedDate({ month: newMonth, year: newYear });
                          } else {
                            setSelectedDate({ month: selectedDate.month, year: selectedDate.year - 1 });
                          }
                        }}
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
                        onClick={() => {
                          if (calendarView === 'month') {
                            const newMonth = selectedDate.month === 12 ? 1 : selectedDate.month + 1;
                            const newYear = selectedDate.month === 12 ? selectedDate.year + 1 : selectedDate.year;
                            setSelectedDate({ month: newMonth, year: newYear });
                          } else {
                            setSelectedDate({ month: selectedDate.month, year: selectedDate.year + 1 });
                          }
                        }}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </CardDescription>

                  </div>

                  {/* ✅ NOUVEAU : Toggle pour basculer entre vue mensuelle et annuelle (calendrier) */}
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
                    <ToggleGroupItem value="year" aria-label="Vue annuelle (calendrier)" className="gap-2">
                      <Grid3x3 className="h-4 w-4" />
                      <span className="hidden sm:inline">Année</span>
                    </ToggleGroupItem>
                  </ToggleGroup>
                </div>

                {/* ✅ MODIFIÉ : Le bouton principal, avec la parenthèse manquante corrigée */}
                <Button
                  onClick={saveAllCalendarData}
                  disabled={isSaving || !isDirty}
                  className={cn(
                    "transition-all",
                    "bg-green-600 text-white", // Couleur de base verte
                    // Le hover ne s'applique que si le bouton est actif (dirty)
                    isDirty && !isSaving ? "hover:bg-green-700" : "",
                    // L'état 'disabled' (géré par shadcn) ajoutera automatiquement
                    // l'opacité pour les états "Enregistré" et "Enregistrement..."
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
             {calendarView === 'month' && (
               <CardDescription className="mt-1 ml-6 text-sm text-muted-foreground">
                  Cliquez sur un jour pour éditer le planning et les heures réalisées.
                </CardDescription>
             )}


             <CardContent className="p-0 md:p-2 pb-48">
                {/* ✅ MODIFIÉ : On passe les nouvelles props à WeekTemplateForm - uniquement en vue mensuelle */}
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
                {isCalendarLoading ? <div className="flex h-full items-center justify-center"><Loader2 className="h-8 w-8 animate-spin" /></div> : (
                  <>
                    {calendarView === 'month' ? (
                      <div className="flex flex-col gap-4 p-2">
                    {/* Noms des jours */}
                    <div className="grid grid-cols-7 text-center text-sm font-medium text-muted-foreground">
                      {["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].map((d) => (
                        <div key={d}>{d}</div>
                      ))}
                    </div>

                    {/* Cases des jours */}
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
                        employeeId={employeeId!}
                      />
                    )}
                  </>
                )}
             </CardContent>
           </Card>
        </TabsContent>
      </Tabs>

      {/* ✅ MODIFIÉ : On passe les nouvelles props à BulkActionPanel */}
      {selectedDays.length > 0 && (
        <BulkActionPanel
          selectedCount={selectedDays.length}
          onBulkUpdate={bulkUpdateDays}
          updateSelection={updateSelection}
          onBulkUpdateAndSave={bulkUpdateDaysAndSave}
          isSaving={isSaving}
          isForfaitJour={isForfaitJour}
        />
      )}

      <Dialog open={planningModalOpen} onOpenChange={setPlanningModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Planifier un entretien</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Date prévue</Label>
              <Input type="date" value={planningDate} onChange={(e) => setPlanningDate(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPlanningModalOpen(false)}>Annuler</Button>
            <Button onClick={handlePlanAnnualReview}>Planifier</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editingReview !== null} onOpenChange={(open) => !open && setEditingReview(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Modifier l'entretien</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Statut</Label>
              <Select value={editStatus} onValueChange={setEditStatus}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="planifie">Planifié</SelectItem>
                  <SelectItem value="en_attente_acceptation">En attente d'acceptation</SelectItem>
                  <SelectItem value="accepte">Accepté</SelectItem>
                  <SelectItem value="refuse">Refusé</SelectItem>
                  <SelectItem value="realise">Réalisé</SelectItem>
                  <SelectItem value="cloture">Clôturé</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Date prévue</Label>
              <Input type="date" value={editPlannedDate} onChange={(e) => setEditPlannedDate(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Date réalisée</Label>
              <Input type="date" value={editCompletedDate} onChange={(e) => setEditCompletedDate(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingReview(null)}>Annuler</Button>
            <Button onClick={handleUpdateReview}>Enregistrer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <SaisieModal
        isOpen={saisieModalOpen}
        onClose={() => setSaisieModalOpen(false)}
        onSave={handleSaveSaisie}
        employees={employee ? [employee] : []} // Le modal attend un tableau d'employés
        employeeScopeId={employee?.id} // On spécifie que le scope est cet employé
      />

      {/* Modal de promotion */}
      <PromotionModal
        isOpen={promotionModalOpen}
        onClose={() => setPromotionModalOpen(false)}
        promotion={null}
        initialEmployeeId={employeeId}
        onSuccess={() => {
          fetchPromotions();
          setPromotionModalOpen(false);
        }}
      />

    </div>
  );
}