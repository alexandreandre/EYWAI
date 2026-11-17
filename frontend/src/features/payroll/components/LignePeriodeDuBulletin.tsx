import { formatFr } from '@/features/payroll/lib/fenetreVariables';
import { usePeriodeVariables } from '@/features/payroll/hooks/usePeriodeVariables';
import { monthYearLabel } from '@/features/payroll/utils/payrollMonth';

/**
 * Une ligne discrète au-dessus du calendrier d'un salarié : les jours que le
 * bulletin du mois retient (absences non rémunérées, activité partielle, heures sup), forfait
 * jours compris (Lyon, 17/11/2026 : on ne voyait pas que le bulletin d'octobre
 * lit la fin de septembre). Même source que « Période des variables ».
 */
export function LignePeriodeDuBulletin({ year, month }: { year: number; month: number }) {
  const { data: fenetre } = usePeriodeVariables(year, month);
  if (!fenetre?.debut || !fenetre?.fin) return null;
  return (
    <p className="text-xs text-muted-foreground" data-testid="periode-du-bulletin">
      Bulletin de {monthYearLabel(month, year).toLowerCase()} : jours du {formatFr(fenetre.debut).slice(0, 5)} au{' '}
      {formatFr(fenetre.fin).slice(0, 5)} (absences non rémunérées, activité partielle, heures sup).
    </p>
  );
}
