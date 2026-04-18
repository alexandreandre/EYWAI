import { useCallback, useEffect, useMemo, useState } from 'react';
import { addDays, addWeeks, format, parseISO, startOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { DuplicationResult, WeekDuplicatePayload } from '@/api/planning';

export interface DuplicateWeekModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: WeekDuplicatePayload) => void;
  sourceWeekStart: string;
  isLoading: boolean;
  result?: DuplicationResult;
}

function mondayOf(iso: string): Date {
  const d = parseISO(iso.slice(0, 10));
  return startOfWeek(d, { weekStartsOn: 1 });
}

function formatWeekRangeFr(mondayIso: string): string {
  const mon = mondayOf(mondayIso);
  const sun = addDays(mon, 6);
  const a = format(mon, "EEEE d/MM", { locale: fr });
  const b = format(sun, "EEEE d/MM/yyyy", { locale: fr });
  return `Semaine du ${a} au ${b}`;
}

function nextMondays(sourceMonday: Date, count: number): string[] {
  const out: string[] = [];
  for (let i = 1; i <= count; i += 1) {
    out.push(format(addWeeks(sourceMonday, i), 'yyyy-MM-dd'));
  }
  return out;
}

function formatConflictRow(c: Record<string, unknown>, index: number): string {
  const keys = Object.keys(c);
  if (keys.length === 0) return `Conflit ${index + 1}`;
  return keys
    .map((k) => `${k}: ${String(c[k])}`)
    .join(' · ')
    .slice(0, 200);
}

