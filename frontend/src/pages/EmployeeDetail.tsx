// src/pages/EmployeeDetail.tsx 

import { log } from '@/lib/logger';
import React, { useCallback, useState, useEffect, useRef, useMemo } from "react";
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
import { Download, Calendar as CalendarIcon, FileText, Loader2, ArrowLeft, Save, ClipboardEdit, ChevronLeft, ChevronRight, UserPlus, Grid3x3, CalendarDays, Edit, MessageSquare, Play, CheckCircle, FileText as FileTextIcon, FileDown, Eye, TrendingUp, Plus, Trash2, ArrowRight, Stethoscope, Calculator, Copy, Award, ClipboardList, ScanLine } from "lucide-react";
import { EmployeeDetailBadgeuseSection } from "@/components/badgeuse/rh/EmployeeDetailBadgeuseSection";
import { isRecentHire } from "@/lib/onboardingUtils";
import { CalendarKpiBand } from "@/components/employee-detail/CalendarKpiBand";
import { CalendarAbsencesHint } from "@/components/employee-detail/CalendarAbsencesHint";
import { computeMonthStats } from "@/lib/calendarStats";
import {
  loadSavedWeekTemplates,
  saveWeekTemplate,
  type SavedWeekTemplate,
} from "@/lib/weekTemplateStorage";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"; // prettier-ignore
import * as saisiesApi from "@/api/saisies"; // ✅ On importe le nouveau type
import { useCalendar, WeekTemplate } from "@/hooks/useCalendar"; // ✅ On importe le nouveau type
import { Input } from "@/components/ui/input"; // ✅ On importe l'Input
import { Label } from "@/components/ui/label";   // ✅ On importe le Label
import { Checkbox } from "@/components/ui/checkbox"; // ✅ On importe Checkbox pour le mode forfait jour
import { isForfaitJour } from '@/utils/employeeUtils';
import { toast } from "@/components/ui/use-toast";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ResidencePermitBadge } from "@/components/ResidencePermitBadge";
import {
  EmployeeDetailAnnualReviewsTab,
  annualReviewsEmployeeQueryKey,
} from "@/components/employee-detail/EmployeeDetailAnnualReviewsTab";
import { getEmployeeAnnualReviews } from "@/api/annualReviews";
import { hasAnnualReviewTabAlert } from "@/lib/annualReviewLabels";
import * as collectiveAgreementsApi from "@/api/collectiveAgreements";
import { PromotionModal } from "@/components/PromotionModal";
import { PromotionBadge } from "@/components/PromotionBadge";
import { EmployeeCSEBlock } from "@/components/EmployeeCSEBlock";
import { getEmployeePromotions } from "@/api/promotions";
import type { PromotionListItem } from "@/api/promotions";
import { getMedicalSettings, getObligationsForEmployee } from "@/api/medicalFollowUp";
import {
  EmployeeDetailMedicalTab,
  medicalEmployeeQueryKey,
} from "@/components/employee-detail/EmployeeDetailMedicalTab";
import { hasMedicalOverdue } from "@/lib/medicalFollowUpLabels";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assignEmployeeTeam, getTeams } from "@/api/teams";
import { generateDocument } from "@/api/documents";
import { DOCUMENT_TYPE_LABELS, getTemplates, type DocumentTemplate } from "@/api/documentLibrary";
import { EmployeeDetailDocumentsTab } from "@/components/employee-detail/EmployeeDetailDocumentsTab";
import {
  diffWatchedSnapshots,
  extractWatchedSnapshot,
  resolveAvenantTypeFromDiffs,
  type ContractualFieldDiff,
} from "@/utils/employeeContractualWatch";
import { useCompany } from "@/contexts/CompanyContext";
import { useAuth } from "@/contexts/AuthContext";
import {
  appliquerAugmentation,
  getSalaryHistory,
  simulerAugmentation,
  type SimulationResultat,
} from "@/api/augmentations";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";

const TAB_AUGMENTATIONS_PROMOTIONS = "augmentations-promotions";

