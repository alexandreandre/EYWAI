import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, ExternalLink, Briefcase, TreePalm, Sparkles, Stethoscope, Coffee } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { PlannedEventData, ActualHoursData } from '@/api/calendar';
import type { DayPatch } from '@/lib/schedulesOverview';

const TYPE_OPTIONS = [
  { value: 'travail', label: 'Travail', icon: Briefcase, cls: 'bg-sky-100 text-sky-700 border-sky-200' },
  { value: 'conge', label: 'Congé', icon: TreePalm, cls: 'bg-amber-100 text-amber-700 border-amber-200' },
  { value: 'ferie', label: 'Férié', icon: Sparkles, cls: 'bg-purple-100 text-purple-700 border-purple-200' },
  { value: 'arret_maladie', label: 'Arrêt', icon: Stethoscope, cls: 'bg-red-100 text-red-700 border-red-200' },
  { value: 'weekend', label: 'Week-end', icon: Coffee, cls: 'bg-slate-100 text-slate-600 border-slate-200' },
] as const;

interface PlanningDayEditorProps {
  employeeName: string;
  employeeId: string;
  day: number;
  year: number;
  month: number;
  isForfaitJour: boolean;
  planned: PlannedEventData | undefined;
  actual: ActualHoursData | undefined;
  hasAbsenceConflict: boolean;
  onApply: (patch: DayPatch) => Promise<boolean>;
  onClose: () => void;
  onOpenFullCalendar: () => void;
}

export function PlanningDayEditor({
  employeeName,
  day,
  year,
  month,
  isForfaitJour,
  planned,
  actual,
  hasAbsenceConflict,
  onApply,
  onClose,
  onOpenFullCalendar,
}: PlanningDayEditorProps) {
  const [type, setType] = useState<string>(planned?.type ?? 'travail');
  const [plannedHours, setPlannedHours] = useState<string>(
    planned?.heures_prevues != null ? String(planned.heures_prevues) : ''
  );
  const [actualHours, setActualHours] = useState<string>(
    actual?.heures_faites != null ? String(actual.heures_faites) : ''
  );
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setType(planned?.type ?? 'travail');
    setPlannedHours(
      planned?.heures_prevues != null ? String(planned.heures_prevues) : ''
    );
    setActualHours(
      actual?.heures_faites != null ? String(actual.heures_faites) : ''
    );
  }, [planned, actual]);

  const dateLabel = new Date(year, month - 1, day).toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });

  const handleTypeChange = (newType: string) => {
    setType(newType);
    if (isForfaitJour) {
      if (newType !== 'travail') {
        setPlannedHours('0');
        setActualHours('0');
      } else if (plannedHours === '' || plannedHours === '0') {
        setPlannedHours('1');
      }
    } else if (newType !== 'travail' && plannedHours === '') {
      // garde la saisie en cours
    } else if (newType === 'travail' && plannedHours === '') {
      setPlannedHours('8');
    }
  };

  const buildPatch = (): DayPatch => {
    const patch: DayPatch = { type };
    if (isForfaitJour) {
      const p = plannedHours.trim();
      const a = actualHours.trim();
      patch.heures_prevues = p === '' ? null : Number(p) > 0 ? 1 : 0;
      patch.heures_faites = a === '' ? null : Number(a) > 0 ? 1 : 0;
    } else {
      patch.heures_prevues = plannedHours === '' ? null : Number(plannedHours);
      patch.heures_faites = actualHours === '' ? null : Number(actualHours);
    }
    if (type !== 'travail' && type !== 'weekend') {
      // Pour congé/férié/arrêt : heures prévues à null par défaut si non renseignées
      if (plannedHours === '') patch.heures_prevues = null;
    }
    return patch;
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const ok = await onApply(buildPatch());
      if (ok) onClose();
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopyPlannedToActual = () => {
    setActualHours(plannedHours);
  };

  return (
    <div className="w-[320px] space-y-3">
      <div>
        <p className="text-sm font-semibold leading-tight">{employeeName}</p>
        <p className="text-xs text-muted-foreground capitalize">{dateLabel}</p>
        {hasAbsenceConflict && (
          <p className="mt-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
            Absence validée non reflétée sur ce jour.
          </p>
        )}
      </div>

      <div>
        <Label className="text-xs mb-1.5 block">Type</Label>
        <div className="grid grid-cols-3 gap-1.5">
          {TYPE_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const active = type === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleTypeChange(opt.value)}
                className={cn(
                  'flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-md border text-[11px] font-medium transition',
                  active ? opt.cls : 'bg-background text-muted-foreground border-input hover:bg-muted'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{opt.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {isForfaitJour ? (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="planned-fj" className="text-xs">Prévu</Label>
            <select
              id="planned-fj"
              className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={plannedHours === '' ? '' : Number(plannedHours) > 0 ? '1' : '0'}
              onChange={(e) => setPlannedHours(e.target.value)}
            >
              <option value="1">Jour prévu</option>
              <option value="0">Non prévu</option>
            </select>
          </div>
          <div>
            <Label htmlFor="actual-fj" className="text-xs">Réel</Label>
            <select
              id="actual-fj"
              className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={actualHours === '' ? '' : Number(actualHours) > 0 ? '1' : '0'}
              onChange={(e) => setActualHours(e.target.value)}
            >
              <option value="">—</option>
              <option value="1">Travaillé</option>
              <option value="0">Non travaillé</option>
            </select>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="planned-h" className="text-xs">H. prévues</Label>
            <Input
              id="planned-h"
              type="number"
              min={0}
              step={0.5}
              value={plannedHours}
              onChange={(e) => setPlannedHours(e.target.value)}
              className="h-9 mt-1"
              placeholder="—"
            />
          </div>
          <div>
            <Label htmlFor="actual-h" className="text-xs">H. faites</Label>
            <Input
              id="actual-h"
              type="number"
              min={0}
              step={0.5}
              value={actualHours}
              onChange={(e) => setActualHours(e.target.value)}
              className="h-9 mt-1"
              placeholder="—"
            />
          </div>
        </div>
      )}

      {!isForfaitJour && plannedHours !== '' && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 text-xs w-full justify-start"
          onClick={handleCopyPlannedToActual}
        >
          Copier prévu → réel
        </Button>
      )}

      <div className="flex items-center justify-between gap-2 pt-1">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 text-xs"
          onClick={onOpenFullCalendar}
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Calendrier complet
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isSaving}>
            Annuler
          </Button>
          <Button size="sm" onClick={() => void handleSave()} disabled={isSaving}>
            {isSaving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
            Enregistrer
          </Button>
        </div>
      </div>
    </div>
  );
}
