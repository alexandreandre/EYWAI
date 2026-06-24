import { Check, Circle, Loader2 } from 'lucide-react';
import type { PlanningImportCommitProgress } from '@/api/adminImport';
import { SharkFinBootProgress } from '@/components/SharkFinBootProgress';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type Props = {
  progress: PlanningImportCommitProgress | null | undefined;
  status: 'committing' | 'failed';
  errorMessage?: string | null;
  onDismiss?: () => void;
};

function employeeState(
  name: string,
  progress: PlanningImportCommitProgress | null | undefined,
): 'done' | 'current' | 'pending' {
  const completed = new Set(progress?.completed_labels ?? []);
  if (completed.has(name)) return 'done';
  if (progress?.label === name && (progress?.phase === 'employee' || progress?.phase === 'starting')) {
    return 'current';
  }
  const queue = progress?.employees_queue ?? [];
  const done = progress?.done ?? 0;
  const currentName = queue[done];
  if (currentName === name) return 'current';
  return 'pending';
}

export function PlanningImportCommitOverlay({ progress, status, errorMessage, onDismiss }: Props) {
  const queue = progress?.employees_queue ?? [];
  const hasQueue = queue.length > 0;
  const determinate = Boolean(progress && progress.total > 0);
  const percent = progress?.percent ?? 0;

  return (
    <div
      className="absolute inset-0 z-20 flex items-start justify-center overflow-y-auto rounded-lg bg-background/95 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="planning-commit-title"
      aria-busy={status === 'committing'}
    >
      <div className="w-full max-w-md space-y-4 py-2">
        <div className="space-y-1 text-center sm:text-left">
          <div className="flex items-center justify-center gap-2 sm:justify-start">
            {status === 'committing' ? (
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
            ) : null}
            <h3 id="planning-commit-title" className="text-sm font-semibold">
              {status === 'failed'
                ? "Enregistrement interrompu"
                : 'Enregistrement du calendrier prévu…'}
            </h3>
          </div>
          <p className="text-xs text-muted-foreground">
            {status === 'failed'
              ? errorMessage ?? "Une erreur est survenue pendant l'import."
              : 'Chaque salarié est enregistré mois par mois. Ne fermez pas cette fenêtre.'}
          </p>
        </div>

        {status === 'committing' ? (
          <>
            <div className="space-y-2 rounded-md border bg-muted/20 p-3">
              <SharkFinBootProgress value={percent} determinate={determinate} />
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="min-w-0 truncate text-muted-foreground">
                  {progress?.phase_label ?? 'Préparation…'}
                  {progress?.label ? (
                    <span className="text-foreground/80"> — {progress.label}</span>
                  ) : null}
                </span>
                {determinate ? (
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {progress?.done}/{progress?.total} • {percent}%
                  </span>
                ) : null}
              </div>
            </div>

            {hasQueue ? (
              <div className="rounded-md border">
                <p className="border-b px-3 py-2 text-xs font-medium text-muted-foreground">
                  Salariés ({progress?.done ?? 0}/{progress?.total ?? queue.length})
                </p>
                <ul className="max-h-52 overflow-y-auto px-1 py-1">
                  {queue.map((name) => {
                    const state = employeeState(name, progress);
                    return (
                      <li
                        key={name}
                        className={cn(
                          'flex items-center gap-2 rounded-sm px-2 py-1.5 text-xs',
                          state === 'current' && 'bg-primary/5 text-foreground',
                          state === 'done' && 'text-muted-foreground',
                          state === 'pending' && 'text-muted-foreground/70',
                        )}
                      >
                        {state === 'done' ? (
                          <Check className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                        ) : state === 'current' ? (
                          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
                        ) : (
                          <Circle className="h-3.5 w-3.5 shrink-0 opacity-40" />
                        )}
                        <span className="truncate">{name}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : null}
          </>
        ) : null}

        {status === 'failed' && onDismiss ? (
          <div className="flex justify-center sm:justify-start">
            <Button type="button" size="sm" variant="outline" onClick={onDismiss}>
              Fermer
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
