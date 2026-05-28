import type { AbsenceBalance } from '@/api/absences';
import { EvenementFamilialBalanceDialog } from '@/components/dashboard/EvenementFamilialBalanceDialog';
import { formatBalanceRemaining } from '@/lib/employeeAbsencesUtils';

const EVENEMENT_FAMILIAL_TYPE = 'Événement familial';

interface EmployeeAbsenceBalanceRowProps {
  balance: AbsenceBalance;
  /** Affiche la ligne « acquis » (page Congés & Absences). */
  showAcquired?: boolean;
}

export function EmployeeAbsenceBalanceRow({
  balance,
  showAcquired = false,
}: EmployeeAbsenceBalanceRowProps) {
  const isFamilial = balance.type === EVENEMENT_FAMILIAL_TYPE;
  const remainingDisplay = formatBalanceRemaining(balance.remaining);
  const acquiredDisplay =
    typeof balance.acquired === 'number'
      ? `${balance.acquired.toFixed(1)} j`
      : '—';

  return (
    <div className="space-y-1 border-b border-border/60 pb-3 last:border-0 last:pb-0">
      <p className="text-sm font-medium">{balance.type || 'Type inconnu'}</p>
      {showAcquired && !isFamilial && (
        <p className="text-xs text-muted-foreground">
          Acquis : {acquiredDisplay} · Pris : {balance.taken} j · Restant :{' '}
          <span className="font-medium text-foreground">{remainingDisplay}</span>
        </p>
      )}
      <div className="flex items-baseline justify-between gap-2">
        {!showAcquired && (
          <span className="text-xs text-muted-foreground">
            Pris : {balance.taken} j
          </span>
        )}
        {isFamilial ? (
          <EvenementFamilialBalanceDialog triggerLabel="Voir le détail" />
        ) : showAcquired ? (
          <strong className="text-lg font-bold text-primary">
            {remainingDisplay}
          </strong>
        ) : (
          <>
            <strong className="text-lg font-bold text-primary">
              {remainingDisplay}
            </strong>
          </>
        )}
      </div>
      {!isFamilial && !showAcquired && (
        <p className="text-right text-xs text-muted-foreground">
          Restant : {remainingDisplay}
        </p>
      )}
    </div>
  );
}
