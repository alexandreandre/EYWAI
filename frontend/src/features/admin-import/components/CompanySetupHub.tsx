import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Loader2,
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

  const { data: status, isLoading, isFetching, refetch } = useCompanySetupStatus(companyId, {
    refetchInterval: 30_000,
  });

  const nextAction = status?.next_actions?.[0];

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
          ) : status ? (
            <p className="text-sm text-muted-foreground">
              {status.idcc ? `IDCC ${status.idcc} · ` : ''}
              {status.blocks.dsn.applicable_covered_months}/{status.blocks.dsn.applicable_months} mois DSN ·{' '}
              {formatEmployeesSetupSummary(status.blocks.employees)}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          {companyId && (
            <div className="flex items-center gap-4 rounded-lg border bg-muted/30 px-4 py-3 min-w-[200px]">
              {isLoading && !status ? (
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              ) : status ? (
                <>
                  <div className="text-center">
                    <p className="text-3xl font-bold tabular-nums leading-none text-foreground">
                      {status.overall_pct}%
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">complété</p>
                  </div>
                  <div className="flex-1 space-y-1.5 min-w-[120px]">
                    <Progress value={status.overall_pct} className="h-2" />
                    {isFetching ? (
                      <p className="text-xs text-muted-foreground">Actualisation…</p>
                    ) : status.overall_pct >= 90 ? (
                      <p className="text-xs text-emerald-700 flex items-center gap-1">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Prêt pour la paie
                      </p>
                    ) : nextAction ? (
                      <button
                        type="button"
                        className="text-xs text-left text-primary hover:underline"
                        onClick={() => setActiveTab(nextAction.tab)}
                      >
                        {nextAction.label}
                      </button>
                    ) : null}
                  </div>
                </>
              ) : null}
            </div>
          )}

          <div className="flex flex-col gap-2 sm:items-stretch">
            <Button type="button" size="lg" className="justify-center" onClick={onStartWizard}>
              <Sparkles className="mr-2 h-4 w-4" />
              Parcours guidé
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            {companyId && status ? (
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => refetch()}>
                  Actualiser
                </Button>
                <Button type="button" variant="outline" size="sm" asChild>
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
