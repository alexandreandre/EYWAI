import { useState } from 'react';
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
import type { DayConfig, WeekConfig, WeekNumber } from './types';

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

interface ApplyModelDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedEmployeeIds: string[];
  year: number;
  month: number;
  onApplied: () => void;
}

export function ApplyModelDialog({
  open,
  onOpenChange,
  selectedEmployeeIds,
  year,
  month,
  onApplied,
}: ApplyModelDialogProps) {
  const { toast } = useToast();
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
