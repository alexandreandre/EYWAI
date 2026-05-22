import { computeMonthStats, type CalendarMonthStats } from '@/lib/calendarStats';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import { cn } from '@/lib/utils';

interface CalendarKpiBandProps {
  plannedCalendar: PlannedEventData[];
  actualHours: ActualHoursData[];
  isForfaitJour: boolean;
  className?: string;
}

function KpiTile({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  highlight?: 'positive' | 'negative' | 'neutral';
}) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2 min-w-[7rem]">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p
        className={cn(
          'text-lg font-semibold tabular-nums',
          highlight === 'positive' && 'text-emerald-600',
          highlight === 'negative' && 'text-destructive'
        )}
      >
        {value}
      </p>
      {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

export function CalendarKpiBand({
  plannedCalendar,
  actualHours,
  isForfaitJour,
  className,
}: CalendarKpiBandProps) {
  const stats: CalendarMonthStats = computeMonthStats(
    plannedCalendar,
    actualHours,
    isForfaitJour
  );

  if (isForfaitJour) {
    return (
      <div className={cn('flex flex-wrap gap-2 px-2 pb-3', className)}>
        <KpiTile label="Jours prévus" value={String(stats.joursPrevus)} />
        <KpiTile label="Jours travaillés" value={String(stats.joursTravaillesForfait)} />
        <KpiTile
          label="Écart"
          value={`${stats.ecartJours >= 0 ? '+' : ''}${stats.ecartJours}`}
          highlight={stats.ecartJours < 0 ? 'negative' : stats.ecartJours > 0 ? 'positive' : 'neutral'}
        />
        <KpiTile label="Congés" value={`${stats.conges} j`} />
        <KpiTile label="Arrêts" value={`${stats.arrets} j`} />
        <KpiTile label="Fériés" value={`${stats.feriels} j`} />
      </div>
    );
  }

  const ecartStr =
    stats.ecart >= 0 ? `+${stats.ecart.toFixed(1)}` : stats.ecart.toFixed(1);

  return (
    <div className={cn('flex flex-wrap gap-2 px-2 pb-3', className)}>
      <KpiTile label="H. prévues" value={`${stats.heuresPrevues.toFixed(1)} h`} />
      <KpiTile label="H. faites" value={`${stats.heuresFaites.toFixed(1)} h`} />
      <KpiTile
        label="Écart"
        value={`${ecartStr} h`}
        highlight={stats.ecart < 0 ? 'negative' : stats.ecart > 0 ? 'positive' : 'neutral'}
      />
      <KpiTile label="Jours travaillés" value={String(stats.joursTravailles)} />
      <KpiTile label="Congés" value={`${stats.conges} j`} />
      <KpiTile label="Arrêts" value={`${stats.arrets} j`} />
    </div>
  );
}
