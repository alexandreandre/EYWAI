import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import { CheckCircle2, Loader2, PartyPopper } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import type { RhPendingTaskId, RhPendingTaskItem } from '@/lib/rhPendingTasks';

const STORAGE_KEY = 'eywai.dashboard.priority-day.validated.v1';

type ValidatedByCount = Record<string, number>;

function readValidated(): ValidatedByCount {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      const out: ValidatedByCount = {};
      for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
        if (typeof k === 'string' && typeof v === 'number') out[k] = v;
      }
      return out;
    }
    return {};
  } catch {
    return {};
  }
}

function formatActionCount(n: number): string {
  return n > 99 ? '99+' : String(n);
}

function TaskChip({
  task,
  selected,
  onSelect,
}: {
  task: RhPendingTaskItem;
  selected: boolean;
  onSelect: () => void;
}) {
  const Icon = task.icon;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        selected
          ? 'border-primary bg-primary/10 text-primary font-medium shadow-sm'
          : 'border-border bg-background text-foreground hover:bg-muted/60',
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0 opacity-80" aria-hidden />
      <span className="truncate max-w-[10rem] sm:max-w-none">{task.label}</span>
      <Badge
        variant={selected ? 'default' : 'secondary'}
        className="h-5 min-w-5 px-1.5 tabular-nums text-xs"
      >
        {task.count}
      </Badge>
    </button>
  );
}

export interface DashboardPriorityPanelProps {
  items: RhPendingTaskItem[];
  /** Total aligné sur la pastille sidebar (hors fiches onboarding / signatures si non comptées nav). */
  sidebarTotal: number;
  loading?: boolean;
  refreshing?: boolean;
}

export function DashboardPriorityPanel({
  items,
  sidebarTotal,
  loading = false,
  refreshing = false,
}: DashboardPriorityPanelProps) {
  const [validatedByCount, setValidatedByCount] = useState<ValidatedByCount>(readValidated);
  const [selectedId, setSelectedId] = useState<RhPendingTaskId | null>(null);

  const pendingItems = useMemo(
    () => items.filter((item) => validatedByCount[item.id] !== item.count),
    [items, validatedByCount],
  );

  const selectedTask =
    pendingItems.find((item) => item.id === selectedId) ?? pendingItems[0] ?? null;

  useEffect(() => {
    if (selectedId && pendingItems.some((item) => item.id === selectedId)) return;
    setSelectedId(pendingItems[0]?.id ?? null);
  }, [pendingItems, selectedId]);

  const modulesTotal = items.length;
  const modulesDone = items.filter((item) => validatedByCount[item.id] === item.count).length;
  const modulesProgressPct =
    modulesTotal > 0 ? Math.round((modulesDone / modulesTotal) * 100) : 100;

  const handleValidateAndNext = () => {
    if (!selectedTask) return;
    const next = { ...validatedByCount, [selectedTask.id]: selectedTask.count };
    setValidatedByCount(next);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    const nextPending = items.filter((item) => next[item.id] !== item.count);
    setSelectedId(nextPending[0]?.id ?? null);
  };

  const handleReset = () => {
    setValidatedByCount({});
    sessionStorage.removeItem(STORAGE_KEY);
    setSelectedId(items[0]?.id ?? null);
  };

  if (loading && items.length === 0) {
    return (
      <Card className="border-l-4 border-l-primary shadow-sm">
        <CardContent className="p-5">
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin shrink-0" aria-hidden />
            <p className="text-sm font-medium">Chargement des actions à traiter…</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (items.length === 0 && refreshing) {
    return (
      <Card className="border-l-4 border-l-primary shadow-sm">
        <CardContent className="p-5">
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin shrink-0" aria-hidden />
            <p className="text-sm font-medium">Finalisation du décompte des actions…</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (items.length === 0) {
    return (
      <Card className="border-l-4 border-l-emerald-500 shadow-sm bg-emerald-50/30">
        <CardContent className="p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <PartyPopper className="h-6 w-6 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="text-lg font-semibold text-foreground">Rien à traiter pour l&apos;instant</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Aucune action en attente sur vos modules RH.
                </p>
              </div>
            </div>
            <Button variant="link" className="h-auto p-0 shrink-0" asChild>
              <Link to="/analytics">Voir les indicateurs de pilotage →</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const allBrowsed = pendingItems.length === 0;
  const FocusIcon: LucideIcon | null = selectedTask?.icon ?? null;

  return (
    <Card className="border-l-4 border-l-primary shadow-sm overflow-hidden">
      <CardContent className="p-0">
        <div className="flex flex-col gap-4 p-5 border-b bg-muted/20">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  À traiter aujourd&apos;hui
                </p>
                {refreshing && (
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                    Mise à jour…
                  </span>
                )}
              </div>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold tabular-nums text-destructive">
                    {formatActionCount(sidebarTotal)}
                  </span>
                  <span className="text-base font-semibold text-foreground">
                    action{sidebarTotal > 1 ? 's' : ''} en attente
                  </span>
                </div>
                <span className="text-sm text-muted-foreground">
                  · {modulesTotal} module{modulesTotal > 1 ? 's' : ''} concerné{modulesTotal > 1 ? 's' : ''}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">
                Cliquez un module pour voir le détail et ouvrir le dossier correspondant.
              </p>
            </div>
            {modulesTotal > 0 && (
              <div className="w-full sm:w-48 space-y-1.5 shrink-0">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Parcours du jour</span>
                  <span className="tabular-nums">
                    {modulesDone}/{modulesTotal}
                  </span>
                </div>
                <Progress value={modulesProgressPct} className="h-1.5" />
              </div>
            )}
          </div>

          <div
            className="flex flex-wrap gap-2 -mx-1 px-1 pb-1 max-h-[8.5rem] overflow-y-auto"
            role="tablist"
            aria-label="Modules à traiter"
          >
            {items.map((task) => {
              const done = validatedByCount[task.id] === task.count;
              return (
                <div key={task.id} className="relative">
                  <TaskChip
                    task={task}
                    selected={selectedTask?.id === task.id}
                    onSelect={() => setSelectedId(task.id)}
                  />
                  {done && (
                    <span
                      className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-600 text-white"
                      title="Parcouru"
                    >
                      <CheckCircle2 className="h-3 w-3" aria-hidden />
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="p-5">
          {allBrowsed ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-semibold text-foreground">Parcours terminé pour aujourd&apos;hui</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Vous avez parcouru tous les modules en attente. Revenez-y après traitement effectif,
                  ou réinitialisez le parcours.
                </p>
              </div>
              <Button type="button" variant="secondary" onClick={handleReset}>
                Réinitialiser le parcours
              </Button>
            </div>
          ) : selectedTask && FocusIcon ? (
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-2 min-w-0 flex-1">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Priorité du jour
                </p>
                <div className="flex items-start gap-3">
                  <FocusIcon className="h-6 w-6 text-primary shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <p className="text-lg font-semibold text-foreground leading-tight">
                      {selectedTask.label}
                    </p>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      <span className="font-medium text-foreground tabular-nums">
                        {selectedTask.count}
                      </span>{' '}
                      {selectedTask.count > 1 ? 'dossiers' : 'dossier'} · {selectedTask.hint}
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 shrink-0">
                <Button asChild>
                  <Link to={selectedTask.href}>Ouvrir le module</Link>
                </Button>
                <Button type="button" variant="secondary" onClick={handleValidateAndNext}>
                  Marquer comme parcouru →
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
