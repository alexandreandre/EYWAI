import { AlertCircle, CalendarClock, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmployeeMedicalKpiBandProps {
  overdue: number;
  upcoming: number;
  completed: number;
}

function KpiTile({
  count,
  label,
  icon: Icon,
  iconClassName,
  subdued,
}: {
  count: number;
  label: string;
  icon: typeof AlertCircle;
  iconClassName: string;
  subdued?: boolean;
}) {
  return (
    <div
      className={cn(
        'flex flex-1 items-center gap-3 rounded-lg border bg-card p-4',
        subdued && 'opacity-80'
      )}
    >
      <Icon className={cn('h-5 w-5 shrink-0', iconClassName)} aria-hidden />
      <div>
        <p className="text-2xl font-bold tabular-nums">{count}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export function EmployeeMedicalKpiBand({
  overdue,
  upcoming,
  completed,
}: EmployeeMedicalKpiBandProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <KpiTile
        count={overdue}
        label="En retard"
        icon={AlertCircle}
        iconClassName="text-destructive"
        subdued={overdue === 0}
      />
      <KpiTile
        count={upcoming}
        label="À venir"
        icon={CalendarClock}
        iconClassName="text-amber-600 dark:text-amber-500"
        subdued={upcoming === 0}
      />
      <KpiTile
        count={completed}
        label="Réalisées"
        icon={CheckCircle2}
        iconClassName="text-emerald-600 dark:text-emerald-500"
        subdued={completed === 0}
      />
    </div>
  );
}
