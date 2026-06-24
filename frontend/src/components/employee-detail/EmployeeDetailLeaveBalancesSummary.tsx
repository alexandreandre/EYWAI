import { Link, useLocation } from 'react-router-dom';
import { AlertCircle, CalendarDays } from 'lucide-react';
import { useEmployeeAbsenceBalancesQuery } from '@/hooks/queries/useEmployeeAbsenceBalancesQuery';
import {
  formatBalanceRemaining,
  formatRhLeaveBalanceDetail,
  getRhLeaveBalanceShortLabel,
  isRhLeaveBalanceVisible,
  balanceUsesHours,
} from '@/lib/employeeAbsencesUtils';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface EmployeeDetailLeaveBalancesSummaryProps {
  employeeId: string;
}

export function EmployeeDetailLeaveBalancesSummary({
  employeeId,
}: EmployeeDetailLeaveBalancesSummaryProps) {
  const location = useLocation();
  const balancesQuery = useEmployeeAbsenceBalancesQuery(employeeId);
  const visibleBalances =
    balancesQuery.data?.filter(isRhLeaveBalanceVisible) ?? [];

  const calendarHref = {
    pathname: location.pathname,
    search: '?tab=calendrier',
  };

  return (
    <div className="space-y-3 border-t pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Soldes congés
        </p>
        <Link
          to={calendarHref}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-4 hover:underline"
        >
          <CalendarDays className="h-3.5 w-3.5" aria-hidden />
          Voir le calendrier
        </Link>
      </div>

      {balancesQuery.isLoading ? (
        <div className="flex min-h-[56px] items-center">
          <SharkFinLoader variant="compact" label="" />
        </div>
      ) : balancesQuery.isError ? (
        <p className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden />
          Impossible de charger les soldes de congés.
        </p>
      ) : visibleBalances.length === 0 ? (
        <p className="text-sm text-muted-foreground">Soldes non disponibles.</p>
      ) : (
        <TooltipProvider delayDuration={200}>
          <div className="flex flex-wrap gap-2">
            {visibleBalances.map((balance) => {
              const unit = balanceUsesHours(balance.type) ? 'h' : 'j';
              const remainingDisplay = formatBalanceRemaining(balance.remaining, unit);
              const isFamilial = balance.remaining === 'selon événement';

              return (
                <Tooltip key={balance.type}>
                  <TooltipTrigger asChild>
                    <div
                      className={cn(
                        'min-w-[7rem] rounded-lg border bg-muted/30 px-3 py-2',
                        'transition-colors hover:bg-muted/50',
                      )}
                    >
                      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                        {getRhLeaveBalanceShortLabel(balance.type)}
                      </p>
                      <p
                        className={cn(
                          'text-lg font-bold leading-tight',
                          isFamilial ? 'text-sm font-semibold text-foreground' : 'text-primary',
                        )}
                      >
                        {remainingDisplay}
                      </p>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="max-w-xs text-xs">
                    <p className="font-medium">{balance.type}</p>
                    <p className="mt-1 text-muted-foreground">
                      {isFamilial
                        ? 'Quota et solde selon le type d’événement (convention collective).'
                        : formatRhLeaveBalanceDetail(balance)}
                    </p>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        </TooltipProvider>
      )}
    </div>
  );
}
