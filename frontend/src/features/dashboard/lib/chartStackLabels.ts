import type { ChartDataPoint, PayrollKpiMeta } from '@/features/dashboard/types';

export type ChartStackMode = 'employer_cost' | 'gross';

export interface ChartStackLabels {
  netLabel: string;
  chargesLabel: string;
  subtitle?: string;
}

export function resolveChartStackLabels(
  payroll: PayrollKpiMeta | undefined,
  chartData: ChartDataPoint[],
): ChartStackLabels {
  const modes = new Set(
    chartData
      .filter((point) => point.source !== 'none')
      .map((point) => point.stackMode ?? 'employer_cost'),
  );
  const hasMixedStacks = modes.size > 1;

  if (hasMixedStacks || payroll?.has_mixed_sources) {
    return {
      netLabel: 'Part nette',
      chargesLabel: 'Cotisations et charges',
    };
  }

  const stackMode: ChartStackMode =
    payroll?.employer_cost && payroll.employer_cost > 0
      ? 'employer_cost'
      : payroll?.source === 'dsn'
        ? 'gross'
        : 'employer_cost';

  if (stackMode === 'gross') {
    return {
      netLabel: 'Net imposable',
      chargesLabel: 'Cotisations salariales',
      subtitle: 'Répartition de la masse brute déclarée',
    };
  }

  if (payroll?.source === 'dsn') {
    return {
      netLabel: 'Net imposable',
      chargesLabel: 'Charges patronales',
    };
  }

  return {
    netLabel: 'Net versé',
    chargesLabel: 'Charges patronales',
  };
}

export function resolvePrimaryPayrollMetric(payroll: PayrollKpiMeta | undefined): {
  amount: number;
  label: string;
  secondaryLabel: string;
} {
  const showEmployerCost = (payroll?.employer_cost ?? 0) > 0;
  return {
    amount: showEmployerCost ? payroll!.employer_cost : payroll?.gross ?? 0,
    label: showEmployerCost ? 'Coût employeur' : 'Masse brute',
    secondaryLabel:
      payroll?.source === 'dsn' ? 'Net imposable (DSN)' : 'Net versé',
  };
}
