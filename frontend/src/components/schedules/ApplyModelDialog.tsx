import { useEffect, useState } from 'react';
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
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ToastAction } from '@/components/ui/toast';
import { Loader2, Undo2 } from 'lucide-react';
import apiClient from '@/api/apiClient';
import * as calendarApi from '@/api/calendar';
import { useToast } from '@/components/ui/use-toast';
import { runWithConcurrency } from '@/lib/concurrency';
import {
  restorePlannedSnapshots,
  type PlannedSnapshot,
} from '@/lib/calendarBulkUndo';
import { loadSavedWeekTemplates, saveWeekTemplate, type SavedWeekTemplate } from '@/lib/weekTemplateStorage';
import { useCompany } from '@/contexts/CompanyContext';
import type { WeekTemplate } from '@/hooks/useCalendar';
import type { DayConfig, WeekConfig, WeekNumber } from './types';

const TIER_LABELS: Record<string, string> = {
  high: '37h',
  low: '32h',
  neutral: 'Neutre',
};

const INITIAL_DAY: DayConfig = { type: 'travail', hours: 8 };
const WEEKEND_DAY: DayConfig = { type: 'weekend', hours: 0 };

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
  onApplied: () => void;
}

export function ApplyModelDialog({
  open,
  onOpenChange,
  selectedEmployeeIds,
  employeeTeamId,
  year,
  month,
  onApplied,
}: ApplyModelDialogProps) {
  const { toast } = useToast();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const [useForAllWeeks, setUseForAllWeeks] = useState(true);
  const [activeWeekTab, setActiveWeekTab] = useState<WeekNumber>(1);
  const [weekConfigs, setWeekConfigs] = useState<Record<WeekNumber, WeekConfig>>({
    1: createInitialWeek(),
    2: createInitialWeek(),
    3: createInitialWeek(),
    4: createInitialWeek(),
    5: createInitialWeek(),
  });
  const [isApplying, setIsApplying] = useState(false);
  const [savedTemplates, setSavedTemplates] = useState<SavedWeekTemplateWithConfig[]>([]);
  const [templateName, setTemplateName] = useState('');

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

  const applySavedTemplate = (tpl: SavedWeekTemplateWithConfig) => {
    const config = tpl.weekConfig;
    setWeekConfigs({
      1: config,
      2: config,
      3: config,
      4: config,
      5: config,
    });
  };

  const updateDayConfig = (
    week: WeekNumber,
    day: keyof WeekConfig,
    field: 'type' | 'hours',
    value: string | number
  ) => {
    setWeekConfigs((prev) => ({
      ...prev,
      [week]: {
        ...prev[week],
        [day]: { ...prev[week][day], [field]: value },
      },
    }));
  };

  const restoreModel = async (snapshots: PlannedSnapshot[]) => {
    try {
      await restorePlannedSnapshots(snapshots, year, month);
      toast({
        title: 'Action annulée',
        description: 'Le planning précédent a été restauré.',
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

  const handleApply = async () => {
    if (selectedEmployeeIds.length === 0) return;
    setIsApplying(true);
    try {
      const modelToApply = useForAllWeeks
        ? {
            1: weekConfigs[1],
            2: weekConfigs[1],
            3: weekConfigs[1],
            4: weekConfigs[1],
            5: weekConfigs[1],
          }
        : weekConfigs;

      const snapshots: PlannedSnapshot[] = [];
      const snapshotTasks = selectedEmployeeIds.map((id) => async () => {
        const res = await calendarApi.getPlannedCalendar(id, year, month);
        snapshots.push({ id, planned: res.data.calendrier_prevu ?? [] });
      });
      await runWithConcurrency(snapshotTasks, 5);

      await apiClient.post('/api/schedules/apply-model', {
        employee_ids: selectedEmployeeIds,
        year,
        month,
        week_configs: modelToApply,
      });

      toast({
        title: 'Modèle appliqué',
        description: `Planning appliqué à ${selectedEmployeeIds.length} employé(s).`,
        action: (
          <ToastAction
            altText="Annuler l'application du modèle"
            onClick={() => void restoreModel(snapshots)}
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

  const current = useForAllWeeks ? 1 : activeWeekTab;
  const disabled = useForAllWeeks && activeWeekTab !== 1;

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
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
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
                    onClick={() => applySavedTemplate(tpl)}
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

          <div className="flex items-center gap-2">
            <Checkbox
              checked={useForAllWeeks}
              onCheckedChange={(v) => setUseForAllWeeks(!!v)}
              id="all-weeks"
            />
            <label htmlFor="all-weeks" className="text-sm">
              Même modèle pour toutes les semaines du mois
            </label>
          </div>

          {!useForAllWeeks && (
            <Tabs
              value={String(activeWeekTab)}
              onValueChange={(v) => setActiveWeekTab(Number(v) as WeekNumber)}
            >
              <TabsList className="grid grid-cols-5 w-full">
                {[1, 2, 3, 4, 5].map((w) => (
                  <TabsTrigger key={w} value={String(w)} className="text-xs">
                    S{w}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}

          <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
            {dayKeys.map((day) => {
              const conf = weekConfigs[current][day];
              return (
                <div
                  key={day}
                  className="grid grid-cols-[5rem_1fr_4rem] gap-2 items-center"
                >
                  <Label className="text-xs">{dayLabels[day]}</Label>
                  <Select
                    value={conf.type}
                    onValueChange={(v) => updateDayConfig(current, day, 'type', v)}
                    disabled={disabled}
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
                      updateDayConfig(current, day, 'hours', Number(e.target.value))
                    }
                    disabled={disabled || conf.type !== 'travail'}
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
                const config = weekConfigs[useForAllWeeks ? 1 : activeWeekTab];
                const template = {
                  1: config.monday.hours,
                  2: config.tuesday.hours,
                  3: config.wednesday.hours,
                  4: config.thursday.hours,
                  5: config.friday.hours,
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
            Appliquer le modèle
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
