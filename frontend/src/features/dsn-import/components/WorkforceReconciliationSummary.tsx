import { AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { WorkforceReconciliationSummary as WorkforceReconciliationSummaryType } from '@/api/dsnImport';

type Props = {
  reconciliation: WorkforceReconciliationSummaryType;
};

function buildBreakdown(reconciliation: WorkforceReconciliationSummaryType): string | null {
  const counts = reconciliation.gap_counts_by_type;
  if (!counts) return null;
  const parts: string[] = [];
  if (counts.new_hire_not_in_dsn) {
    parts.push(`${counts.new_hire_not_in_dsn} embauche(s) récente(s)`);
  }
  if (counts.missing_from_dsn) {
    parts.push(`${counts.missing_from_dsn} départ(s) probable(s)`);
  }
  if (counts.contract_end_in_dsn) {
    parts.push(`${counts.contract_end_in_dsn} fin(s) de contrat DSN`);
  }
  return parts.length > 0 ? parts.join(' · ') : null;
}

export function WorkforceReconciliationSummary({ reconciliation }: Props) {
  const {
    gaps,
    unresolved_count,
    resolved_count,
    period,
    active_without_nir_count,
    excluded_out_of_scope_count,
  } = reconciliation;
  const breakdown = buildBreakdown(reconciliation);

  return (
    <Card className="border-amber-200 bg-amber-50/40">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="h-4 w-4 text-amber-700" />
          Réconciliation des effectifs
          {period && (
            <span className="text-sm font-normal text-muted-foreground">— {period}</span>
          )}
        </CardTitle>
        <CardDescription>
          {gaps.length} écart(s) détecté(s) entre la DSN et vos effectifs actifs.
          {' '}
          {resolved_count} décision(s) prise(s), {unresolved_count} restante(s).
          {breakdown && (
            <>
              <br />
              <span className="text-amber-900/80">{breakdown}</span>
            </>
          )}
        </CardDescription>
      </CardHeader>
      {(active_without_nir_count != null && active_without_nir_count > 0)
        || (excluded_out_of_scope_count != null && excluded_out_of_scope_count > 0) ? (
        <CardContent className="pt-0 space-y-1">
          {active_without_nir_count != null && active_without_nir_count > 0 && (
            <p className="text-xs text-amber-800">
              {active_without_nir_count} salarié(s) actif(s) sans NIR : comparaison automatique impossible.
            </p>
          )}
          {excluded_out_of_scope_count != null && excluded_out_of_scope_count > 0 && (
            <p className="text-xs text-muted-foreground">
              {excluded_out_of_scope_count} salarié(s) hors périmètre du mois (embauche future ou déjà parti) — aucune décision requise.
            </p>
          )}
        </CardContent>
      ) : null}
    </Card>
  );
}
