import { periodeEnClair } from '@/features/payroll/utils/payrollMonth';

export function DsnImportCutoffNote({ period }: { period?: string | null }) {
  if (!period) return null;
  return (
    <p className="text-xs text-muted-foreground">
      Les imports du logiciel précédent sont attendus jusqu’à {periodeEnClair(period)}.
      Les mois suivants relèvent de la paie Martine. Les mois déjà importés restent indiqués séparément.
    </p>
  );
}
