import { AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { WorkforceReconciliationSummary as WorkforceReconciliationSummaryType } from '@/api/dsnImport';

type Props = {
  reconciliation: WorkforceReconciliationSummaryType;
};

export function WorkforceReconciliationSummary({ reconciliation }: Props) {
  const { gaps, unresolved_count, resolved_count, period, active_without_nir_count } = reconciliation;

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
        </CardDescription>
      </CardHeader>
      {active_without_nir_count != null && active_without_nir_count > 0 && (
        <CardContent className="pt-0">
          <p className="text-xs text-amber-800">
            {active_without_nir_count} salarié(s) actif(s) sans NIR : comparaison automatique impossible.
          </p>
        </CardContent>
      )}
    </Card>
  );
}
