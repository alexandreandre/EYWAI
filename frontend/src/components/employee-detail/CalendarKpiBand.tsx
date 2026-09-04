import {
  computeMonthStats,
  joursArretCalendairesDuMois,
  type AbsenceLike,
  type CalendarMonthStats,
} from '@/lib/calendarStats';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import { cn } from '@/lib/utils';

interface CalendarKpiBandProps {
  plannedCalendar: PlannedEventData[];
  actualHours: ActualHoursData[];
  isForfaitJour: boolean;
  className?: string;
  /** Absences validées du salarié : la tuile Arrêts passe alors en jours
   * CALENDAIRES (week-ends compris, décompte prévoyance). */
  absences?: AbsenceLike[];
  year?: number;
  month?: number;
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
  absences,
  year,
  month,
}: CalendarKpiBandProps) {
  const stats: CalendarMonthStats = computeMonthStats(
    plannedCalendar,
    actualHours,
    isForfaitJour
  );
  const arretsCalendaires =
    absences && year && month
      ? joursArretCalendairesDuMois(absences, year, month)
      : null;
  // Repli sur le compte du calendrier quand aucune demande d'absence ne porte
  // l'arrêt (jours typés à la main dans le planning, reprises).
  const arretsTile =
    arretsCalendaires !== null && (arretsCalendaires > 0 || stats.arrets === 0)
      ? { value: `${arretsCalendaires} j`, sub: 'calendaires (prévoyance)' }
      : { value: `${stats.arrets} j`, sub: undefined };

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
        <KpiTile label="Arrêts" value={arretsTile.value} sub={arretsTile.sub} />
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
      <KpiTile label="Arrêts" value={arretsTile.value} sub={arretsTile.sub} />
    </div>
  );
}
