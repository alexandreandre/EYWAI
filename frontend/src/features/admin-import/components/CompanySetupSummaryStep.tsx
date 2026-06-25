import {
  AlertCircle,
  CheckCircle2,
  Circle,
  ExternalLink,
  Loader2,
  MinusCircle,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import type { CompanySetupNextAction, CompanySetupStatus } from '@/api/adminImport';
import { useCompanySetupStatus } from '@/features/admin-import/hooks/useCompanySetupStatus';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useCompanyImport } from '@/features/admin-import/context/CompanyImportContext';
import {
  COMPANY_SETUP_STEPS,
  getCompanySetupStepState,
  getCompanySetupStepSummaryLine,
  type CompanySetupStepState,
} from '@/features/admin-import/lib/companySetupSteps';
import {
  isSetupStepValidated,
  loadValidatedSetupSteps,
} from '@/features/admin-import/lib/companySetupValidatedSteps';
import { PayrollSourceBadge } from '@/components/analytics/PayrollSourceBadge';
import { cn } from '@/lib/utils';
import { useMemo } from 'react';

type Props = {
  companyId: string;
  validatedSteps?: ReadonlySet<string>;
  onOpenTab?: (tab: string) => void;
  onGoToStep?: (stepId: string) => void;
};

function StepStatusIcon({ state }: { state: CompanySetupStepState }) {
  if (state === 'done') {
    return <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />;
  }
  if (state === 'blocked') {
    return <MinusCircle className="h-4 w-4 shrink-0 text-muted-foreground/60" aria-hidden />;
  }
  return <Circle className="h-4 w-4 shrink-0 text-amber-500" aria-hidden />;
}

function stepStatusLabel(state: CompanySetupStepState, optional = false): string {
  if (state === 'done') return 'Complet';
  if (state === 'blocked') return 'Bloqué';
  return optional ? 'Optionnel' : 'À faire';
}

function BoolBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
        ok ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-900',
      )}
    >
      {label}
    </span>
  );
}

function PayrollParamLine({
  label,
  value,
  format,
}: {
  label: string;
  value: number | string | null | undefined;
  format?: (v: number | string) => string;
}) {
  const missing = value == null || value === '';
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('tabular-nums', missing && 'text-amber-700')}>
        {missing ? '—' : format ? format(value as number | string) : String(value)}
      </span>
    </div>
  );
}

