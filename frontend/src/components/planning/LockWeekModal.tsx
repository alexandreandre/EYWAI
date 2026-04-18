import { useEffect, useState } from 'react';
import { addDays, format, parseISO, startOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Loader2 } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export interface LockWeekModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (reason?: string) => void;
  weekStart: string;
  shiftsCount: number;
  totalHours: number;
  employeesCount: number;
  isLoading: boolean;
}

function weekRangeLabel(weekStartIso: string): string {
  const mon = startOfWeek(parseISO(weekStartIso.slice(0, 10)), { weekStartsOn: 1 });
  const sun = addDays(mon, 6);
  const a = format(mon, 'd/MM', { locale: fr });
  const b = format(sun, 'd/MM/yyyy', { locale: fr });
  return `Semaine du ${a} au ${b}`;
}

export function LockWeekModal({
  open,
  onClose,
  onConfirm,
  weekStart,
  shiftsCount,
  totalHours,
  employeesCount,
  isLoading,
}: LockWeekModalProps) {
  const [reason, setReason] = useState('');

  useEffect(() => {
    if (open) setReason('');
  }, [open]);

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !isLoading) onClose();
      }}
    >
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>Verrouiller la semaine</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-1 text-left text-sm text-foreground">
              <p className="font-medium text-foreground">{weekRangeLabel(weekStart)}</p>
              <p className="text-muted-foreground">
                {shiftsCount} shifts · {totalHours.toFixed(1)}h planifiées · {employeesCount} salariés
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-3 text-sm">
          <div className="rounded-md border border-orange-300 bg-amber-50 p-3 text-amber-950 dark:border-orange-800 dark:bg-amber-950/40 dark:text-amber-50">
            Une fois verrouillée, cette semaine ne pourra plus être modifiée sans déverrouillage. Les
            heures seront automatiquement transmises au module Paie.
          </div>
          <div className="space-y-2">
            <Label htmlFor="lock-week-reason">Motif du verrouillage — optionnel</Label>
            <Input
              id="lock-week-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Ex. clôture paie, validation manager…"
              disabled={isLoading}
            />
          </div>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isLoading}>Annuler</AlertDialogCancel>
          <Button
            type="button"
            variant="destructive"
            disabled={isLoading}
            onClick={() => onConfirm(reason.trim() || undefined)}
          >
            {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
            Verrouiller
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
