import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, ExternalLink, Briefcase, TreePalm, Sparkles, Stethoscope, Coffee, Leaf, Ban, Moon, GraduationCap, PauseCircle, type LucideIcon } from 'lucide-react';
import { useActivitePartielleActive } from '@/hooks/useActivitePartielleActive';
import { editableTypeOptionsFor, reelApresChangementDeType } from '@/lib/calendarTypes';
import { estAbsentATyper } from '@/lib/absentATyper';
import { cn } from '@/lib/utils';
import type { PlannedEventData, ActualHoursData } from '@/api/calendar';
import type { DayPatch } from '@/lib/schedulesOverview';

// Les types proposés sont ceux du calendrier complet (`editableTypeOptionsFor`) :
// même liste, activité partielle comprise si la société l'a activée ; « Arrêt »
// et l'ancien « Congé (hors paie) » seulement sur un jour qui les porte déjà
// (Lyon, 17/11 : la liste écrite ici en dur divergeait). Ici, l'apparence.
const APPARENCE: Record<string, { label?: string; icon: LucideIcon; cls: string }> = {
  travail: { icon: Briefcase, cls: 'bg-sky-100 text-sky-700 border-sky-200' },
  conges_payes: { label: 'CP', icon: TreePalm, cls: 'bg-green-100 text-green-700 border-green-200' },
  rtt: { icon: Leaf, cls: 'bg-teal-100 text-teal-700 border-teal-200' },
  ferie: { icon: Sparkles, cls: 'bg-purple-100 text-purple-700 border-purple-200' },
  weekend: { icon: Coffee, cls: 'bg-slate-100 text-slate-600 border-slate-200' },
  repos: { label: 'Repos / récup.', icon: Moon, cls: 'bg-slate-100 text-slate-700 border-slate-300' },
  absence_non_remuneree: { label: 'Abs. non payée', icon: Ban, cls: 'bg-orange-100 text-orange-700 border-orange-200' },
  ecole: { icon: GraduationCap, cls: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
  activite_partielle: { label: 'Act. partielle', icon: PauseCircle, cls: 'bg-amber-100 text-amber-800 border-amber-200' },
  arret_maladie: { label: 'Arrêt', icon: Stethoscope, cls: 'bg-red-100 text-red-700 border-red-200' },
  conge: { icon: TreePalm, cls: 'bg-amber-100 text-amber-700 border-amber-200' },
};
const APPARENCE_PAR_DEFAUT: { label?: string; icon: LucideIcon; cls: string } = {
  icon: Briefcase,
  cls: 'bg-muted text-foreground border-input',
};

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
  const activitePartielle = useActivitePartielleActive();
  const [type, setType] = useState<string>(planned?.type ?? 'travail');
  const [plannedHours, setPlannedHours] = useState<string>(
    planned?.heures_prevues != null ? String(planned.heures_prevues) : ''
  );
  const [actualHours, setActualHours] = useState<string>(
    actual?.heures_faites != null ? String(actual.heures_faites) : ''
  );
  const [isSaving, setIsSaving] = useState(false);
  // Demi-journée d'un CP ou d'un RTT posé ici, comme dans « Saisir les congés »
  // (retour du 10/11). Seulement pour un jour nouvellement typé : un congé
  // déjà posé se modifie dans « Gestion des congés ».
  const [demiJournee, setDemiJournee] = useState<'journee' | 'matin' | 'apres_midi'>('journee');

  useEffect(() => {
    setDemiJournee('journee');
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
    // Même règle que la case du calendrier : un type non travaillé remet le
    // réel à 0 ; la RH saisit ensuite les heures faites (demi-journée).
    const reel = reelApresChangementDeType(newType, type);
    if (reel !== undefined && reel !== null) setActualHours(String(reel));
    if (isForfaitJour) {
      if (newType === 'activite_partielle') {
        // Le jour chômé reste un jour prévu : c'est lui qui est indemnisé.
        if (plannedHours === '' || plannedHours === '0') setPlannedHours('1');
      } else if (newType !== 'travail') {
        setPlannedHours('0');
      } else if (plannedHours === '' || plannedHours === '0') {
        setPlannedHours('1');
      }
    } else if (newType === 'conges_payes' || newType === 'rtt') {
      // Jour d'absence : 0 h au planning (convention bulletin) — la demande
      // validée créée côté serveur porte le décompte.
      setPlannedHours('0');
    } else if (newType === 'travail' && plannedHours === '') {
      setPlannedHours('8');
    }
  };

  const congeAvecDemiJournee =
    !isForfaitJour &&
    (type === 'conges_payes' || type === 'rtt') &&
    planned?.type !== type;

  const buildPatch = (): DayPatch => {
    const patch: DayPatch = { type };
    if (congeAvecDemiJournee && demiJournee !== 'journee') {
      patch.demi_journee = demiJournee;
    }
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
    if (type !== 'travail' && type !== 'work' && type !== 'activite_partielle') {
      // Un réel > 0 sur un jour non travaillé compte les heures comme
      // travaillées en paie et efface l'absence du bulletin : forcé à 0.
      // Activité partielle : les heures faites d'une demi-journée restent.
      patch.heures_faites = 0;
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
        {estAbsentATyper(planned) && (
          <p
            className="mt-1 text-xs font-medium text-red-800 bg-red-50 border border-red-300 rounded px-2 py-1"
            data-testid="editeur-absent-a-typer"
          >
            Absent : choisissez le type du jour (CP, RTT, arrêt ou absence non payée). La paie
            reste bloquée tant qu’il manque.
          </p>
        )}
        {hasAbsenceConflict && (
          <p className="mt-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
            Absence validée non reflétée sur ce jour.
          </p>
        )}
      </div>

      <div>
        <Label className="text-xs mb-1.5 block">Type</Label>
        <div className="grid grid-cols-3 gap-1.5">
          {editableTypeOptionsFor(planned?.type, activitePartielle).map((choix) => {
            const apparence = APPARENCE[choix.value] ?? APPARENCE_PAR_DEFAUT;
            const opt = { ...choix, ...apparence, label: apparence.label ?? choix.label };
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

      {congeAvecDemiJournee && (
        <div data-testid="demi-journee-calendrier">
          <Label className="text-xs mb-1.5 block">Durée</Label>
          <div className="grid grid-cols-3 gap-1.5">
            {(
              [
                ['journee', 'Journée'],
                ['matin', 'Matin'],
                ['apres_midi', 'Après-midi'],
              ] as const
            ).map(([valeur, libelle]) => (
              <button
                key={valeur}
                type="button"
                aria-pressed={demiJournee === valeur}
                onClick={() => setDemiJournee(valeur)}
                className={cn(
                  'px-2 py-1.5 rounded-md border text-[11px] font-medium transition',
                  demiJournee === valeur
                    ? 'bg-green-100 text-green-700 border-green-200'
                    : 'bg-background text-muted-foreground border-input hover:bg-muted'
                )}
              >
                {libelle}
              </button>
            ))}
          </div>
          {demiJournee !== 'journee' && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              Une demi-journée compte 0,5 jour.
            </p>
          )}
        </div>
      )}

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
            <Label htmlFor="actual-fj" className="text-xs">Travaillé</Label>
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
