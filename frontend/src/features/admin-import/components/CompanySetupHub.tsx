import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCompanySetupStatus } from '@/features/admin-import/hooks/useCompanySetupStatus';
import { CompanyCombobox } from '@/features/admin-import/components/CompanyCombobox';
import { useCompanyImport } from '@/features/admin-import/context/CompanyImportContext';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { formatEmployeesSetupSummary } from '@/features/admin-import/lib/companySetupSteps';
import { cn } from '@/lib/utils';

type Props = {
  onStartWizard: () => void;
  onNewDsnFolder: () => void;
};

export function CompanySetupHub({ onStartWizard, onNewDsnFolder }: Props) {
  const { companyId, setCompanyId, setActiveTab } = useCompanyImport();

  const { data: status, isFetching, refetch } = useCompanySetupStatus(companyId, {
    refetchInterval: 30_000,
  });

  const showProgress = Boolean(companyId);
  const progressLoading = showProgress && !status;
  const nextAction = status?.next_actions?.[0];

  const progressHint = (() => {
    if (progressLoading) {
      return <span className="text-muted-foreground">Actualisation…</span>;
    }
    if (!status) return null;
    if (status.overall_pct >= 90) {
      return (
        <span className="flex items-center gap-1 text-emerald-700">
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          Prêt pour la paie
        </span>
      );
    }
    if (nextAction) {
      return (
        <button
          type="button"
          className="text-left text-primary hover:underline"
          onClick={() => setActiveTab(nextAction.tab)}
        >
          {nextAction.label}
        </button>
      );
    }
    return <span className="invisible select-none" aria-hidden>—</span>;
  })();

  return (
    <section
      className={cn(
        'rounded-xl border bg-card shadow-sm',
        companyId ? 'border-border' : 'border-dashed border-muted-foreground/30 bg-muted/15',
      )}
    >
      <div className="flex flex-col gap-6 p-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-3 min-w-0 flex-1">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Building2 className="h-4 w-4 shrink-0" />
            Filiale existante
          </div>
          <CompanyCombobox
            value={companyId}
            onChange={setCompanyId}
            className="max-w-lg"
            placeholder="Rechercher une filiale du groupe…"
          />
          {!companyId ? (
            <p className="text-sm text-muted-foreground max-w-xl">
              Choisissez une entreprise déjà dans EYWAI pour compléter imports et paramètres.
              <button
                type="button"
                className="ml-1 text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                onClick={onNewDsnFolder}
              >
                Créer une filiale via DSN
              </button>
            </p>
          ) : (
            <p className="min-h-5 text-sm text-muted-foreground">
              {status ? (
                <>
                  {status.idcc ? `IDCC ${status.idcc} · ` : ''}
                  {status.blocks.dsn.applicable_covered_months}/{status.blocks.dsn.applicable_months} mois DSN ·{' '}
                  {formatEmployeesSetupSummary(status.blocks.employees)}
                </>
              ) : (
                <span className="inline-block h-4 w-full max-w-md animate-pulse rounded bg-muted" />
              )}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          {showProgress && (
            <div className="flex min-h-[72px] min-w-[280px] items-center gap-4 rounded-lg border bg-muted/30 px-4 py-3">
              <div className="w-[4.75rem] shrink-0 text-center">
                {status ? (
                  <p className="text-3xl font-bold tabular-nums leading-none text-foreground">
                    {status.overall_pct}%
                  </p>
                ) : (
                  <div className="mx-auto h-8 w-[4.25rem] animate-pulse rounded bg-muted" />
                )}
                <p className="mt-1 text-xs text-muted-foreground">complété</p>
              </div>
              <div className="min-w-[140px] flex-1 space-y-1.5">
                <Progress
                  value={status?.overall_pct ?? 0}
                  className={cn('h-2', (progressLoading || isFetching) && 'opacity-60')}
                />
                <p className="min-h-8 text-xs leading-4">{progressHint}</p>
              </div>
            </div>
          )}

          <div className="flex flex-col gap-2 sm:items-stretch">
            <Button type="button" size="lg" className="justify-center" onClick={onStartWizard}>
              <Sparkles className="mr-2 h-4 w-4" />
              Parcours guidé
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            {companyId ? (
              <div className="flex min-h-9 gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={progressLoading}
                  onClick={() => refetch()}
                >
                  Actualiser
                </Button>
                <Button type="button" variant="outline" size="sm" asChild disabled={progressLoading}>
                  <Link to={`/super-admin/companies?highlight=${companyId}`}>Fiche entreprise</Link>
                </Button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