export function CompanySetupSummaryStep({
  companyId,
  validatedSteps: validatedStepsProp,
  onOpenTab,
  onGoToStep,
}: Props) {
  const { openWizard, setWizardStep } = useCompanyImport();
  const { data, isLoading, refetch, isFetching } = useCompanySetupStatus(companyId);

  const validatedSteps = useMemo(() => {
    if (validatedStepsProp) return validatedStepsProp;
    return companyId ? loadValidatedSetupSteps(companyId) : new Set<string>();
  }, [validatedStepsProp, companyId]);

  if (!companyId) {
    return <p className="text-sm text-muted-foreground">Sélectionnez une entreprise.</p>;
  }

  if (isLoading && !data) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Calcul du bilan…
      </div>
    );
  }

  if (!data) {
    return (
      <p className="text-sm text-muted-foreground">
        Impossible de charger le bilan pour cette filiale.
      </p>
    );
  }

  const handleAction = (action: CompanySetupNextAction) => {
    if (onOpenTab) onOpenTab(action.tab);
    else openWizard(action.tab === 'params' ? 'params' : action.tab);
  };

  const goToStep = (stepId: string) => {
    if (onGoToStep) onGoToStep(stepId);
    else {
      setWizardStep(stepId);
      openWizard(stepId);
    }
  };

  const dsnGaps = data.blocks.dsn.gaps ?? [];
  const readyForPayroll = data.overall_pct >= 90 && data.next_actions.length === 0;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Bilan — {data.company_name}</CardTitle>
          <CardDescription>
            {data.idcc ? `IDCC ${data.idcc} · ` : ''}
            Synthèse du parcours guidé
            {isFetching ? ' · actualisation…' : ''}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Complétude globale</span>
              <span className="font-semibold tabular-nums">{data.overall_pct}%</span>
            </div>
            <Progress value={data.overall_pct} className="h-2.5" />
            {readyForPayroll ? (
              <p className="flex items-center gap-1.5 text-sm text-emerald-700">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                Configuration essentielle prête pour la première paie.
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                {data.next_actions.length} action(s) recommandée(s) ci-dessous.
              </p>
            )}
          </div>
          {data.payroll_kpi ? (
            <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">Masse salariale (M-1)</span>
                <PayrollSourceBadge
                  source={data.payroll_kpi.source}
                  sourceLabel={data.payroll_kpi.source_label}
                  partial={data.payroll_kpi.partial}
                />
              </div>
              {data.payroll_kpi.ready ? (
                <p className="text-sm tabular-nums">
                  {new Intl.NumberFormat('fr-FR', {
                    style: 'currency',
                    currency: 'EUR',
                    maximumFractionDigits: 0,
                  }).format(data.payroll_kpi.gross)}
                  <span className="text-muted-foreground text-xs ml-2">
                    · période {data.payroll_kpi.period}
                  </span>
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Importez une DSN mensuelle pour afficher la masse déclarée sur le dashboard RH.
                </p>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Étapes du parcours</CardTitle>
          <CardDescription>
            État métier et validation manuelle (coche verte dans la sidebar).
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <ul className="divide-y">
            <li className="flex items-start gap-3 px-4 py-3">
              <CheckCircle2
                className={cn(
                  'mt-0.5 h-4 w-4 shrink-0',
                  companyId ? 'text-emerald-600' : 'text-muted-foreground/50',
                )}
              />
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">Préparation</span>
                  <span className="text-xs text-muted-foreground">Filiale sélectionnée</span>
                </div>
                <p className="text-xs text-muted-foreground">{data.company_name}</p>
              </div>
            </li>
            {COMPANY_SETUP_STEPS.map((step) => {
              const state = getCompanySetupStepState(step.id, data);
              const validated = isSetupStepValidated(step.id, companyId, validatedSteps);
              const optional = step.id === 'planning';
              return (
                <li key={step.id} className="flex items-start gap-3 px-4 py-3">
                  <StepStatusIcon state={state} />
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">{step.label}</span>
                      <span
                        className={cn(
                          'rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                          state === 'done'
                            ? 'bg-emerald-50 text-emerald-800'
                            : state === 'blocked'
                              ? 'bg-muted text-muted-foreground'
                              : optional
                                ? 'bg-sky-50 text-sky-800'
                                : 'bg-amber-50 text-amber-900',
                        )}
                      >
                        {stepStatusLabel(state, optional)}
                      </span>
                      {validated ? (
                        <span className="text-[10px] text-emerald-700">Validée</span>
                      ) : null}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {getCompanySetupStepSummaryLine(step.id, data)}
                    </p>
                    {state !== 'blocked' ? (
                      <Button
                        type="button"
                        variant="link"
                        size="sm"
                        className="h-auto p-0 text-xs"
                        onClick={() => goToStep(step.id)}
                      >
                        Revoir cette étape
                      </Button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">DSN &amp; effectifs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <PayrollParamLine
              label="Couverture DSN"
              value={`${data.blocks.dsn.applicable_covered_months}/${data.blocks.dsn.applicable_months} mois`}
            />
            <PayrollParamLine label="Dernier mois importé" value={data.blocks.dsn.last_period} />
            <PayrollParamLine
              label="Mois attendu"
              value={data.blocks.dsn.expected_last_period}
            />
            <PayrollParamLine label="Salariés actifs" value={data.blocks.employees.total} />
            <PayrollParamLine
              label="Fiches complètes"
              value={`${data.blocks.employees.profile_complete_pct}%`}
            />
            <PayrollParamLine
              label="RIB manquants"
              value={data.blocks.employees.missing_rib_count}
            />
            {dsnGaps.length > 0 ? (
              <div className="mt-2 rounded-md border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-950">
                <p className="flex items-center gap-1.5 font-medium">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  {dsnGaps.length} mois DSN manquant(s)
                </p>
                <p className="mt-1 text-amber-900/90">{dsnGaps.slice(0, 6).join(', ')}</p>
                {dsnGaps.length > 6 ? (
                  <p className="mt-0.5 text-amber-800/80">… et {dsnGaps.length - 6} autre(s)</p>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Paramètres &amp; imports</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex flex-wrap gap-1.5">
              <BoolBadge ok={data.blocks.leave_settings.configured} label="Congés / RTT" />
              <BoolBadge ok={data.blocks.payroll_params.taux_at_mp != null} label="AT/MP" />
              <BoolBadge
                ok={data.blocks.payroll_params.paie_jour_de_fin != null}
                label="Calendrier paie"
              />
              <BoolBadge ok={data.blocks.modulation.configured} label="Modulation" />
              <BoolBadge ok={data.blocks.jei.configured} label="JEI" />
              <BoolBadge ok={data.blocks.oeth.configured} label="OETH" />
            </div>
            <PayrollParamLine
              label="Soldes CP importés"
              value={data.blocks.cp.adjusted_count}
            />
            <PayrollParamLine
              label="Mois calendrier importés"
              value={data.blocks.planning.months_with_calendar}
            />
            <PayrollParamLine
              label="Taux AT/MP"
              value={data.blocks.payroll_params.taux_at_mp}
              format={(v) => `${v} %`}
            />
            <PayrollParamLine
              label="Jour de fin de paie"
              value={data.blocks.payroll_params.paie_jour_de_fin}
            />
            <PayrollParamLine
              label="Occurrence paie"
              value={data.blocks.payroll_params.paie_occurrence}
            />
          </CardContent>
        </Card>
      </div>

      {data.next_actions.length > 0 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Actions recommandées</CardTitle>
            <CardDescription>Par ordre de priorité pour finaliser la filiale.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.next_actions.map((action, index) => (
              <Button
                key={action.block}
                type="button"
                variant="outline"
                size="sm"
                className="h-auto w-full justify-start py-2 text-left"
                onClick={() => handleAction(action)}
              >
                <span className="mr-2 shrink-0 tabular-nums text-muted-foreground">
                  {index + 1}.
                </span>
                {action.label}
              </Button>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-wrap gap-2 border-t pt-2">
        <Button type="button" variant="outline" size="sm" onClick={() => refetch()}>
          Recalculer le bilan
        </Button>
        <Button type="button" variant="outline" size="sm" asChild>
          <Link to={`/super-admin/companies?highlight=${companyId}`}>
            <ExternalLink className="mr-2 h-3.5 w-3.5" />
            Fiche entreprise
          </Link>
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => goToStep('intro')}>
          Revoir le parcours depuis le début
        </Button>
      </div>
    </div>
  );
}