function normalizeEmployeeDetailTab(tabParam: string | null | undefined, fallback = "documents"): string {
  const tab = tabParam ?? fallback;
  if (tab === "bulletins") return "documents";
  if (tab === "augmentation" || tab === "promotions") return TAB_AUGMENTATIONS_PROMOTIONS;
  if (tab === "suivi_medical" || tab === "suivi-medical" || tab === "medical") return "suivi_medical";
  return tab;
}

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
  college_electoral?: string | null;
  statut_cse?: string | null;
  heures_delegation_mensuelles?: number | null;
  salaire_de_base?: unknown;
  duree_hebdomadaire?: unknown;
  lieu_travail?: unknown;
  workplace?: unknown;
  poste?: string | null;
  weekly_hours?: unknown;
  team_id?: string | null;
}
function formatEuroAmount(n: number): string {
  return `${n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function formatDateFR(iso: string): string {
  if (!iso) return "";
  const d = iso.includes("T") ? new Date(iso) : new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("fr-FR");
}

function valeurSalaireBrut(obj: unknown): number {
  if (obj && typeof obj === "object" && obj !== null && "valeur" in obj) {
    const v = (obj as { valeur: unknown }).valeur;
    if (typeof v === "number" && !Number.isNaN(v)) return v;
    if (typeof v === "string") {
      const p = parseFloat(v.replace(",", "."));
      return Number.isNaN(p) ? 0 : p;
    }
  }
  return 0;
}

// ✅ MODIFIÉ : Le formulaire pour le modèle de semaine
// -----------------------------------------------------------------------------
interface WeekTemplateFormProps {
  template: WeekTemplate;
  setTemplate: React.Dispatch<React.SetStateAction<WeekTemplate>>;
  onApply: () => void;
  onApplyAndSave: () => void;
  onCopyPreviousMonth: () => void;
  isSaving: boolean;
  isCopyingPrevMonth?: boolean;
  isForfaitJour?: boolean;
  companyId: string;
  daysInMonth: number;
}

function WeekTemplateForm({
  template,
  setTemplate,
  onApply,
  onApplyAndSave,
  onCopyPreviousMonth,
  isSaving,
  isCopyingPrevMonth = false,
  isForfaitJour = false,
  companyId,
  daysInMonth,
}: WeekTemplateFormProps) {
  const [savedTemplates, setSavedTemplates] = useState<SavedWeekTemplate[]>(() =>
    loadSavedWeekTemplates(companyId)
  );
  const [saveTemplateName, setSaveTemplateName] = useState("");

  useEffect(() => {
    setSavedTemplates(loadSavedWeekTemplates(companyId));
  }, [companyId]);
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
        
        <div className="flex flex-col gap-2 w-full md:w-auto mt-4 md:mt-0">
          <Button onClick={onApply} disabled={isSaving} className="w-full">
            <ArrowRight className="mr-2 h-4 w-4" />
            Appliquer au mois
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" disabled={isSaving} className="w-full">
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                Appliquer et enregistrer
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Appliquer le modèle et enregistrer ?</AlertDialogTitle>
                <AlertDialogDescription>
                  Cela écrasera les valeurs prévues des jours ouvrés du mois ({daysInMonth} jours)
                  et lancera immédiatement l&apos;enregistrement et le calcul paie.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Annuler</AlertDialogCancel>
                <AlertDialogAction onClick={onApplyAndSave}>Confirmer</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button
            variant="secondary"
            onClick={onCopyPreviousMonth}
            disabled={isSaving || isCopyingPrevMonth}
            className="w-full"
          >
            {isCopyingPrevMonth ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Copy className="mr-2 h-4 w-4" />
            )}
            Copier le mois précédent
          </Button>
        </div>
      </CardContent>
      <CardContent className="pt-0 border-t">
        <div className="flex flex-wrap items-end gap-2">
          {savedTemplates.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {savedTemplates.map((st) => (
                <Button
                  key={st.name}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => setTemplate(st.template)}
                >
                  {st.name}
                </Button>
              ))}
            </div>
          )}
          <Input
            className="h-8 w-36 text-xs"
            placeholder="Nom du modèle"
            value={saveTemplateName}
            onChange={(e) => setSaveTemplateName(e.target.value)}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 text-xs"
            disabled={!saveTemplateName.trim()}
            onClick={() => {
              setSavedTemplates(saveWeekTemplate(companyId, saveTemplateName, template));
              setSaveTemplateName("");
              toast({ title: "Modèle enregistré", description: "Jusqu'à 3 modèles par société." });
            }}
          >
            Mémoriser
          </Button>
        </div>
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
  onBulkCopyPlannedToActual: () => void;
  isSaving: boolean;
  isForfaitJour?: boolean;
}

function buildBulkPreview(
  selectedCount: number,
  type: string,
  plannedHours: string,
  actualHours: string,
  actualHoursForfaitJour: string,
  isForfaitJour: boolean
): string {
  const parts: string[] = [`${selectedCount} jour${selectedCount > 1 ? 's' : ''}`];
  if (type) parts.push(`Type → ${type}`);
  if (isForfaitJour) {
    if (plannedHours) parts.push(`J. prévus → ${plannedHours === '1' ? 'oui' : 'non'}`);
    if (actualHoursForfaitJour)
      parts.push(`J. travaillés → ${actualHoursForfaitJour === '1' ? 'oui' : 'non'}`);
  } else {
    if (plannedHours) parts.push(`H. prévues → ${plannedHours}`);
    if (actualHours) parts.push(`H. faites → ${actualHours}`);
  }
  return parts.join(' • ');
}

function BulkActionPanel({
  selectedCount,
  onBulkUpdate,
  updateSelection,
  onBulkUpdateAndSave,
  onBulkCopyPlannedToActual,
  isSaving,
  isForfaitJour = false,
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

  const preview = buildBulkPreview(
    selectedCount,
    type,
    plannedHours,
    actualHours,
    actualHoursForfaitJour,
    isForfaitJour
  );

  const hasFieldChanges =
    Boolean(type) ||
    (isForfaitJour ? Boolean(plannedHours || actualHoursForfaitJour) : Boolean(plannedHours || actualHours));

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-card p-3 border rounded-lg shadow-2xl flex flex-col gap-2 max-w-[95vw] animate-in fade-in-90 slide-in-from-bottom-10">
      <p className="text-xs text-muted-foreground px-1">{preview}</p>
      <div className="flex flex-wrap items-center gap-3">
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
          </SelectContent>
        </Select>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 text-xs"
          onClick={() => {
            setType("conge");
            setPlannedHours(isForfaitJour ? "0" : "0");
          }}
        >
          Tout congé
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 text-xs"
          onClick={() => {
            setType("travail");
            setPlannedHours(isForfaitJour ? "1" : "8");
          }}
        >
          {isForfaitJour ? "Tout travail" : "Travail 8 h"}
        </Button>
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
        type="button"
        size="sm"
        variant="secondary"
        onClick={onBulkCopyPlannedToActual}
        disabled={isSaving}
      >
        <Copy className="mr-1 h-3.5 w-3.5" />
        Prévu → réel
      </Button>
      <Button
        size="sm"
        onClick={() => buildUpdateDataAndCall(onBulkUpdate)}
        disabled={isSaving || !hasFieldChanges}
      >
        Appliquer
      </Button>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button size="sm" variant="outline" disabled={isSaving || !hasFieldChanges}>
            {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Appliquer et enregistrer
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Modifier {selectedCount} jours et enregistrer ?</AlertDialogTitle>
            <AlertDialogDescription>{preview}. L&apos;enregistrement lancera le calcul paie.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={() => buildUpdateDataAndCall(onBulkUpdateAndSave)}>
              Confirmer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <Button size="sm" variant="ghost" onClick={() => updateSelection('none')} disabled={isSaving}>
        Annuler
      </Button>
      </div>
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
  isForfaitJour?: boolean;
  onMonthClick?: (month: number) => void;
}

function YearCalendarView({
  year,
  employeeId,
  isForfaitJour = false,
  onMonthClick,
}: YearCalendarViewProps) {
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
        log.error("Erreur lors du chargement des données annuelles (calendrier)", error);
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

    const monthStats = computeMonthStats(monthData.planned, monthData.actual, isForfaitJour);

    return (
      <Card
        key={monthIndex}
        className={cn(
          "p-3 transition-colors",
          onMonthClick && "cursor-pointer hover:border-primary/50 hover:shadow-md"
        )}
        role={onMonthClick ? "button" : undefined}
        tabIndex={onMonthClick ? 0 : undefined}
        onClick={() => onMonthClick?.(month)}
        onKeyDown={(e) => {
          if (onMonthClick && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            onMonthClick(month);
          }
        }}
      >
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
        <p className="mt-2 text-[10px] text-center text-muted-foreground leading-snug">
          Travail : {monthStats.joursTravailles} j • Congés : {monthStats.conges} j • Arrêt : {monthStats.arrets} j
          {!isForfaitJour && (
            <>
              <br />
              {monthStats.heuresPrevues.toFixed(0)} h prév. / {monthStats.heuresFaites.toFixed(0)} h faites
            </>
          )}
        </p>
      </Card>
    );
  };

  const yearTotals = useMemo(() => {
    let heuresPrevues = 0;
    let heuresFaites = 0;
    let conges = 0;
    let arrets = 0;
    let feriels = 0;

    Object.values(yearData).forEach((monthData) => {
      const stats = computeMonthStats(monthData.planned, monthData.actual, isForfaitJour);
      heuresPrevues += stats.heuresPrevues;
      heuresFaites += stats.heuresFaites;
      conges += stats.conges;
      arrets += stats.arrets;
      feriels += stats.feriels;
    });

    return {
      heuresPrevues,
      heuresFaites,
      ecart: heuresFaites - heuresPrevues,
      conges,
      arrets,
      feriels,
    };
  }, [yearData, isForfaitJour]);

  if (isLoadingYear) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-12 w-12 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <Card className="p-4">
        <CardTitle className="text-sm font-semibold mb-2">Synthèse {year}</CardTitle>
        <div className="flex flex-wrap gap-4 text-sm">
          {isForfaitJour ? (
            <>
              <span>
                <span className="text-muted-foreground">Jours prévus (année) :</span>{' '}
                <strong>{Object.values(yearData).reduce((a, m) => a + computeMonthStats(m.planned, m.actual, true).joursPrevus, 0)}</strong>
              </span>
              <span>
                <span className="text-muted-foreground">Jours travaillés :</span>{' '}
                <strong>{Object.values(yearData).reduce((a, m) => a + computeMonthStats(m.planned, m.actual, true).joursTravaillesForfait, 0)}</strong>
              </span>
            </>
          ) : (
            <>
              <span>
                <span className="text-muted-foreground">H. prévues :</span>{' '}
                <strong>{yearTotals.heuresPrevues.toFixed(1)} h</strong>
              </span>
              <span>
                <span className="text-muted-foreground">H. faites :</span>{' '}
                <strong>{yearTotals.heuresFaites.toFixed(1)} h</strong>
              </span>
              <span>
                <span className="text-muted-foreground">Écart :</span>{' '}
                <strong className={yearTotals.ecart < 0 ? 'text-destructive' : ''}>
                  {yearTotals.ecart >= 0 ? '+' : ''}
                  {yearTotals.ecart.toFixed(1)} h
                </strong>
              </span>
            </>
          )}
          <span>
            <span className="text-muted-foreground">Congés :</span> <strong>{yearTotals.conges} j</strong>
          </span>
          <span>
            <span className="text-muted-foreground">Arrêts :</span> <strong>{yearTotals.arrets} j</strong>
          </span>
          <span>
            <span className="text-muted-foreground">Fériés :</span> <strong>{yearTotals.feriels} j</strong>
          </span>
        </div>
      </Card>

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
    monthCompletionStatus,
    copyPreviousMonthPlanned,
    copyPlannedToActualForDay,
    bulkCopyPlannedToActual,
    isCopyingPrevMonth,
  } = useCalendar(employeeId, employeeStatut);
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
    return normalizeEmployeeDetailTab(params.get("tab"));
  });

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get("tab");
    if (tabParam) {
      setActiveTab(normalizeEmployeeDetailTab(tabParam));
    }
  }, [location.search]);

  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";
  const { user } = useAuth();
  const showEmployeeCSEBlock =
    user?.role === "rh" || user?.role === "admin" || user?.role === "collaborateur_rh";
  const canDeleteReview =
    user?.role === "rh" || user?.role === "admin" || user?.role === "collaborateur_rh";

  const [augSimType, setAugSimType] = useState<"pourcentage" | "montant_fixe">("pourcentage");
  const [augValeur, setAugValeur] = useState("");
  const [augEffectiveDate, setAugEffectiveDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [augSimLoading, setAugSimLoading] = useState(false);
  const [augSimResult, setAugSimResult] = useState<SimulationResultat | null>(null);
  const [augApplyDialogOpen, setAugApplyDialogOpen] = useState(false);
  const [augApplyMotif, setAugApplyMotif] = useState("");
  const [augApplySubmitting, setAugApplySubmitting] = useState(false);
  const [augGenDraft, setAugGenDraft] = useState<{
    nouveau_brut: number;
    effective_date: string;
    motif: string;
  } | null>(null);
  const [augGenDialogOpen, setAugGenDialogOpen] = useState(false);
  const [augGenDateInput, setAugGenDateInput] = useState("");
  const [augGenMotifInput, setAugGenMotifInput] = useState("");

  const salaryHistoryQuery = useQuery({
    queryKey: ["salary-history", employeeId, activeCompanyId],
    queryFn: () => getSalaryHistory(employeeId!, activeCompanyId),
    enabled: Boolean(
      employeeId && activeCompanyId && activeTab === TAB_AUGMENTATIONS_PROMOTIONS,
    ),
  });

  const [companyAgreements, setCompanyAgreements] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]>([]);
  const [collectiveAgreementId, setCollectiveAgreementId] = useState<string | null>(null);
  const [isSavingCC, setIsSavingCC] = useState(false);

  const [draftTeamId, setDraftTeamId] = useState<string>("__none__");
  const [savingTeam, setSavingTeam] = useState(false);

  const teamsActiveQuery = useQuery({
    queryKey: ["teams-active"],
    queryFn: () => getTeams(false),
    enabled: Boolean(employeeId),
  });
  const activeTeamsSorted = useMemo(
    () =>
      [...(teamsActiveQuery.data?.teams ?? [])].sort((a, b) =>
        a.name.localeCompare(b.name, "fr", { sensitivity: "base" }),
      ),
    [teamsActiveQuery.data?.teams],
  );
  const queryClient = useQueryClient();
  const contractualBaselineSeededRef = useRef(false);
  const contractualInitialWatchRef = useRef<ReturnType<typeof extractWatchedSnapshot> | null>(null);
  const [contractualOpen, setContractualOpen] = useState(false);
  const [contractualDiffs, setContractualDiffs] = useState<ContractualFieldDiff[]>([]);
  const [contractualAvenantType, setContractualAvenantType] = useState("avenant_general");
  const [contractualTemplate, setContractualTemplate] = useState("__eywai__");
  const [contractualDateEffet, setContractualDateEffet] = useState("");
  const [contractualMotifExtra, setContractualMotifExtra] = useState("");

  useEffect(() => {
    contractualBaselineSeededRef.current = false;
    contractualInitialWatchRef.current = null;
  }, [employeeId]);

  useEffect(() => {
    if (employee?.team_id) setDraftTeamId(employee.team_id);
    else setDraftTeamId("__none__");
  }, [employee?.team_id]);

  const savedTeamSelectValue = employee?.team_id ? employee.team_id : "__none__";
  const teamAssignmentDirty = draftTeamId !== savedTeamSelectValue;

  useEffect(() => {
    if (!employee || contractualBaselineSeededRef.current) return;
    contractualInitialWatchRef.current = extractWatchedSnapshot(
      employee as unknown as Record<string, unknown>,
    );
    contractualBaselineSeededRef.current = true;
  }, [employee, employeeId]);

  const resetContractualBaselineFromEmployee = useCallback((emp: Employee) => {
    contractualInitialWatchRef.current = extractWatchedSnapshot(
      emp as unknown as Record<string, unknown>,
    );
  }, []);

  const evaluateContractualAfterPersist = useCallback((nextEmployee: Employee) => {
    if (!contractualInitialWatchRef.current) return;
    const cur = extractWatchedSnapshot(nextEmployee as unknown as Record<string, unknown>);
    const diffs = diffWatchedSnapshots(contractualInitialWatchRef.current, cur);
    if (diffs.length === 0) return;
    setContractualDiffs(diffs);
    setContractualAvenantType(resolveAvenantTypeFromDiffs(diffs));
    setContractualTemplate("__eywai__");
    setContractualDateEffet("");
    setContractualMotifExtra("");
    setContractualOpen(true);
  }, []);

  const contractualGenMut = useMutation({
    mutationFn: generateDocument,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ["employee-generated-documents", employeeId] });
      setContractualOpen(false);
      setContractualDiffs([]);
      if (employeeId) {
        try {
          const r = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
          setEmployee(r.data);
          resetContractualBaselineFromEmployee(r.data);
        } catch {
          if (employee) resetContractualBaselineFromEmployee(employee);
        }
      }
      toast({ title: "Avenant généré", description: "Le document a été ajouté à la liste." });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Échec",
        description: typeof msg === "string" ? msg : "Génération impossible.",
        variant: "destructive",
      });
    },
  });

  const augSalariatGenMut = useMutation({
    mutationFn: generateDocument,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ["employee-generated-documents", employeeId] });
      setAugGenDialogOpen(false);
      setAugGenDraft(null);
      toast({
        title: "Avenant salaire généré",
        description: "Le PDF est disponible dans l’onglet Documents.",
      });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Échec",
        description: typeof msg === "string" ? msg : "Génération impossible.",
        variant: "destructive",
      });
    },
  });

  const { data: contractualLibTemplates = [] } = useQuery({
    queryKey: ["document-library", "templates", "active", contractualAvenantType, contractualOpen],
    queryFn: () => getTemplates("active"),
    enabled: contractualOpen && !!contractualAvenantType,
  });

  const contractualTemplatesForType = useMemo(
    () =>
      contractualLibTemplates.filter(
        (t: DocumentTemplate) => t.document_type === contractualAvenantType && t.status === "active"
      ),
    [contractualLibTemplates, contractualAvenantType]
  );

  // Promotions
  const [promotions, setPromotions] = useState<PromotionListItem[]>([]);
  const [promotionsLoading, setPromotionsLoading] = useState(false);
  const [promotionModalOpen, setPromotionModalOpen] = useState(false);

  // Suivi médical (module optionnel)
  const medicalSettingsQuery = useQuery({
    queryKey: ["medical-follow-up", "settings", "employee-detail"],
    queryFn: getMedicalSettings,
  });
  const medicalModuleEnabled = medicalSettingsQuery.data?.enabled === true;

  const medicalTabBadgeQuery = useQuery({
    queryKey: employeeId ? medicalEmployeeQueryKey(employeeId) : ["medical-follow-up", "employee", "none"],
    queryFn: () => getObligationsForEmployee(employeeId!),
    enabled: medicalModuleEnabled && !!employeeId,
    staleTime: 60_000,
  });
  const medicalTabHasOverdue = hasMedicalOverdue(medicalTabBadgeQuery.data ?? []);

  const annualReviewsTabBadgeQuery = useQuery({
    queryKey: employeeId ? annualReviewsEmployeeQueryKey(employeeId) : ["annual-reviews", "employee", "none"],
    queryFn: async () => {
      const res = await getEmployeeAnnualReviews(employeeId!);
      return res.data ?? [];
    },
    enabled: !!employeeId,
    staleTime: 60_000,
  });
  const annualReviewTabHasAlert = hasAnnualReviewTabAlert(annualReviewsTabBadgeQuery.data ?? []);

  const refreshEmployeeSnapshot = useCallback(async () => {
    if (!employeeId) return;
    const employeeRes = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
    setEmployee(employeeRes.data);
    evaluateContractualAfterPersist(employeeRes.data);
  }, [employeeId, evaluateContractualAfterPersist]);

  // Charger les promotions de l'employé
  const fetchPromotions = useCallback(async () => {
    if (!employeeId) return;
    setPromotionsLoading(true);
    try {
      const res = await getEmployeePromotions(employeeId);
      setPromotions(res.data || []);
    } catch (err) {
      log.error("Erreur chargement promotions", err);
      setPromotions([]);
    } finally {
      setPromotionsLoading(false);
    }
  }, [employeeId]);

  useEffect(() => {
    if (employeeId) fetchPromotions();
  }, [employeeId, fetchPromotions]);

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
      const employeeRes = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
      setEmployee(employeeRes.data);
      evaluateContractualAfterPersist(employeeRes.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erreur";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    } finally {
      setIsSavingCC(false);
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
      log.error("❌ Erreur lors du chargement des saisies :", err);
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
      setEmployee(null);
      setCredentialsPdfUrl(null);
      try {
        const employeeRes = await apiClient.get(`/api/employees/${employeeId}`);
        setEmployee(employeeRes.data);

        try {
          const credentialsPdfRes = await apiClient.get(
            `/api/employees/${employeeId}/credentials-pdf`,
          );
          setCredentialsPdfUrl(credentialsPdfRes.data.url ?? null);
        } catch (credErr) {
          log.error("Erreur lors du chargement du PDF de création de compte", credErr);
          setCredentialsPdfUrl(null);
        }
      } catch (err) {
        log.error("Erreur lors du chargement des données de la page", err);
        setEmployee(null);
      } finally {
        setIsPageLoading(false);
      }
    };
    fetchPageData();
  }, [employeeId]);

  const handleSimulateAugmentation = async () => {
    if (!employeeId || !activeCompanyId) {
      toast({ title: "Entreprise active requise", variant: "destructive" });
      return;
    }
    const v = parseFloat(augValeur.replace(",", "."));
    if (Number.isNaN(v) || v <= 0) {
      toast({ title: "Saisissez une valeur positive.", variant: "destructive" });
      return;
    }
    setAugSimLoading(true);
    try {
      const res = await simulerAugmentation(employeeId, activeCompanyId, {
        type_augmentation: augSimType,
        valeur: v,
        effective_date: augEffectiveDate,
      });
      setAugSimResult(res);
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Simulation impossible",
        description: typeof msg === "string" ? msg : "Réessayez plus tard.",
        variant: "destructive",
      });
    } finally {
      setAugSimLoading(false);
    }
  };

  const handleApplyAugmentationConfirm = async () => {
    if (!employeeId || !activeCompanyId || !augSimResult) return;
    const snapshot = {
      nouveau_brut: augSimResult.nouveau_salaire_brut,
      effective_date: augEffectiveDate,
      motif: augApplyMotif.trim(),
    };
    setAugApplySubmitting(true);
    try {
      await appliquerAugmentation(employeeId, activeCompanyId, {
        nouveau_salaire: augSimResult.nouveau_salaire_brut,
        motif: augApplyMotif.trim() || undefined,
        effective_date: augEffectiveDate,
      });
      toast({
        title: "Augmentation enregistrée",
        description: "Le salaire de base a été mis à jour.",
      });
      setAugApplyDialogOpen(false);
      setAugApplyMotif("");
      setAugSimResult(null);
      setAugValeur("");
      setAugGenDraft(snapshot);
      setAugGenDateInput(snapshot.effective_date);
      setAugGenMotifInput(snapshot.motif);
      await salaryHistoryQuery.refetch();
      const employeeRes = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
      setEmployee(employeeRes.data);
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Enregistrement impossible",
        description: typeof msg === "string" ? msg : "Réessayez plus tard.",
        variant: "destructive",
      });
    } finally {
      setAugApplySubmitting(false);
    }
  };

  const handleDeleteEmployee = async () => {
    if (!employeeId) return;
    try {
      await apiClient.delete(`/api/employees/${employeeId}`);
      toast({
        title: "Collaborateur supprimé",
        description: "Le collaborateur et son compte utilisateur ont été supprimés avec succès.",
      });
      navigate("/employees");
    } catch (error: unknown) {
      if (import.meta.env.DEV) {
        log.error("Erreur lors de la suppression du collaborateur", error);
      }
      const errorMessage =
        error && typeof error === "object" && "response" in error
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur de suppression",
        description:
          typeof errorMessage === "string" && errorMessage
            ? errorMessage
            : "Une erreur est survenue.",
        variant: "destructive",
      });
    }
  };

  const handleSaveTeamAssignment = async () => {
    if (!employeeId) return;
    setSavingTeam(true);
    try {
      const nextId = draftTeamId === "__none__" ? null : draftTeamId;
      await assignEmployeeTeam(employeeId, nextId);
      setEmployee((prev) => (prev ? { ...prev, team_id: nextId } : prev));
      const employeeRes = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
      setEmployee(employeeRes.data);
      void queryClient.invalidateQueries({ queryKey: ["employee", employeeId] });
      toast({ title: "Équipe mise à jour" });
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      const errorMessage =
        err.response?.data?.detail || "Impossible de mettre à jour l'équipe.";
      toast({
        title: "Erreur",
        description: String(errorMessage),
        variant: "destructive",
      });
    } finally {
      setSavingTeam(false);
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
  if (!employee) {
    return (
      <div className="space-y-6 p-8">
        <Link to="/employees" className="flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste des collaborateurs
        </Link>
        <p className="text-center text-muted-foreground">Employé non trouvé.</p>
      </div>
    );
  }

  
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
            {isRecentHire(employee.hire_date) ? (
              <Button variant="outline" size="sm" asChild>
                <Link to={`/onboarding/${employee.id}`}>
                  <ClipboardList className="mr-2 h-4 w-4" />
                  Voir l&apos;onboarding
                </Link>
              </Button>
            ) : null}
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
                <div className="flex flex-wrap items-center gap-2 basis-full sm:basis-auto">
                  <strong className="shrink-0">Équipe :</strong>
                  <div className="inline-flex min-w-0 flex-nowrap items-center gap-2">
                    <Select
                      value={draftTeamId}
                      onValueChange={setDraftTeamId}
                      disabled={teamsActiveQuery.isLoading || savingTeam}
                    >
                      <SelectTrigger
                        className="h-8 w-auto shrink-0 gap-1.5 px-2.5 [&>span]:line-clamp-none [&>span]:whitespace-nowrap"
                        aria-label="Équipe du collaborateur"
                      >
                        <SelectValue
                          placeholder={
                            employee.team_id && teamsActiveQuery.isLoading
                              ? "Chargement…"
                              : "Aucune équipe"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent position="popper" className="z-[100]">
                        <SelectItem value="__none__">Aucune équipe</SelectItem>
                        {activeTeamsSorted.map((t) => (
                          <SelectItem key={t.id} value={t.id}>
                            <span className="flex items-center gap-2">
                              <span
                                className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-border"
                                style={{ backgroundColor: t.color }}
                                aria-hidden
                              />
                              {t.name}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {teamAssignmentDirty && (
                      <>
                        <Button
                          type="button"
                          size="sm"
                          className="h-8 shrink-0"
                          disabled={savingTeam}
                          onClick={() => void handleSaveTeamAssignment()}
                        >
                          {savingTeam ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            "Enregistrer"
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 shrink-0"
                          disabled={savingTeam}
                          onClick={() => setDraftTeamId(savedTeamSelectValue)}
                        >
                          Annuler
                        </Button>
                      </>
                    )}
                  </div>
                </div>
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
                    <SelectTrigger className="h-8 w-auto shrink-0 gap-1.5 px-2.5 [&>span]:line-clamp-none [&>span]:whitespace-nowrap">
                      <SelectValue placeholder="Aucune" />
                    </SelectTrigger>
                    <SelectContent position="popper" className="z-[100]">
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

      {/* Bloc CSE — réservé RH / admin / collaborateur_rh (masqué pour manager) */}
      {employeeId && showEmployeeCSEBlock && (
        <EmployeeCSEBlock
          employeeId={employeeId}
          collegeElectoral={employee?.college_electoral}
          statutCse={employee?.statut_cse}
          heuresDelegationMensuelles={employee?.heures_delegation_mensuelles}
        />
      )}
      
      <Tabs value={activeTab} onValueChange={setActiveTab} defaultValue="documents" className="w-full">
        <TabsList
          className={cn(
            "grid h-auto min-h-10 w-full gap-0.5 p-1",
            medicalModuleEnabled
              ? "grid-cols-[minmax(0,0.9fr)_minmax(0,1.16fr)_minmax(0,0.9fr)_minmax(0,0.9fr)_minmax(0,0.9fr)_minmax(0,0.9fr)]"
              : "grid-cols-[minmax(0,0.92fr)_minmax(0,1.2fr)_minmax(0,0.92fr)_minmax(0,0.92fr)_minmax(0,0.92fr)]",
          )}
        >
          <TabsTrigger value="documents" className="px-2 py-1.5 text-[13px]">
            <FileText className="mr-1.5 h-4 w-4 shrink-0" />
            Documents
          </TabsTrigger>
          <TabsTrigger
            value={TAB_AUGMENTATIONS_PROMOTIONS}
            className="min-w-0 px-2 py-1.5 text-[13px] leading-snug"
            title="Augmentations et Promotions"
          >
            <TrendingUp className="mr-1.5 h-4 w-4 shrink-0" aria-hidden />
            <span className="whitespace-nowrap">Augmentations et Promotions</span>
          </TabsTrigger>
          <TabsTrigger value="saisie" className="px-2 py-1.5 text-[13px]">
            <ClipboardEdit className="mr-1.5 h-4 w-4 shrink-0" />
            Primes et autres
          </TabsTrigger>
          <TabsTrigger value="entretiens" className="relative gap-1.5 px-2 py-1.5 text-[13px]">
            <MessageSquare className="h-4 w-4 shrink-0" aria-hidden />
            Entretiens
            {annualReviewTabHasAlert && (
              <span
                className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-amber-500"
                aria-label="Entretien à traiter"
              />
            )}
          </TabsTrigger>
          {medicalModuleEnabled && (
            <TabsTrigger value="suivi_medical" className="relative gap-1.5 px-2 py-1.5 text-[13px]">
              <Stethoscope className="h-4 w-4 shrink-0" aria-hidden />
              Suivi médical
              {medicalTabHasOverdue && (
                <span
                  className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-destructive"
                  aria-label="Visite en retard"
                />
              )}
            </TabsTrigger>
          )}
          <TabsTrigger value="calendrier" className="px-2 py-1.5 text-[13px]">
            <CalendarIcon className="mr-1.5 h-4 w-4 shrink-0" />
            Calendrier
          </TabsTrigger>
          <TabsTrigger value="badgeuse" className="px-2 py-1.5 text-[13px]">
            <ScanLine className="mr-1.5 h-4 w-4 shrink-0" />
            Badgeuse
          </TabsTrigger>
        </TabsList>

        {/* --- Onglet Documents (explorateur par dossiers) --- */}
        <TabsContent value="documents" className="mt-4">
          {employeeId && employee && (
            <EmployeeDetailDocumentsTab
              employeeId={employeeId}
              employee={employee}
              credentialsPdfUrl={credentialsPdfUrl}
            />
          )}
        </TabsContent>

        <TabsContent value={TAB_AUGMENTATIONS_PROMOTIONS} className="mt-4">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-0">
          <div className="space-y-6 min-w-0 lg:pr-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calculator className="h-5 w-5 text-muted-foreground" />
                Augmentation simple
              </CardTitle>
              <CardDescription>
                Salaire brut mensuel :{" "}
                <span className="font-medium text-foreground">
                  {formatEuroAmount(valeurSalaireBrut(employee?.salaire_de_base))}
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <Label>Type d&apos;augmentation</Label>
                <RadioGroup
                  value={augSimType}
                  onValueChange={(v) => setAugSimType(v as "pourcentage" | "montant_fixe")}
                  className="flex flex-col gap-2 sm:flex-row sm:gap-6"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="pourcentage" id="aug-pct" />
                    <Label htmlFor="aug-pct" className="font-normal cursor-pointer">
                      Par pourcentage
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="montant_fixe" id="aug-fixe" />
                    <Label htmlFor="aug-fixe" className="font-normal cursor-pointer">
                      Par montant fixe
                    </Label>
                  </div>
                </RadioGroup>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="aug-valeur">
                    {augSimType === "pourcentage" ? "Pourcentage (%)" : "Montant (€)"}
                  </Label>
                  <Input
                    id="aug-valeur"
                    type="number"
                    min={0}
                    step={augSimType === "pourcentage" ? "0.1" : "1"}
                    value={augValeur}
                    onChange={(e) => setAugValeur(e.target.value)}
                    placeholder={augSimType === "pourcentage" ? "Ex. 3" : "Ex. 150"}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="aug-date-effet">Date d&apos;effet</Label>
                  <Input
                    id="aug-date-effet"
                    type="date"
                    value={augEffectiveDate}
                    onChange={(e) => setAugEffectiveDate(e.target.value)}
                  />
                </div>
                <div className="flex items-end">
                  <Button
                    type="button"
                    className="w-full sm:w-auto"
                    onClick={() => void handleSimulateAugmentation()}
                    disabled={augSimLoading || !activeCompanyId}
                  >
                    {augSimLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <TrendingUp className="mr-2 h-4 w-4" />
                    )}
                    Simuler
                  </Button>
                </div>
              </div>

              {augSimResult && (
                <div className="space-y-4">
                  <Card className="border-muted bg-muted/30">
                    <CardContent className="pt-6">
                      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3">
                        <div className="space-y-2">
                          <p className="text-sm font-semibold">Brut</p>
                          <p className="text-sm text-muted-foreground">
                            Avant : {formatEuroAmount(augSimResult.ancien_salaire_brut)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Après : {formatEuroAmount(augSimResult.nouveau_salaire_brut)}
                          </p>
                          <p className="text-sm font-medium text-emerald-700">
                            Gain : +{formatEuroAmount(augSimResult.difference_brut)} (
                            {augSimResult.taux_augmentation_reel.toLocaleString("fr-FR", {
                              maximumFractionDigits: 2,
                            })}
                            %)
                          </p>
                        </div>
                        <div className="space-y-2">
                          <p className="text-sm font-semibold">Net estimé*</p>
                          <p className="text-sm text-muted-foreground">
                            Avant : {formatEuroAmount(augSimResult.ancien_net_estime)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Après : {formatEuroAmount(augSimResult.nouveau_net_estime)}
                          </p>
                          <p className="text-sm font-medium text-emerald-700">
                            Gain : +{formatEuroAmount(augSimResult.difference_net)}
                          </p>
                          <p className="text-xs text-muted-foreground leading-snug">
                            * Estimation basée sur des taux moyens. Le net réel figure sur le bulletin de paie.
                          </p>
                        </div>
                        <div className="space-y-2">
                          <p className="text-sm font-semibold">Coût employeur</p>
                          <p className="text-sm text-muted-foreground">
                            Avant : {formatEuroAmount(augSimResult.cout_total_employeur_avant)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Après : {formatEuroAmount(augSimResult.cout_total_employeur_apres)}
                          </p>
                          <p className="text-sm font-medium text-emerald-700">
                            Gain : +{formatEuroAmount(augSimResult.difference_cout_employeur)}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Button type="button" onClick={() => setAugApplyDialogOpen(true)}>
                    Appliquer cette augmentation
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {augGenDraft && employee && (
            <Card className="border-primary/35 bg-muted/15">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Prochaine étape</CardTitle>
                <CardDescription>
                  Formaliser l&apos;augmentation par un avenant salaire (PDF dans Documents RH).
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-4">
                <Button
                  type="button"
                  onClick={() => {
                    setAugGenDateInput(augGenDraft.effective_date);
                    setAugGenMotifInput(augGenDraft.motif);
                    setAugGenDialogOpen(true);
                  }}
                >
                  Générer l&apos;avenant salaire
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setAugGenDraft(null)}>
                  Masquer
                </Button>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Historique des augmentations</CardTitle>
              <CardDescription>Évolutions de salaire enregistrées pour ce collaborateur.</CardDescription>
            </CardHeader>
            <CardContent>
              {salaryHistoryQuery.isLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : salaryHistoryQuery.data && salaryHistoryQuery.data.length > 0 ? (
                <div className="w-full overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date d&apos;effet</TableHead>
                        <TableHead>Ancien salaire</TableHead>
                        <TableHead>Nouveau salaire</TableHead>
                        <TableHead>Motif</TableHead>
                        <TableHead>Augmentation</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {salaryHistoryQuery.data.map((row) => {
                        const avant = valeurSalaireBrut(row.ancien_salaire);
                        const apres = valeurSalaireBrut(row.nouveau_salaire);
                        const diff = apres - avant;
                        const pct = avant > 0 ? (diff / avant) * 100 : 0;
                        return (
                          <TableRow key={row.id}>
                            <TableCell>{formatDateFR(row.effective_date)}</TableCell>
                            <TableCell>{formatEuroAmount(avant)}</TableCell>
                            <TableCell>{formatEuroAmount(apres)}</TableCell>
                            <TableCell className="max-w-[200px] truncate" title={row.motif ?? ""}>
                              {row.motif ?? "—"}
                            </TableCell>
                            <TableCell className="font-medium text-emerald-700 whitespace-nowrap">
                              +{formatEuroAmount(diff)} (+
                              {pct.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}%)
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  Aucune augmentation enregistrée.
                </p>
              )}
            </CardContent>
          </Card>

          <Dialog open={augApplyDialogOpen} onOpenChange={setAugApplyDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Confirmer l&apos;augmentation</DialogTitle>
                <DialogDescription>
                  Augmenter {employee.first_name} {employee.last_name} de{" "}
                  {augSimResult
                    ? `${formatEuroAmount(augSimResult.ancien_salaire_brut)} à ${formatEuroAmount(
                        augSimResult.nouveau_salaire_brut,
                      )} brut`
                    : ""}
                  .
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2 py-2">
                <Label htmlFor="aug-motif">Motif (optionnel)</Label>
                <Input
                  id="aug-motif"
                  value={augApplyMotif}
                  onChange={(e) => setAugApplyMotif(e.target.value)}
                  placeholder="Ex. ancienneté, reclassement…"
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setAugApplyDialogOpen(false)}>
                  Annuler
                </Button>
                <Button
                  onClick={() => void handleApplyAugmentationConfirm()}
                  disabled={augApplySubmitting || !augSimResult}
                >
                  {augApplySubmitting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Confirmer
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={augGenDialogOpen} onOpenChange={setAugGenDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Générer un avenant salaire</DialogTitle>
                <DialogDescription>
                  Générer un avenant salaire pour {employee.first_name} {employee.last_name}
                  {augGenDraft ? (
                    <>
                      {" "}
                      — nouveau brut : {formatEuroAmount(augGenDraft.nouveau_brut)}
                    </>
                  ) : null}
                  .
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="space-y-2">
                  <Label htmlFor="aug-gen-date">Date d&apos;effet</Label>
                  <Input
                    id="aug-gen-date"
                    type="date"
                    value={augGenDateInput}
                    onChange={(e) => setAugGenDateInput(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="aug-gen-motif">Motif (optionnel)</Label>
                  <Input
                    id="aug-gen-motif"
                    value={augGenMotifInput}
                    onChange={(e) => setAugGenMotifInput(e.target.value)}
                    placeholder="Ex. revue salariale"
                  />
                </div>
                <p className="text-xs text-muted-foreground rounded-md border border-muted bg-muted/30 px-3 py-2">
                  Les données seront enregistrées dans le document pour application automatique lorsque
                  le statut passera à « Signé ».
                </p>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button type="button" variant="outline" onClick={() => setAugGenDialogOpen(false)}>
                  Annuler
                </Button>
                <Button
                  type="button"
                  disabled={
                    augSalariatGenMut.isPending ||
                    !employeeId ||
                    !augGenDraft ||
                    !augGenDateInput.trim()
                  }
                  onClick={() => {
                    if (!employeeId || !augGenDraft) return;
                    augSalariatGenMut.mutate({
                      employee_id: employeeId,
                      document_type: "avenant_salaire",
                      category: "avenant",
                      date_effet: augGenDateInput,
                      motif: augGenMotifInput.trim() || undefined,
                      nouveau_salaire: augGenDraft.nouveau_brut,
                      template_id: null,
                    });
                  }}
                >
                  {augSalariatGenMut.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Confirmer
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          </div>

          <div className="space-y-6 min-w-0 lg:border-l-2 lg:border-muted-foreground/35 lg:pl-6">
          <Card>
            <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Award className="h-5 w-5 text-muted-foreground" />
                  Promotions
                </CardTitle>
                <CardDescription>
                  Évolutions de poste, salaire ou statut pour {employee.first_name} {employee.last_name}.
                </CardDescription>
              </div>
              <Button onClick={() => setPromotionModalOpen(true)} className="shrink-0">
                <Plus className="mr-2 h-4 w-4" />
                Nouvelle promotion
              </Button>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Historique des promotions</CardTitle>
              <CardDescription>
                Promotions et évolutions de carrière enregistrées pour ce collaborateur.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {promotionsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : promotions.length > 0 ? (
                <div className="w-full overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Type</TableHead>
                        <TableHead>Évolution</TableHead>
                        <TableHead>Date d&apos;effet</TableHead>
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
                                `/promotions/${promo.id}?returnTo=employee&employeeId=${employeeId}&tab=${TAB_AUGMENTATIONS_PROMOTIONS}`
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
                              {formatDateFR(promo.effective_date)}
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
                                    `/promotions/${promo.id}?returnTo=employee&employeeId=${employeeId}&tab=${TAB_AUGMENTATIONS_PROMOTIONS}`
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
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  Aucune promotion enregistrée.
                </p>
              )}
            </CardContent>
          </Card>
          </div>
          </div>
        </TabsContent>

        <TabsContent value="saisie" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row justify-between items-center">
              <div>
                <CardTitle>Primes de {new Date(selectedDate.year, selectedDate.month - 1).toLocaleString("fr-FR", { month: "long" })}</CardTitle>
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
          {employeeId && (
            <EmployeeDetailAnnualReviewsTab
              employeeId={employeeId}
              employeeName={`${employee.first_name} ${employee.last_name}`}
              canDeleteReview={canDeleteReview}
              onEmployeeRefresh={refreshEmployeeSnapshot}
            />
          )}
        </TabsContent>

        {medicalModuleEnabled && employeeId && (
          <TabsContent value="suivi_medical" className="mt-4">
            <EmployeeDetailMedicalTab
              employeeId={employeeId}
              employeeName={
                employee ? `${employee.first_name} ${employee.last_name}` : undefined
              }
            />
          </TabsContent>
        )}

        <TabsContent value="calendrier" className="mt-4">
          {isForfaitJour && employee && (
            <div className="mb-2 rounded-md border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
              <span className="font-medium">Saisie en jours (forfait jour)</span>
              {employee.statut ? (
                <span className="text-muted-foreground"> — statut : {employee.statut}</span>
              ) : null}
            </div>
          )}
          {!isForfaitJour && (
            <div className="mb-2 rounded-md border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
              Saisie en heures
            </div>
          )}
          <Card className="mt-3">
             <CardHeader className="flex flex-row justify-between items-center">
                <div className="flex items-center gap-4">
                  <div>
                    <CardTitle className="text-xl font-semibold text-foreground flex flex-wrap items-center gap-2">
                      Calendrier de {employee.first_name} {employee.last_name}
                      {calendarView === 'month' && (
                        <Badge
                          variant={monthCompletionStatus === 'saisi' ? 'secondary' : 'outline'}
                          className="text-xs font-normal"
                        >
                          {monthCompletionStatus === 'saisi' ? 'Saisi' : 'À saisir'}
                        </Badge>
                      )}
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
                <div className="flex items-center gap-2">
                  {!isDirty && !isSaving && (
                    <Badge variant="outline" className="text-xs font-normal text-muted-foreground">
                      À jour
                    </Badge>
                  )}
                  <Button
                    onClick={saveAllCalendarData}
                    disabled={isSaving || !isDirty}
                  >
                    {isSaving ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    {isSaving ? "Enregistrement..." : "Enregistrer"}
                  </Button>
                </div>
             </CardHeader>
             {calendarView === 'month' && (
               <CardDescription className="mt-1 ml-6 text-sm text-muted-foreground">
                  Cliquez sur un jour pour éditer le planning et les heures réalisées.
                </CardDescription>
             )}


             <CardContent className="p-0 md:p-2 pb-48">
                {calendarView === 'month' && employeeId && (
                  <CalendarAbsencesHint
                    employeeId={employeeId}
                    year={selectedDate.year}
                    month={selectedDate.month}
                  />
                )}
                {calendarView === 'month' && !isCalendarLoading && (
                  <CalendarKpiBand
                    plannedCalendar={plannedCalendar}
                    actualHours={actualHours}
                    isForfaitJour={isForfaitJour}
                  />
                )}
                {calendarView === 'month' && (
                  <WeekTemplateForm
                    template={weekTemplate}
                    setTemplate={setWeekTemplate}
                    onApply={applyWeekTemplate}
                    onApplyAndSave={applyWeekTemplateAndSave}
                    onCopyPreviousMonth={() => void copyPreviousMonthPlanned()}
                    isSaving={isSaving}
                    isCopyingPrevMonth={isCopyingPrevMonth}
                    isForfaitJour={isForfaitJour}
                    companyId={activeCompanyId}
                    daysInMonth={new Date(selectedDate.year, selectedDate.month, 0).getDate()}
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
                              className="min-h-[8.5rem] rounded-2xl bg-white dark:bg-slate-900/40 shadow-sm hover:shadow-md transition-all"
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
                                onCopyPlannedToActual={copyPlannedToActualForDay}
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
                        isForfaitJour={isForfaitJour}
                        onMonthClick={(month) => {
                          setSelectedDate({ year: selectedDate.year, month });
                          setCalendarView('month');
                        }}
                      />
                    )}
                  </>
                )}
             </CardContent>
           </Card>
        </TabsContent>

        <TabsContent value="badgeuse" className="mt-4">
          {employeeId && activeCompanyId && employee && (
            <EmployeeDetailBadgeuseSection
              employeeId={employeeId}
              companyId={activeCompanyId}
              employeeName={`${employee.first_name} ${employee.last_name}`}
            />
          )}
        </TabsContent>
      </Tabs>

      {/* ✅ MODIFIÉ : On passe les nouvelles props à BulkActionPanel */}
      {selectedDays.length > 0 && (
        <BulkActionPanel
          selectedCount={selectedDays.length}
          onBulkUpdate={bulkUpdateDays}
          updateSelection={updateSelection}
          onBulkUpdateAndSave={bulkUpdateDaysAndSave}
          onBulkCopyPlannedToActual={bulkCopyPlannedToActual}
          isSaving={isSaving}
          isForfaitJour={isForfaitJour}
        />
      )}

      <Dialog
        open={contractualOpen}
        onOpenChange={(open) => {
          if (!open) {
            setContractualOpen(false);
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Modification contractuelle détectée</DialogTitle>
            <DialogDescription>
              Des champs pouvant nécessiter un avenant ont changé depuis le chargement de la fiche.
              La fiche est déjà enregistrée : vous pouvez générer un avenant ou ignorer cette proposition.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[40vh] space-y-2 overflow-y-auto rounded-md border bg-muted/40 p-3 text-sm">
            {contractualDiffs.map((d) => (
              <p key={d.key}>
                <span className="font-medium">{d.label}</span> : {d.before} → {d.after}
              </p>
            ))}
          </div>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>Type d&apos;avenant</Label>
              <Select value={contractualAvenantType} onValueChange={setContractualAvenantType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(
                    [
                      "avenant_salaire",
                      "avenant_poste",
                      "avenant_temps",
                      "avenant_lieu",
                      "avenant_general",
                    ] as const
                  ).map((t) => (
                    <SelectItem key={t} value={t}>
                      {DOCUMENT_TYPE_LABELS[t] ?? t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Modèle</Label>
              <Select value={contractualTemplate} onValueChange={setContractualTemplate}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__eywai__">Standard EYWAI</SelectItem>
                  {contractualTemplatesForType.map((tpl: DocumentTemplate) => (
                    <SelectItem key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Date d&apos;effet</Label>
              <Input
                type="date"
                value={contractualDateEffet}
                onChange={(e) => setContractualDateEffet(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label>Motif (optionnel)</Label>
              <Input
                value={contractualMotifExtra}
                onChange={(e) => setContractualMotifExtra(e.target.value)}
                placeholder="Précisions pour l'avenant"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                setContractualOpen(false);
                if (employee) resetContractualBaselineFromEmployee(employee);
              }}
            >
              Ignorer
            </Button>
            <Button
              disabled={!contractualDateEffet || contractualGenMut.isPending}
              onClick={() => {
                if (!employeeId) return;
                const lines = contractualDiffs.map((d) => `${d.label} : ${d.before} → ${d.after}`);
                const auto = `Modification détectée sur la fiche :\n${lines.join("\n")}`;
                const motif = [auto, contractualMotifExtra.trim()].filter(Boolean).join("\n\n");
                contractualGenMut.mutate({
                  employee_id: employeeId,
                  document_type: contractualAvenantType,
                  category: "avenant",
                  date_effet: contractualDateEffet,
                  motif,
                  template_id: contractualTemplate === "__eywai__" ? null : contractualTemplate,
                });
              }}
            >
              {contractualGenMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer l&apos;avenant
            </Button>
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