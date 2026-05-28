import { Link } from 'react-router-dom';
import { CheckCircle, CircleX, Hourglass } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmployeeExpensesKpiBandProps {
  pending: number;
  rejected: number;
  validated: number;
}

function KpiTile({
  to,
  count,
  label,
  icon: Icon,
  iconClassName,
  subdued,
}: {
  to: string;
  count: number;
  label: string;
  icon: typeof Hourglass;
  iconClassName: string;
  subdued?: boolean;
}) {
  return (
    <Link
      to={to}
      className={cn(
        'flex flex-1 items-center gap-3 rounded-lg border bg-card p-4 transition-colors hover:bg-muted/50',
        subdued && 'opacity-80'
      )}
    >
      <Icon className={cn('h-5 w-5 shrink-0', iconClassName)} />
      <div>
        <p className="text-2xl font-bold tabular-nums">{count}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </Link>
  );
}

export function EmployeeExpensesKpiBand({
  pending,
  rejected,
  validated,
}: EmployeeExpensesKpiBandProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <KpiTile
        to="/expenses?status=pending"
        count={pending}
        label="En attente"
        icon={Hourglass}
        iconClassName="text-amber-500"
      />
      <KpiTile
        to="/expenses?status=rejected"
        count={rejected}
        label="Refusées"
        icon={CircleX}
        iconClassName="text-destructive"
      />
      <KpiTile
        to="/expenses?status=validated"
        count={validated}
        label="Validées"
        icon={CheckCircle}
        iconClassName="text-emerald-600"
        subdued={validated === 0}
      />
    </div>
  );
}