export function DuplicateWeekModal({
  open,
  onClose,
  onSubmit,
  sourceWeekStart,
  isLoading,
  result,
}: DuplicateWeekModalProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedTargets, setSelectedTargets] = useState<Set<string>>(new Set());
  const [includeComments, setIncludeComments] = useState(true);
  const [skipAbsentEmployees, setSkipAbsentEmployees] = useState(true);
  const [skipLockedDays, setSkipLockedDays] = useState(true);

  const sourceMonday = useMemo(() => mondayOf(sourceWeekStart), [sourceWeekStart]);
  const twelveMondays = useMemo(() => nextMondays(sourceMonday, 12), [sourceMonday]);

  useEffect(() => {
    if (!open) return;
    if (result) {
      setStep(3);
      return;
    }
    setStep(1);
    setSelectedTargets(new Set());
    setIncludeComments(true);
    setSkipAbsentEmployees(true);
    setSkipLockedDays(true);
  }, [open, result]);

  const toggleTarget = useCallback((iso: string, checked: boolean) => {
    setSelectedTargets((prev) => {
      const next = new Set(prev);
      if (checked) next.add(iso);
      else next.delete(iso);
      return next;
    });
  }, []);

  const selectQuick = useCallback(
    (weeks: number) => {
      const mondays = nextMondays(sourceMonday, weeks);
      setSelectedTargets(new Set(mondays));
    },
    [sourceMonday]
  );

  const targetWeeksSorted = useMemo(
    () => Array.from(selectedTargets).sort(),
    [selectedTargets]
  );

  const handleConfirmDuplicate = () => {
    onSubmit({
      source_week_start: format(sourceMonday, 'yyyy-MM-dd'),
      target_weeks: targetWeeksSorted,
      include_comments: includeComments,
      skip_absent_employees: skipAbsentEmployees,
      skip_locked_days: skipLockedDays,
    });
  };

  const canGoStep2 = targetWeeksSorted.length >= 1;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !isLoading) onClose();
      }}
    >
      <DialogContent className="max-h-[90vh] max-w-lg overflow-hidden sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Dupliquer la semaine</DialogTitle>
          <DialogDescription className="sr-only">
            Assistant en trois étapes pour dupliquer le planning vers d&apos;autres semaines.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className={step >= 1 ? 'font-semibold text-foreground' : ''}>1. Cibles</span>
          <span aria-hidden>→</span>
          <span className={step >= 2 ? 'font-semibold text-foreground' : ''}>2. Options</span>
          <span aria-hidden>→</span>
          <span className={step >= 3 ? 'font-semibold text-foreground' : ''}>3. Confirmation</span>
        </div>

        {step === 1 ? (
          <div className="space-y-4 py-1">
            <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm">
              <p className="font-medium text-foreground">Semaine source</p>
              <p className="text-muted-foreground">{formatWeekRangeFr(sourceWeekStart)}</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" size="sm" onClick={() => selectQuick(4)}>
                4 semaines suivantes
              </Button>
              <Button type="button" variant="secondary" size="sm" onClick={() => selectQuick(8)}>
                8 semaines
              </Button>
            </div>

            <div>
              <Label className="text-sm font-medium">12 prochains lundis</Label>
              <ScrollArea className="mt-2 h-48 rounded-md border pr-3">
                <ul className="space-y-2 p-3">
                  {twelveMondays.map((iso) => (
                    <li key={iso} className="flex items-center gap-3">
                      <Checkbox
                        id={`dup-${iso}`}
                        checked={selectedTargets.has(iso)}
                        onCheckedChange={(v) => toggleTarget(iso, v === true)}
                        disabled={isLoading}
                      />
                      <label htmlFor={`dup-${iso}`} className="text-sm leading-none">
                        {format(parseISO(iso), 'EEEE d MMMM yyyy', { locale: fr })}
                      </label>
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="space-y-4 py-1">
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{targetWeeksSorted.length}</span>{' '}
              semaine(s) sélectionnée(s)
            </p>

            <div className="flex items-center justify-between gap-4 rounded-md border px-3 py-2">
              <div className="space-y-0.5">
                <Label htmlFor="dup-comments">Inclure les commentaires</Label>
                <p className="text-xs text-muted-foreground">Commentaires RH et salarié</p>
              </div>
              <Switch
                id="dup-comments"
                checked={includeComments}
                onCheckedChange={(v) => setIncludeComments(v === true)}
                disabled={isLoading}
              />
            </div>

            <div className="flex items-center justify-between gap-4 rounded-md border px-3 py-2">
              <div className="space-y-0.5">
                <Label htmlFor="dup-absent">Ignorer les salariés absents</Label>
                <p className="text-xs text-muted-foreground">Par défaut : activé</p>
              </div>
              <Switch
                id="dup-absent"
                checked={skipAbsentEmployees}
                onCheckedChange={(v) => setSkipAbsentEmployees(v === true)}
                disabled={isLoading}
              />
            </div>

            <div className="flex items-center justify-between gap-4 rounded-md border px-3 py-2">
              <div className="space-y-0.5">
                <Label htmlFor="dup-locked">Ignorer les jours verrouillés</Label>
                <p className="text-xs text-muted-foreground">Par défaut : activé</p>
              </div>
              <Switch
                id="dup-locked"
                checked={skipLockedDays}
                onCheckedChange={(v) => setSkipLockedDays(v === true)}
                disabled={isLoading}
              />
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="space-y-4 py-1">
            {result ? (
              <>
                <p className="text-sm font-medium">
                  {result.shifts_created} shifts créés, {result.shifts_skipped} ignorés
                </p>
                {result.conflicts.length > 0 ? (
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-10">#</TableHead>
                          <TableHead>Détail</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {result.conflicts.map((c, i) => (
                          <TableRow key={i}>
                            <TableCell className="align-top text-muted-foreground">{i + 1}</TableCell>
                            <TableCell className="max-w-[280px] break-words text-xs">
                              {formatConflictRow(c, i)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : null}
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  Vous allez dupliquer vers <strong>{targetWeeksSorted.length}</strong> semaine(s)
                  cible(s).
                </p>
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
                  La duplication n&apos;est pas réversible automatiquement.
                </div>
              </>
            )}
          </div>
        ) : null}

        <DialogFooter className="flex-col gap-2 sm:flex-col sm:space-x-0">
          {step === 1 ? (
            <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" disabled={isLoading} onClick={() => onClose()}>
                Annuler
              </Button>
              <Button
                type="button"
                disabled={!canGoStep2 || isLoading}
                onClick={() => setStep(2)}
              >
                Suivant
              </Button>
            </div>
          ) : null}

          {step === 2 ? (
            <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" disabled={isLoading} onClick={() => onClose()}>
                Annuler
              </Button>
              <Button type="button" variant="ghost" disabled={isLoading} onClick={() => setStep(1)}>
                Retour
              </Button>
              <Button type="button" disabled={isLoading} onClick={() => setStep(3)}>
                Suivant
              </Button>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              {result ? (
                <Button type="button" variant="default" disabled={isLoading} onClick={() => onClose()}>
                  Fermer
                </Button>
              ) : (
                <>
                  <Button type="button" variant="outline" disabled={isLoading} onClick={() => onClose()}>
                    Annuler
                  </Button>
                  <Button type="button" variant="ghost" disabled={isLoading} onClick={() => setStep(2)}>
                    Retour
                  </Button>
                  <Button type="button" disabled={isLoading} onClick={handleConfirmDuplicate}>
                    {isLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                    ) : null}
                    Confirmer la duplication
                  </Button>
                </>
              )}
            </div>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
