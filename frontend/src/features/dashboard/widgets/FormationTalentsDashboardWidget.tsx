import { useNavigate } from 'react-router-dom';
import { Loader2, GraduationCap } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useFormationDashboardQueries } from '@/hooks/queries/useFormationDashboardQueries';
import type { TrainingBudgetAlertLevel } from '@/api/trainingBudget';

function FormationTalentsCellLoader() {
  return (
    <div className="mt-3 flex min-h-[40px] items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden />
    </div>
  );
}

function countBadgeClass(n: number, tone: 'red' | 'orange') {
  if (n <= 0) return 'bg-muted text-muted-foreground';
  return tone === 'red' ? 'bg-red-600 text-white' : 'bg-orange-500 text-white';
}

function budgetGaugeFillClass(level: TrainingBudgetAlertLevel) {
  if (level === 'critical') return 'bg-red-500';
  if (level === 'warning') return 'bg-orange-500';
  return 'bg-emerald-500';
}

export function FormationTalentsDashboardWidget() {
  const navigate = useNavigate();
  const year = new Date().getFullYear();
  const { certs, overdue, budget, achievement } = useFormationDashboardQueries(year);

  const expired = certs.isError ? null : (certs.data?.expired ?? 0);
  const expiring = certs.isError ? null : (certs.data?.expiring ?? 0);
  const overdueCount = overdue.isError ? null : (overdue.data?.count ?? 0);
  const pct =
    budget.isError || !budget.data
      ? null
      : Math.min(100, Math.max(0, budget.data.consumption_pct));
  const alertLevel: TrainingBudgetAlertLevel | null = budget.isError
    ? null
    : (budget.data?.alert_level ?? 'none');
  const rate =
    achievement.isError || achievement.data?.rate == null
      ? null
      : achievement.data.rate;

  const rateColor =
    rate == null
      ? 'text-muted-foreground'
      : rate >= 80
        ? 'text-emerald-600'
        : rate >= 50
          ? 'text-orange-600'
          : 'text-red-600';

  return (
    <Card className="border-primary/15 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <GraduationCap className="h-5 w-5 text-primary" />
          Formation &amp; Talents
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Indicateurs Pack Talent — cliquez pour ouvrir le module.
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <button
            type="button"
            onClick={() =>
              navigate({ pathname: '/formation', hash: 'conformite', search: '?sub=habilitations' })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Habilitations expirées</span>
            {certs.isLoading ? (
              <FormationTalentsCellLoader />
            ) : (
              <div className="mt-2 flex flex-1 flex-col justify-center gap-2">
                <Badge
                  className={
                    expired == null ? 'bg-muted text-muted-foreground' : countBadgeClass(expired, 'red')
                  }
                >
                  {expired == null ? '—' : expired}
                </Badge>
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              navigate({ pathname: '/formation', hash: 'conformite', search: '?sub=habilitations' })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Habilitations à échéance</span>
            {certs.isLoading ? (
              <FormationTalentsCellLoader />
            ) : (
              <div className="mt-2 flex flex-1 flex-col justify-center gap-2">
                <Badge
                  className={
                    expiring == null
                      ? 'bg-muted text-muted-foreground'
                      : countBadgeClass(expiring, 'orange')
                  }
                >
                  {expiring == null ? '—' : expiring}
                </Badge>
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              navigate({ pathname: '/formation', hash: 'formations', search: '?sub=budget' })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Budget formation consommé</span>
            {budget.isLoading ? (
              <FormationTalentsCellLoader />
            ) : pct == null || alertLevel == null ? (
              <p className="mt-3 text-sm text-muted-foreground">—</p>
            ) : (
              <div className="mt-3 space-y-1">
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full transition-all ${budgetGaugeFillClass(alertLevel)}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-xs tabular-nums text-muted-foreground">{pct.toFixed(0)} %</p>
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              navigate({ pathname: '/formation', hash: 'conformite', search: '?sub=obligations' })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Retard entretien prof.</span>
            {overdue.isLoading ? (
              <FormationTalentsCellLoader />
            ) : (
              <div className="mt-2 flex flex-1 flex-col justify-center gap-2">
                <Badge
                  className={
                    overdueCount == null
                      ? 'bg-muted text-muted-foreground'
                      : countBadgeClass(overdueCount, 'red')
                  }
                >
                  {overdueCount == null ? '—' : overdueCount}
                </Badge>
              </div>
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              navigate({ pathname: '/formation', hash: 'developpement', search: '?sub=objectifs' })
            }
            className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
          >
            <span className="text-xs font-medium text-muted-foreground">Taux d&apos;atteinte objectifs</span>
            {achievement.isLoading ? (
              <FormationTalentsCellLoader />
            ) : (
              <p className={`mt-3 text-2xl font-bold tabular-nums ${rateColor}`}>
                {rate == null ? '—' : `${rate.toFixed(0)} %`}
              </p>
            )}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
