import { useMemo, useState } from 'react';
import { AlertTriangle, Check, Loader2, Trash2, UserCheck, UserX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import { runWithConcurrency } from '@/lib/concurrency';
import {
  getActualHours,
  getPlannedCalendar,
  updateActualHours,
  updatePlannedCalendar,
  type AiCalendarProposal,
  type AiEmployeeProposal,
  type DayNature,
  type RosterEmployee,
} from '@/api/calendar';

const DAY_TYPES: { value: string; label: string }[] = [
  { value: 'travail', label: 'Travail' },
  { value: 'conge', label: 'Congé' },
  { value: 'ferie', label: 'Férié' },
  { value: 'arret_maladie', label: 'Arrêt maladie' },
  { value: 'absence', label: 'Absence' },
  { value: 'weekend', label: 'Week-end' },
];

interface EditableDay {
  jour: number;
  heures: number | null;
  type: string;
  nature: DayNature;
}

interface EditableRow {
  key: string;
  rawName: string;
  employeeId: string | null;
  confidence: AiEmployeeProposal['match_confidence'];
  warnings: string[];
  days: EditableDay[];
}

interface AssistedFillReviewProps {
  proposal: AiCalendarProposal;
  roster: RosterEmployee[];
  onApplied: () => void;
  onBack: () => void;
}

function ConfidenceBadge({ confidence }: { confidence: AiEmployeeProposal['match_confidence'] }) {
  if (confidence === 'high') {
    return (
      <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-emerald-700">
        <UserCheck className="mr-1 h-3 w-3" /> Identifié
      </Badge>
    );
  }
  if (confidence === 'medium') {
    return (
      <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-700">
        <AlertTriangle className="mr-1 h-3 w-3" /> À confirmer
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="border-destructive/40 bg-destructive/5 text-destructive">
      <UserX className="mr-1 h-3 w-3" /> Non reconnu
    </Badge>
  );
}

/** Petit bouton bascule prévu / fait pour un jour. */
function NatureToggle({
  nature,
  onChange,
}: {
  nature: DayNature;
  onChange: (n: DayNature) => void;
}) {
  const isPrevu = nature === 'prevu';
  return (
    <button
      type="button"
      onClick={() => onChange(isPrevu ? 'reel' : 'prevu')}
      className={cn(
        'rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide transition-colors',
        isPrevu
          ? 'bg-sky-100 text-sky-700 hover:bg-sky-200'
          : 'bg-violet-100 text-violet-700 hover:bg-violet-200',
      )}
      title={isPrevu ? 'Heures prévues (cliquer pour basculer en faites)' : 'Heures faites (cliquer pour basculer en prévues)'}
    >
      {isPrevu ? 'Prév.' : 'Fait'}
    </button>
  );
}

interface ExistingDay {
  jour: number;
  type?: string | null;
}

export function AssistedFillReview({
  proposal,
  roster,
  onApplied,
  onBack,
}: AssistedFillReviewProps) {
  const { toast } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  const [rows, setRows] = useState<EditableRow[]>(() =>
    proposal.employees.map((emp, idx) => ({
      key: `${idx}-${emp.raw_name}`,
      rawName: emp.raw_name,
      employeeId: emp.employee_id,
      confidence: emp.match_confidence,
      warnings: emp.warnings,
      days: emp.days.map((d) => ({
        jour: d.jour,
        heures: d.heures,
        type: d.type,
        nature: d.nature,
      })),
    })),
  );

  const sortedRoster = useMemo(
    () =>
      [...roster].sort((a, b) =>
        `${a.last_name} ${a.first_name}`.localeCompare(
          `${b.last_name} ${b.first_name}`,
          'fr',
        ),
      ),
    [roster],
  );

  const natureCounts = useMemo(() => {
    let prevu = 0;
    let reel = 0;
    rows.forEach((r) =>
      r.days.forEach((d) => {
        if (d.nature === 'prevu') prevu += 1;
        else reel += 1;
      }),
    );
    return { prevu, reel };
  }, [rows]);

  const updateRow = (key: string, patch: Partial<EditableRow>) => {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  };

  const updateDay = (rowKey: string, jour: number, patch: Partial<EditableDay>) => {
    setRows((prev) =>
      prev.map((r) =>
        r.key === rowKey
          ? {
              ...r,
              days: r.days.map((d) => (d.jour === jour ? { ...d, ...patch } : d)),
            }
          : r,
      ),
    );
  };

  const removeDay = (rowKey: string, jour: number) => {
    setRows((prev) =>
      prev.map((r) =>
        r.key === rowKey ? { ...r, days: r.days.filter((d) => d.jour !== jour) } : r,
      ),
    );
  };

  const setAllNature = (nature: DayNature) => {
    setRows((prev) =>
      prev.map((r) => ({ ...r, days: r.days.map((d) => ({ ...d, nature })) })),
    );
  };

  const readyRows = rows.filter((r) => r.employeeId && r.days.length > 0);
  const unresolvedCount = rows.filter((r) => !r.employeeId).length;

  const persistEmployee = async (row: EditableRow) => {
    const employeeId = row.employeeId as string;
    const prevuDays = row.days.filter((d) => d.nature === 'prevu');
    const reelDays = row.days.filter((d) => d.nature === 'reel');

    if (prevuDays.length > 0) {
      let existing: ExistingDay[] = [];
      try {
        const res = await getPlannedCalendar(employeeId, proposal.year, proposal.month);
        existing = (res.data?.calendrier_prevu ?? []) as ExistingDay[];
      } catch {
        existing = [];
      }
      const map = new Map<number, { jour: number; type: string; heures_prevues: number | null }>();
      existing.forEach((d) => {
        if (typeof d.jour === 'number') {
          map.set(d.jour, {
            jour: d.jour,
            type: (d.type as string) ?? 'travail',
            heures_prevues:
              (d as { heures_prevues?: number | null }).heures_prevues ?? null,
          });
        }
      });
      prevuDays.forEach((d) =>
        map.set(d.jour, { jour: d.jour, type: d.type, heures_prevues: d.heures }),
      );
      await updatePlannedCalendar(
        employeeId,
        proposal.year,
        proposal.month,
        Array.from(map.values()).sort((a, b) => a.jour - b.jour),
      );
    }

    if (reelDays.length > 0) {
      let existing: ExistingDay[] = [];
      try {
        const res = await getActualHours(employeeId, proposal.year, proposal.month);
        existing = (res.data?.calendrier_reel ?? []) as ExistingDay[];
      } catch {
        existing = [];
      }
      const map = new Map<number, { jour: number; type: string | null; heures_faites: number | null }>();
      existing.forEach((d) => {
        if (typeof d.jour === 'number') {
          map.set(d.jour, {
            jour: d.jour,
            type: (d.type as string) ?? null,
            heures_faites:
              (d as { heures_faites?: number | null }).heures_faites ?? null,
          });
        }
      });
      reelDays.forEach((d) =>
        map.set(d.jour, { jour: d.jour, type: d.type, heures_faites: d.heures }),
      );
      await updateActualHours(
        employeeId,
        proposal.year,
        proposal.month,
        Array.from(map.values()).sort((a, b) => a.jour - b.jour),
      );
    }
  };

  const handleSave = async () => {
    if (readyRows.length === 0) {
      toast({
        title: 'Rien à enregistrer',
        description: 'Associez au moins un employé identifié à des heures.',
        variant: 'destructive',
      });
      return;
    }
    setIsSaving(true);
    try {
      const tasks = readyRows.map((row) => () => persistEmployee(row));
      await runWithConcurrency(tasks, 4);
      const parts: string[] = [];
      if (natureCounts.prevu > 0) parts.push('prévues');
      if (natureCounts.reel > 0) parts.push('faites');
      toast({
        title: 'Heures enregistrées',
        description: `${readyRows.length} employé(s) — heures ${parts.join(' et ')} mises à jour.`,
      });
      onApplied();
    } catch {
      toast({
        title: 'Erreur',
        description: "L'enregistrement a échoué pour certains employés.",
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Source : {proposal.source}</span>
        <span className="text-muted-foreground">•</span>
        <span>{rows.length} employé(s) détecté(s)</span>
        {unresolvedCount > 0 && (
          <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-700">
            {unresolvedCount} à associer
          </Badge>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
        <span className="text-xs text-muted-foreground">
          Nature détectée :{' '}
          <span className="font-medium text-sky-700">{natureCounts.prevu} prévues</span>
          {' / '}
          <span className="font-medium text-violet-700">{natureCounts.reel} faites</span>
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Tout marquer comme :</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 border-sky-200 text-sky-700 hover:bg-sky-50"
            onClick={() => setAllNature('prevu')}
          >
            Prévues
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 border-violet-200 text-violet-700 hover:bg-violet-50"
            onClick={() => setAllNature('reel')}
          >
            Faites
          </Button>
        </div>
      </div>

      {proposal.warnings.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-900">
          {proposal.warnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}

      <ScrollArea className="max-h-[50vh] pr-2">
        <div className="space-y-3">
          {rows.map((row) => (
            <div key={row.key} className="rounded-lg border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">« {row.rawName} »</span>
                <ConfidenceBadge confidence={row.employeeId ? row.confidence : 'none'} />
                <div className="ml-auto w-[240px]">
                  <Select
                    value={row.employeeId ?? ''}
                    onValueChange={(v) =>
                      updateRow(row.key, { employeeId: v, confidence: 'high' })
                    }
                  >
                    <SelectTrigger className="h-8">
                      <SelectValue placeholder="Associer à un employé" />
                    </SelectTrigger>
                    <SelectContent>
                      {sortedRoster.map((emp) => (
                        <SelectItem key={emp.id} value={emp.id}>
                          {emp.last_name} {emp.first_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {row.warnings.length > 0 && (
                <p className="mt-1 text-xs text-amber-700">{row.warnings.join(' ')}</p>
              )}

              {row.days.length === 0 ? (
                <p className="mt-2 text-xs text-muted-foreground">Aucun jour détecté.</p>
              ) : (
                <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(190px,1fr))] gap-2">
                  {row.days.map((day) => (
                    <div
                      key={`${day.jour}-${day.nature}`}
                      className="flex items-center gap-1 rounded-md border bg-muted/30 px-2 py-1"
                    >
                      <span className="w-5 text-xs font-medium tabular-nums">{day.jour}</span>
                      <NatureToggle
                        nature={day.nature}
                        onChange={(n) => updateDay(row.key, day.jour, { nature: n })}
                      />
                      <Input
                        type="number"
                        step="0.25"
                        min="0"
                        value={day.heures ?? ''}
                        onChange={(e) =>
                          updateDay(row.key, day.jour, {
                            heures: e.target.value === '' ? null : Number(e.target.value),
                          })
                        }
                        className="h-7 w-12 px-1 text-xs"
                        aria-label={`Heures jour ${day.jour}`}
                      />
                      <Select
                        value={day.type}
                        onValueChange={(v) => updateDay(row.key, day.jour, { type: v })}
                      >
                        <SelectTrigger className="h-7 w-[74px] px-1 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {DAY_TYPES.map((t) => (
                            <SelectItem key={t.value} value={t.value} className="text-xs">
                              {t.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <button
                        type="button"
                        onClick={() => removeDay(row.key, day.jour)}
                        className="text-muted-foreground hover:text-destructive"
                        aria-label={`Retirer jour ${day.jour}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>

      <div className="flex items-center justify-between border-t pt-3">
        <Button type="button" variant="ghost" onClick={onBack} disabled={isSaving}>
          Retour
        </Button>
        <Button type="button" onClick={() => void handleSave()} disabled={isSaving}>
          {isSaving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Check className="mr-2 h-4 w-4" />
          )}
          Valider et enregistrer ({readyRows.length})
        </Button>
      </div>
    </div>
  );
}
