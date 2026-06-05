import { Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { formatMonthYearLabel } from '@/lib/employeeCseUtils';
import { cn } from '@/lib/utils';

interface EmployeeCseDelegationBannerProps {
  creditBase: number;
  reportedAvailable: number;
  transfersIn: number;
  monthlyCap: number;
  quotaHours: number;
  consumedHours: number;
  remainingHours: number;
  isNearLimit: boolean;
  isOverLimit: boolean;
  warnings?: string[];
  onSaisirHeure: () => void;
  compact?: boolean;
}

export function EmployeeCseDelegationBanner({
  creditBase,
  reportedAvailable,
  transfersIn,
  monthlyCap,
  quotaHours,
  consumedHours,
  remainingHours,
  isNearLimit,
  isOverLimit,
  warnings = [],
  onSaisirHeure,
  compact = false,
}: EmployeeCseDelegationBannerProps) {
  const monthLabel = formatMonthYearLabel(new Date());
  const progressValue =
    monthlyCap > 0 ? Math.min(100, (consumedHours / monthlyCap) * 100) : 0;

  return (
    <Card
      className={cn(
        'border-blue-200/80 bg-blue-50/80 dark:border-blue-900/50 dark:bg-blue-950/20',
        compact && 'shadow-none'
      )}
    >
      <CardHeader className={cn(compact && 'pb-2')}>
        <CardTitle className="flex items-center gap-2 text-base">
          <Clock className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          Délégation — {monthLabel}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              {consumedHours.toFixed(1)} h consommées — plafond {monthlyCap.toFixed(1)} h
            </span>
            <span
              className={cn(
                'font-medium',
                isOverLimit && 'text-destructive',
                isNearLimit && !isOverLimit && 'text-amber-600'
              )}
            >
              {remainingHours.toFixed(1)} h restantes
            </span>
          </div>
          <Progress
            value={progressValue}
            className={cn(
              'h-2',
              isOverLimit && '[&>div]:bg-destructive',
              isNearLimit && !isOverLimit && '[&>div]:bg-amber-500'
            )}
          />
        </div>

        <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4 sm:gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Crédit base</p>
            <p className="text-lg font-bold">{creditBase} h</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Reporté</p>
            <p className="text-lg font-bold">{reportedAvailable.toFixed(1)} h</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Mutualisé</p>
            <p className="text-lg font-bold">{transfersIn.toFixed(1)} h</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Restant</p>
            <p
              className={cn(
                'text-lg font-bold',
                isOverLimit && 'text-destructive',
                isNearLimit && !isOverLimit && 'text-amber-600'
              )}
            >
              {remainingHours.toFixed(1)} h
            </p>
          </div>
        </div>

        {warnings.length > 0 && (
          <ul className="space-y-1 text-sm text-amber-800 dark:text-amber-100">
            {warnings.map((w) => (
              <li key={w} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 dark:border-amber-900 dark:bg-amber-950/40">
                {w}
              </li>
            ))}
          </ul>
        )}

        {(isNearLimit || isOverLimit) && (
          <p
            className={cn(
              'rounded-md border px-3 py-2 text-sm',
              isOverLimit
                ? 'border-destructive/30 bg-destructive/10 text-destructive'
                : 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100'
            )}
          >
            {isOverLimit
              ? `Vous avez dépassé votre quota mensuel de ${Math.abs(remainingHours).toFixed(1)} h.`
              : `Vous approchez de votre quota mensuel (${remainingHours.toFixed(1)} h restantes).`}
          </p>
        )}

        <Button onClick={onSaisirHeure} className="w-full sm:w-auto">
          Saisir une heure de délégation
        </Button>
      </CardContent>
    </Card>
  );
}
