import { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
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
import { Progress } from '@/components/ui/progress';
import {
  purgeAllCompanyEmployees,
  type DeleteAllCompanyEmployeesResult,
} from '@/api/adminCompanies';
import {
  purgeEmployeesEventLabel,
  purgeEmployeesProgressPercent,
  type PurgeEmployeeStep,
  type PurgeEmployeesStreamEvent,
} from '@/lib/purgeEmployeesProgress';
import { showErrorToast } from '@/lib/errorMessages';
import { cn } from '@/lib/utils';

type Phase = 'confirm' | 'running' | 'done' | 'empty';

type DeleteAllEmployeesDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyId: string;
  companyName: string;
  employeesCount: number;
  onCompleted: (result: DeleteAllCompanyEmployeesResult) => void;
};

const LOG_MAX = 12;

export function DeleteAllEmployeesDialog({
  open,
  onOpenChange,
  companyId,
  companyName,
  employeesCount,
  onCompleted,
}: DeleteAllEmployeesDialogProps) {
  const [phase, setPhase] = useState<Phase>('confirm');
  const [progress, setProgress] = useState(0);
  const [employeeIndex, setEmployeeIndex] = useState(0);
  const [employeeTotal, setEmployeeTotal] = useState(0);
  const [currentEmployeeName, setCurrentEmployeeName] = useState<string | null>(null);
  const [currentStepLabel, setCurrentStepLabel] = useState<string | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [result, setResult] = useState<DeleteAllCompanyEmployeesResult | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  const resetState = useCallback(() => {
    setPhase('confirm');
    setProgress(0);
    setEmployeeIndex(0);
    setEmployeeTotal(0);
    setCurrentEmployeeName(null);
    setCurrentStepLabel(null);
    setLogLines([]);
    setResult(null);
    abortRef.current = null;
  }, []);

  useEffect(() => {
    if (!open) {
      abortRef.current?.abort();
      resetState();
      return;
    }
    if (employeesCount === 0) {
      setPhase('empty');
    }
  }, [open, resetState, employeesCount]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [logLines]);

  const appendLog = (line: string) => {
    setLogLines((prev) => [...prev.slice(-(LOG_MAX - 1)), line]);
  };

  const handleStreamEvent = (event: PurgeEmployeesStreamEvent) => {
    const label = purgeEmployeesEventLabel(event);
    if (label) appendLog(label);

    if (event.event === 'started') {
      setEmployeeTotal(event.total);
      if (event.total === 0) {
        setProgress(100);
      }
    }

    if (
      event.event === 'employee_started' ||
      event.event === 'step' ||
      event.event === 'employee_done' ||
      event.event === 'employee_failed'
    ) {
      setEmployeeIndex(event.index);
      setEmployeeTotal(event.total);
      setCurrentEmployeeName(event.employee_name);

      if (event.event === 'step') {
        setCurrentStepLabel(event.label);
        setProgress(
          purgeEmployeesProgressPercent(event.total, event.index, event.step),
        );
      } else if (event.event === 'employee_done' || event.event === 'employee_failed') {
        setCurrentStepLabel(null);
        setProgress(purgeEmployeesProgressPercent(event.total, event.index, undefined, true));
      } else if (event.event === 'employee_started') {
        setCurrentStepLabel('Démarrage…');
        setProgress(purgeEmployeesProgressPercent(event.total, event.index));
      }
    }

    if (event.event === 'completed') {
      setResult(event.result);
      setProgress(100);
      setPhase('done');
    }
  };

  const startPurge = async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase('running');
    setProgress(0);
    setLogLines([]);
    setResult(null);

    try {
      const purgeResult = await purgeAllCompanyEmployees(companyId, {
        signal: controller.signal,
        onEvent: handleStreamEvent,
      });
      setResult(purgeResult);
      setPhase('done');
      setProgress(100);
      onCompleted(purgeResult);
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return;
      }
      showErrorToast(error, {
        title: 'Suppression impossible',
        fallback: 'La suppression des employés a échoué. Réessayez.',
      });
      setPhase('confirm');
    }
  };

  const handleOpenChange = (next: boolean) => {
    if (!next && phase === 'running') return;
    onOpenChange(next);
  };

  const handleCloseDone = () => {
    onOpenChange(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {phase === 'empty' ? 'Aucun salarié' : 'Supprimer tous les employés'}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {phase === 'empty' ? (
              <>
                Tous les employés de <strong>{companyName}</strong> ont déjà été supprimés.
                L&apos;entreprise et les utilisateurs RH sont conservés.
              </>
            ) : phase === 'done' ? (
              <>
                Purge terminée pour <strong>{companyName}</strong>.
              </>
            ) : (
              <>
                Cette action est irréversible. Tous les salariés de{' '}
                <strong>{companyName}</strong> et leurs données seront supprimés
                définitivement. L&apos;entreprise et les utilisateurs RH ne sont pas
                concernés.
              </>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {phase === 'empty' && (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/80 p-4 text-sm text-emerald-900">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden />
            <span>0 employé à supprimer.</span>
          </div>
        )}

        {phase === 'confirm' && (
          <div className="rounded-lg bg-muted p-4 text-sm">
            <p className="font-medium">{employeesCount} employé(s) concerné(s)</p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-muted-foreground">
              <li>Bulletins de paie et saisies mensuelles</li>
              <li>Absences, plannings et pointages</li>
              <li>Contrats, documents et processus de sortie</li>
              <li>Comptes collaborateurs sans autre accès entreprise</li>
            </ul>
          </div>
        )}

        {(phase === 'running' || phase === 'done') && (
          <div className="space-y-3 rounded-lg border bg-muted/30 p-4" role="status" aria-live="polite">
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="font-medium text-foreground">
                {phase === 'running' ? 'Suppression en cours…' : 'Résumé'}
              </span>
              {employeeTotal > 0 && (
                <span className="tabular-nums text-muted-foreground">
                  {phase === 'done' ? employeeTotal : employeeIndex} / {employeeTotal} salarié
                  {employeeTotal !== 1 ? 's' : ''}
                </span>
              )}
            </div>

            <Progress value={progress} className="h-2" />

            <div className="space-y-0.5 text-sm">
              {currentEmployeeName && phase === 'running' && (
                <p className="font-medium text-foreground truncate">{currentEmployeeName}</p>
              )}
              {currentStepLabel && phase === 'running' && (
                <p className="text-muted-foreground">{currentStepLabel}</p>
              )}
              {phase === 'done' && result && (
                <p
                  className={cn(
                    'flex items-center gap-2',
                    result.failed.length > 0 ? 'text-amber-800' : 'text-green-700',
                  )}
                >
                  {result.failed.length > 0 ? (
                    <XCircle className="h-4 w-4 shrink-0" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                  )}
                  {result.removed_count} supprimé{result.removed_count !== 1 ? 's' : ''}
                  {result.failed.length > 0
                    ? `, ${result.failed.length} échec${result.failed.length !== 1 ? 's' : ''}`
                    : ''}
                </p>
              )}
            </div>

            {logLines.length > 0 && (
              <div className="max-h-36 overflow-y-auto rounded-md border bg-background/80 p-2 font-mono text-xs text-muted-foreground">
                {logLines.map((line, i) => (
                  <div key={`${i}-${line}`} className="leading-relaxed">
                    {line}
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            )}
          </div>
        )}

        <AlertDialogFooter>
          {phase === 'empty' && (
            <Button onClick={handleCloseDone} className="w-full sm:w-auto">
              Fermer
            </Button>
          )}
          {phase === 'confirm' && (
            <>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <Button
                variant="destructive"
                disabled={employeesCount === 0}
                onClick={() => void startPurge()}
              >
                Supprimer définitivement
              </Button>
            </>
          )}
          {phase === 'running' && (
            <Button disabled className="w-full sm:w-auto">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Suppression… {progress}%
            </Button>
          )}
          {phase === 'done' && (
            <Button onClick={handleCloseDone} className="w-full sm:w-auto">
              Fermer
            </Button>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
