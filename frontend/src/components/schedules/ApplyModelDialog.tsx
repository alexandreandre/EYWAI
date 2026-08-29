import { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { ToastAction } from '@/components/ui/toast';
import { Loader2, Undo2 } from 'lucide-react';
import apiClient from '@/api/apiClient';
import * as calendarApi from '@/api/calendar';
import { useToast } from '@/components/ui/use-toast';
import { runWithConcurrency } from '@/lib/concurrency';
import {
  restoreActualSnapshots,
  restorePlannedSnapshots,
  type ActualSnapshot,
  type PlannedSnapshot,
} from '@/lib/calendarBulkUndo';
import {
  buildActualEntriesFromWeekConfig,
  buildPlannedEntriesFromWeekConfig,
  sameWeekConfigAllMonth,
  type ApplyModelTarget,
  type ApplyModelWeekConfig,
} from '@/lib/applyWeekModel';
import {
  computePlanningWeeks,
  planningWeekDays,
  planningWeekLabel,
} from '@/lib/planningWeeks';
import type { EmployeeCalendarOverviewRow } from '@/lib/schedulesOverview';
import { loadSavedWeekTemplates, saveWeekTemplate, type SavedWeekTemplate } from '@/lib/weekTemplateStorage';
import { useCompany } from '@/contexts/CompanyContext';
import type { WeekTemplate } from '@/hooks/useCalendar';
import type { DayConfig, WeekConfig } from './types';

const TIER_LABELS: Record<string, string> = {
  high: '37h',
  low: '32h',
  neutral: 'Neutre',
};

const INITIAL_DAY: DayConfig = { type: 'travail', hours: 8 };
const WEEKEND_DAY: DayConfig = { type: 'weekend', hours: 0 };
const MONTH_SCOPE = 'month';

const createInitialWeek = (): WeekConfig => ({
  monday: { ...INITIAL_DAY },
  tuesday: { ...INITIAL_DAY },
  wednesday: { ...INITIAL_DAY },
  thursday: { ...INITIAL_DAY },
  friday: { ...INITIAL_DAY },
  saturday: { ...WEEKEND_DAY },
  sunday: { ...WEEKEND_DAY },
});

function weekTemplateToWeekConfig(template: WeekTemplate): WeekConfig {
  const week = createInitialWeek();
  const dayMap: Array<[keyof WeekConfig, number]> = [
    ['monday', 1],
    ['tuesday', 2],
    ['wednesday', 3],
    ['thursday', 4],
    ['friday', 5],
    ['saturday', 6],
    ['sunday', 7],
  ];
  for (const [key, day] of dayMap) {
    const raw = template[day];
    if (raw === undefined) continue;
    const hours = raw === '1' ? 1 : parseFloat(String(raw || '0')) || 0;
    if (hours <= 0) {
      week[key] = { type: 'weekend', hours: 0 };
    } else {
      week[key] = { type: 'travail', hours };
    }
  }
  return week;
}

type SavedWeekTemplateWithConfig = SavedWeekTemplate & { weekConfig: WeekConfig };

interface ApplyModelDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedEmployeeIds: string[];
  /** Équipe commune des salariés sélectionnés (filtre modèles par équipe). */
  employeeTeamId?: string | null;
  year: number;
  month: number;
  /** Semaine affichée dans la vue planning (0-based). */
  viewWeekIndex: number;
  overviewRows: EmployeeCalendarOverviewRow[];
  onApplied: () => void;
}

