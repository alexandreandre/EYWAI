import type { AdvanceAvailableAmount } from '@/api/saisiesAvances';
import { Card, CardContent } from '@/components/ui/card';
import { formatCurrency } from '@/lib/employeeDashboardUtils';
import { formatAdvancePlafondSummary } from '@/lib/employeeSalaryAdvancesUtils';
import { cn } from '@/lib/utils';
import { Wallet } from 'lucide-react';

type AdvanceAvailableSummaryProps = {
  data: AdvanceAvailableAmount;
  variant?: 'card' | 'inline';
};

export function AdvanceAvailableSummary({
  data,
  variant = 'card',
}: AdvanceAvailableSummaryProps) {
  const available = Number(data.available_amount || 0);
  const outstanding = Number(data.outstanding_advances || 0);
  const referenceNet = Number(data.reference_net_salary || 0);
  const maxFromNet = Number(data.max_advance_from_net || 0);
  const isZero = available <= 0;

  if (variant === 'inline') {
    return (
      <span>
        <strong>Montant disponible :</strong> {formatCurrency(available)}
        {referenceNet > 0 && (
          <>
            {' '}
            — Plafond : {formatAdvancePlafondSummary(data)} ({formatCurrency(referenceNet)},
            max. {formatCurrency(maxFromNet)})
          </>
        )}
        {outstanding > 0 && (
          <>
            {' '}
            — Avances en cours : {formatCurrency(outstanding)}
          </>
        )}
      </span>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-2 pt-6">
        <p className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Wallet className="h-4 w-4" />
          Montant disponible
        </p>
        <p
          className={cn(
            'text-3xl font-bold',
            isZero ? 'text-muted-foreground' : 'text-primary'
          )}
        >
          {formatCurrency(available)}
        </p>
        {referenceNet > 0 && (
          <p className="text-sm text-muted-foreground">
            Plafond : {formatAdvancePlafondSummary(data)} ({formatCurrency(referenceNet)} — max.{' '}
            {formatCurrency(maxFromNet)})
          </p>
        )}
        {outstanding > 0 && (
          <p className="text-sm text-muted-foreground">
            Avances en cours déduites : {formatCurrency(outstanding)}
          </p>
        )}
        {isZero && (
          <p className="text-sm text-muted-foreground">
            Aucun montant disponible pour le moment.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
