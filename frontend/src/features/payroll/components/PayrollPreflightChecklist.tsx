import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Calendar,
  Plane,
  Notebook,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ChevronDown,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRhSidebarTaskBadges } from '@/hooks/useRhSidebarTaskBadges';

interface PreflightStep {
  url: string;
  label: string;
  description: string;
  icon: LucideIcon;
  /** true si l'étape dispose d'un suivi automatique des actions en attente. */
  tracked: boolean;
}

/**
 * Étapes de préparation à réaliser avant de lancer la paie.
 * L'ordre suit le workflow RH ; les compteurs proviennent des badges de la sidebar.
 */
const PREFLIGHT_STEPS: PreflightStep[] = [
  {
    url: '/schedules',
    label: 'Calendrier & temps de travail',
    description: 'Heures et plannings du mois à saisir',
    icon: Calendar,
    tracked: true,
  },
  {
    url: '/leaves',
    label: 'Congés & absences',
    description: 'Demandes en attente de validation',
    icon: Plane,
    tracked: true,
  },
  {
    url: '/expenses',
    label: 'Notes de frais',
    description: 'Dépenses en attente de validation',
    icon: Notebook,
    tracked: true,
  },
];

interface PayrollPreflightChecklistProps {
  className?: string;
  /** Navigation programmée (ex. depuis un modal) — évite le conflit Link + navigate(-1). */
  onStepClick?: (url: string) => void;
}

export function PayrollPreflightChecklist({
  className,
  onStepClick,
}: PayrollPreflightChecklistProps) {
  const { getCount, isLoading: badgesLoading } = useRhSidebarTaskBadges(true);
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);

  const isLoading = badgesLoading;

  const steps = PREFLIGHT_STEPS.map((step) => ({
    ...step,
    count: step.tracked ? getCount(step.url) : 0,
  }));

  const pendingSteps = steps.filter((step) => step.count > 0);
  const totalPending = pendingSteps.reduce((acc, step) => acc + step.count, 0);
  const trackedSteps = steps.filter((step) => step.tracked);
  const okTrackedCount = trackedSteps.filter((step) => step.count === 0).length;
  const allClear = !isLoading && pendingSteps.length === 0;

  const open = manualOpen ?? (!isLoading && (pendingSteps.length > 0 || allClear));

  return (
    <div
      className={cn(
        'rounded-xl border',
        allClear
          ? 'border-success/30 bg-success/5'
          : isLoading
            ? 'border-border bg-muted/30'
            : 'border-amber-300/60 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-950/20',
        className,
      )}
    >
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setManualOpen(!open);
        }}
        className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left"
      >
        <span className="shrink-0">
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden />
          ) : allClear ? (
            <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />
          ) : (
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" aria-hidden />
          )}
        </span>

        <div className="min-w-0 flex-1">
          {isLoading ? (
            <p className="text-sm font-medium text-muted-foreground">
              Vérification du processus de préparation…
            </p>
          ) : allClear ? (
            <>
              <p className="text-sm font-semibold text-foreground">
                Processus de préparation validé
              </p>
              <p className="text-xs text-muted-foreground">
                Toutes les étapes suivies sont à jour — vous pouvez lancer la paie.
              </p>
            </>
          ) : (
            <>
              <p className="text-sm font-semibold text-foreground">
                {totalPending} action{totalPending > 1 ? 's' : ''} en attente sur{' '}
                {pendingSteps.length} étape{pendingSteps.length > 1 ? 's' : ''}
              </p>
              <p className="text-xs text-muted-foreground">
                Vous pouvez lancer la paie, mais vérifiez ces points en amont.
              </p>
            </>
          )}
        </div>

        {!isLoading && (
          <span className="shrink-0 text-muted-foreground">
            {open ? (
              <ChevronDown className="h-4 w-4" aria-hidden />
            ) : (
              <ChevronRight className="h-4 w-4" aria-hidden />
            )}
          </span>
        )}
      </button>

      {open && !isLoading && (
        <div className="space-y-1.5 px-3 pb-3">
          {!allClear && (
            <p className="px-1 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {okTrackedCount}/{trackedSteps.length} étapes suivies à jour
            </p>
          )}
          <ul className="space-y-1.5">
            {steps.map((step) => {
              const Icon = step.icon;
              const hasPending = step.count > 0;
              const rowClassName = cn(
                'flex w-full items-center gap-3 rounded-lg border bg-background px-3 py-2 text-left transition-colors hover:bg-muted/60',
                hasPending ? 'border-amber-300/70' : 'border-border',
              );
              const rowContent = (
                <>
                  <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium leading-tight">{step.label}</p>
                    <p className="truncate text-xs text-muted-foreground">{step.description}</p>
                  </div>
                  {hasPending ? (
                    <span className="shrink-0 rounded-md bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                      {step.count} à traiter
                    </span>
                  ) : (
                    <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-success">
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                      À jour
                    </span>
                  )}
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                </>
              );

              return (
                <li key={step.url}>
                  {onStepClick ? (
                    <button
                      type="button"
                      onClick={() => onStepClick(step.url)}
                      className={rowClassName}
                    >
                      {rowContent}
                    </button>
                  ) : (
                    <Link to={step.url} className={rowClassName}>
                      {rowContent}
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
