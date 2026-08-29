import { useEffect, useState } from 'react';
import { Check, Loader2, Sparkles } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  AI_FILL_STEPS,
  progressAt,
  stepStateAt,
} from './aiFillProgressModel';

const DEFAULT_EXPECTED_MS = 18_000;
const TICK_MS = 200;
const GRID_COLS = 7;
const GRID_ROWS = 3;

type AssistedFillProgressProps = {
  expectedMs?: number;
  className?: string;
};

function StepMarker({ state }: { state: ReturnType<typeof stepStateAt> }) {
  if (state === 'done') {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
        <Check className="h-3 w-3" strokeWidth={2.5} aria-hidden />
      </span>
    );
  }
  if (state === 'active') {
    return (
      <span className="relative flex h-5 w-5 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-2.5 w-2.5 animate-ping rounded-full bg-primary/50 motion-reduce:hidden" />
        <Loader2
          className="h-3.5 w-3.5 animate-spin text-primary motion-reduce:animate-none"
          aria-hidden
        />
      </span>
    );
  }
  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center" aria-hidden>
      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
    </span>
  );
}

export function AssistedFillProgress({
  expectedMs = DEFAULT_EXPECTED_MS,
  className,
}: AssistedFillProgressProps) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const id = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt);
    }, TICK_MS);
    return () => window.clearInterval(id);
  }, []);

  const progress = progressAt(elapsedMs, expectedMs);
  const percentLabel = Math.round(progress);

  return (
    <div
      className={cn(
        'flex h-full min-h-0 flex-col justify-center gap-5 py-2',
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="flex items-center gap-3">
        <span className="relative flex h-10 w-10 shrink-0 items-center justify-center">
          <span className="absolute inset-0 rounded-full bg-primary/15 animate-pulse motion-reduce:animate-none" />
          <span className="absolute inset-1 rounded-full bg-primary/10 animate-pulse-glow motion-reduce:animate-none" />
          <Sparkles className="relative h-5 w-5 text-primary" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">Analyse de la consigne</p>
          <p className="text-xs text-muted-foreground">
            Cela prend généralement 10 à 30 secondes.
          </p>
        </div>
      </div>

      <ol className="space-y-2">
        {AI_FILL_STEPS.map((step, index) => {
          const state = stepStateAt(progress, index);
          return (
            <li
              key={step.label}
              className={cn(
                'flex items-center gap-2.5 text-sm',
                state === 'active' && 'font-medium text-foreground',
                state === 'done' && 'text-foreground/80',
                state === 'pending' && 'text-muted-foreground',
              )}
            >
              <StepMarker state={state} />
              <span>{step.label}</span>
            </li>
          );
        })}
      </ol>

      <div className="space-y-1.5">
        <Progress value={progress} className="h-1.5" />
        <p className="text-right text-[11px] tabular-nums text-muted-foreground">
          {percentLabel} %
        </p>
      </div>

      <div
        className="grid grid-cols-7 gap-1.5"
        aria-hidden
      >
        {Array.from({ length: GRID_COLS * GRID_ROWS }, (_, i) => {
          const col = i % GRID_COLS;
          const row = Math.floor(i / GRID_COLS);
          const weekend = col >= 5;
          return (
            <Skeleton
              key={i}
              className={cn(
                'rounded-sm motion-reduce:animate-none',
                weekend ? 'h-5 opacity-50' : 'h-7',
              )}
              style={{ animationDelay: `${(col + row) * 70}ms` }}
            />
          );
        })}
      </div>

      <p className="text-xs text-muted-foreground">
        Vous pourrez ajuster chaque jour avant d&apos;enregistrer.
      </p>
    </div>
  );
}