export function ApplyModelDialog({
  open,
  onOpenChange,
  selectedEmployeeIds,
  employeeTeamId,
  year,
  month,
  viewWeekIndex,
  overviewRows,
  onApplied,
}: ApplyModelDialogProps) {
  const { toast } = useToast();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const weeks = useMemo(() => computePlanningWeeks(year, month), [year, month]);
  const clampedViewWeek = Math.min(Math.max(viewWeekIndex, 0), Math.max(weeks.length - 1, 0));

  const [weekConfig, setWeekConfig] = useState<WeekConfig>(createInitialWeek);
  const [applyScope, setApplyScope] = useState(`week-${clampedViewWeek}`);
  const [isApplying, setIsApplying] = useState(false);
  const [applyTarget, setApplyTarget] = useState<ApplyModelTarget>('planned');
  const [savedTemplates, setSavedTemplates] = useState<SavedWeekTemplateWithConfig[]>([]);
  const [templateName, setTemplateName] = useState('');

  useEffect(() => {
    if (!open) return;
    setApplyScope(`week-${clampedViewWeek}`);
  }, [open, clampedViewWeek]);

  useEffect(() => {
    if (!open || !companyId) return;
    let cancelled = false;
    loadSavedWeekTemplates(companyId, employeeTeamId)
      .then((rows) => {
        if (cancelled) return;
        setSavedTemplates(
          rows.map((t) => ({
            ...t,
            weekConfig: weekTemplateToWeekConfig(t.template),
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setSavedTemplates([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open, companyId, employeeTeamId]);

  const isMonthScope = applyScope === MONTH_SCOPE;
  const scopeWeekIndex = isMonthScope
    ? clampedViewWeek
    : Number(applyScope.replace('week-', ''));
  const scopedDays = isMonthScope
    ? undefined
    : planningWeekDays(weeks[scopeWeekIndex] ?? []);
  const scopeLabel = isMonthScope
    ? 'le mois entier'
    : `la semaine ${planningWeekLabel(weeks[scopeWeekIndex] ?? [])}`;

  const updateDayConfig = (
    day: keyof WeekConfig,
    field: 'type' | 'hours',
    value: string | number,
  ) => {
    setWeekConfig((prev) => ({
      ...prev,
      [day]: { ...prev[day], [field]: value },
    }));
  };

  const restoreModel = async (
    plannedSnapshots: PlannedSnapshot[],
    actualSnapshots: ActualSnapshot[],
  ) => {
    try {
      if (plannedSnapshots.length > 0) {
        await restorePlannedSnapshots(plannedSnapshots, year, month);
      }
      if (actualSnapshots.length > 0) {
        await restoreActualSnapshots(actualSnapshots, year, month);
      }
      toast({
        title: 'Action annulée',
        description: 'L’état précédent a été restauré.',
      });
      onApplied();
    } catch {
      toast({
        title: 'Erreur',
        description: "Impossible d'annuler l'application du modèle.",
        variant: 'destructive',
      });
    }
  };

  const applyActualHours = async (config: ApplyModelWeekConfig) => {
    const snapshots: ActualSnapshot[] = [];
    const tasks = selectedEmployeeIds.map((id) => async () => {
      const [plannedRes, actualRes] = await Promise.all([
        calendarApi.getPlannedCalendar(id, year, month),
        calendarApi.getActualHours(id, year, month),
      ]);
      const existing = actualRes.data.calendrier_reel ?? [];
      snapshots.push({ id, actual: existing });
      const isForfait =
        overviewRows.find((row) => row.employee.id === id)?.isForfaitJour ?? false;
      const entries = buildActualEntriesFromWeekConfig(
        year,
        month,
        config,
        isForfait,
        {
          existing,
          planned: plannedRes.data.calendrier_prevu ?? [],
          onlyDays: scopedDays,
        },
      );
      await calendarApi.updateActualHours(id, year, month, entries);
    });
    await runWithConcurrency(tasks, 5);
    return snapshots;
  };

  const applyPlannedHours = async (config: ApplyModelWeekConfig) => {
    const snapshots: PlannedSnapshot[] = [];
    if (isMonthScope) {
      const snapshotTasks = selectedEmployeeIds.map((id) => async () => {
        const res = await calendarApi.getPlannedCalendar(id, year, month);
        snapshots.push({ id, planned: res.data.calendrier_prevu ?? [] });
      });
      await runWithConcurrency(snapshotTasks, 5);
      await apiClient.post('/api/schedules/apply-model', {
        employee_ids: selectedEmployeeIds,
        year,
        month,
        week_configs: sameWeekConfigAllMonth(config),
      });
      return snapshots;
    }

    const tasks = selectedEmployeeIds.map((id) => async () => {
      const res = await calendarApi.getPlannedCalendar(id, year, month);
      const existing = res.data.calendrier_prevu ?? [];
      snapshots.push({ id, planned: existing });
      const isForfait =
        overviewRows.find((row) => row.employee.id === id)?.isForfaitJour ?? false;
      const entries = buildPlannedEntriesFromWeekConfig(
        year,
        month,
        config,
        isForfait,
        { existing, onlyDays: scopedDays },
      );
      await calendarApi.updatePlannedCalendar(id, year, month, entries);
    });
    await runWithConcurrency(tasks, 5);
    return snapshots;
  };

  const handleApply = async () => {
    if (selectedEmployeeIds.length === 0) return;
    setIsApplying(true);
    try {
      const writePlanned = applyTarget === 'planned' || applyTarget === 'both';
      const writeActual = applyTarget === 'actual' || applyTarget === 'both';

      let plannedSnapshots: PlannedSnapshot[] = [];
      let actualSnapshots: ActualSnapshot[] = [];

      if (writePlanned) {
        plannedSnapshots = await applyPlannedHours(weekConfig);
      }
      if (writeActual) {
        actualSnapshots = await applyActualHours(weekConfig);
      }

      const count = selectedEmployeeIds.length;
      const toastCopy =
        applyTarget === 'actual'
          ? {
              title: 'Heures faites appliquées',
              description: `Heures faites posées sur ${scopeLabel} pour ${count} employé(s).`,
            }
          : applyTarget === 'both'
            ? {
                title: 'Modèle appliqué',
                description: `Heures prévues et faites posées sur ${scopeLabel} pour ${count} employé(s).`,
              }
            : {
                title: 'Modèle appliqué',
                description: `Planning prévu appliqué sur ${scopeLabel} pour ${count} employé(s).`,
              };

      toast({
        ...toastCopy,
        action: (
          <ToastAction
            altText="Annuler l'application du modèle"
            onClick={() => void restoreModel(plannedSnapshots, actualSnapshots)}
          >
            <Undo2 className="mr-1 h-3.5 w-3.5" />
            Annuler
          </ToastAction>
        ),
      });
      onApplied();
      onOpenChange(false);
    } catch (err: unknown) {
      const detail =
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast({
        title: 'Erreur',
        description: String(detail ?? "Impossible d'appliquer le modèle."),
        variant: 'destructive',
      });
    } finally {
      setIsApplying(false);
    }
  };

  const dayKeys = [
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday',
  ] as const;
  const dayLabels: Record<(typeof dayKeys)[number], string> = {
    monday: 'Lundi',
    tuesday: 'Mardi',
    wednesday: 'Mercredi',
    thursday: 'Jeudi',
    friday: 'Vendredi',
    saturday: 'Samedi',
    sunday: 'Dimanche',
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Appliquer un modèle de semaine</DialogTitle>
          <DialogDescription>
            {selectedEmployeeIds.length} employé(s) sélectionné(s) —{' '}
            {new Date(year, month - 1).toLocaleString('fr-FR', {
              month: 'long',
              year: 'numeric',
            })}
            . Les absences validées restent intactes.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Écrire dans</Label>
            <ToggleGroup
              type="single"
              value={applyTarget}
              onValueChange={(v) => v && setApplyTarget(v as ApplyModelTarget)}
              className="grid w-full grid-cols-3 border rounded-md"
            >
              <ToggleGroupItem value="planned" className="h-8 px-2 text-xs">
                Heures prévues
              </ToggleGroupItem>
              <ToggleGroupItem value="actual" className="h-8 px-2 text-xs">
                Heures faites
              </ToggleGroupItem>
              <ToggleGroupItem value="both" className="h-8 px-2 text-xs">
                Les deux
              </ToggleGroupItem>
            </ToggleGroup>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Appliquer à</Label>
            <Select value={applyScope} onValueChange={setApplyScope}>
              <SelectTrigger className="h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {weeks.map((week, index) => {
                  const label = planningWeekLabel(week);
                  const isCurrent = index === clampedViewWeek;
                  return (
                    <SelectItem key={index} value={`week-${index}`}>
                      {isCurrent
                        ? `Cette semaine · ${label}`
                        : `Sem. ${index + 1} · ${label}`}
                    </SelectItem>
                  );
                })}
                <SelectItem value={MONTH_SCOPE}>Mois entier</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {savedTemplates.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">
                Modèles entreprise (bibliothèque)
              </Label>
              <div className="flex flex-wrap gap-1">
                {savedTemplates.map((tpl) => (
                  <Button
                    key={tpl.id ?? tpl.name}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => setWeekConfig(tpl.weekConfig)}
                  >
                    {tpl.name}
                    {tpl.modulation_tier && tpl.modulation_tier !== 'neutral' && (
                      <span className="ml-1 text-muted-foreground">
                        ({TIER_LABELS[tpl.modulation_tier] ?? tpl.modulation_tier})
                      </span>
                    )}
                  </Button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
            {dayKeys.map((day) => {
              const conf = weekConfig[day];
              return (
                <div
                  key={day}
                  className="grid grid-cols-[5rem_1fr_4rem] gap-2 items-center"
                >
                  <Label className="text-xs">{dayLabels[day]}</Label>
                  <Select
                    value={conf.type}
                    onValueChange={(v) => updateDayConfig(day, 'type', v)}
                  >
                    <SelectTrigger className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="travail">Travail</SelectItem>
                      <SelectItem value="conge">Congé</SelectItem>
                      <SelectItem value="ferie">Férié</SelectItem>
                      <SelectItem value="arret_maladie">Arrêt</SelectItem>
                      <SelectItem value="weekend">Week-end</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    type="number"
                    min={0}
                    max={24}
                    step={0.5}
                    value={conf.hours}
                    onChange={(e) =>
                      updateDayConfig(day, 'hours', Number(e.target.value))
                    }
                    disabled={conf.type !== 'travail'}
                    className="h-8"
                  />
                </div>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t pt-3">
            <Input
              className="h-8 w-40 text-xs"
              placeholder="Nom du modèle"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              disabled={!templateName.trim()}
              onClick={async () => {
                const template = {
                  1: weekConfig.monday.hours,
                  2: weekConfig.tuesday.hours,
                  3: weekConfig.wednesday.hours,
                  4: weekConfig.thursday.hours,
                  5: weekConfig.friday.hours,
                };
                const next = await saveWeekTemplate(companyId, templateName, template);
                setSavedTemplates(
                  next.map((t) => ({
                    ...t,
                    weekConfig: weekTemplateToWeekConfig(t.template),
                  })),
                );
                setTemplateName('');
                toast({ title: 'Modèle enregistré' });
              }}
            >
              Mémoriser en bibliothèque
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isApplying}>
            Annuler
          </Button>
          <Button onClick={() => void handleApply()} disabled={isApplying}>
            {isApplying && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isMonthScope ? 'Appliquer au mois' : 'Appliquer à la semaine'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
