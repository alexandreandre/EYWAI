import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle } from 'lucide-react';

import type { IccpDetails } from '@/api/employeeExits';
import { libelleMethodeIccp, lignesDesPeriodes } from '@/features/employee-exits/utils/iccpLibelles';

function formatCurrency(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
  }).format(value);
}

export interface IccpArbitrageDetailProps {
  montant?: number | null;
  joursRestants?: number | null;
  calcul?: string | null;
  description?: string | null;
  details?: IccpDetails | null;
  compact?: boolean;
}

export default function IccpArbitrageDetail({
  montant,
  joursRestants,
  calcul,
  description,
  details,
  compact = false,
}: IccpArbitrageDetailProps) {
  const hasArbitrage =
    details &&
    (details.indemnite_maintien != null || details.indemnite_dixieme != null);
  // Estimation par période (règle du bulletin de sortie) : une ligne par période.
  const lignesPeriodes = lignesDesPeriodes(details);

  return (
    <div className="space-y-3">
      {!compact && description && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}

      {joursRestants != null && (
        <p className="text-sm">
          <span className="text-muted-foreground">Solde CP restant : </span>
          <span className="font-medium">{joursRestants.toFixed(2)} jours</span>
        </p>
      )}

      {lignesPeriodes.length > 0 && (
        <div className="rounded-lg border bg-muted/30 p-3 space-y-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground">Méthode retenue</span>
            <Badge variant="secondary">{libelleMethodeIccp(details?.methode_retenue)}</Badge>
          </div>
          <ul className="space-y-1">
            {lignesPeriodes.map((ligne) => (
              <li key={ligne}>{ligne}</li>
            ))}
          </ul>
        </div>
      )}

      {hasArbitrage && (
        <div className="rounded-lg border bg-muted/30 p-3 space-y-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground">Méthode retenue</span>
            <Badge variant="secondary">{libelleMethodeIccp(details?.methode_retenue)}</Badge>
          </div>
          <div className="grid gap-1 sm:grid-cols-2">
            <p>
              <span className="text-muted-foreground">Maintien : </span>
              {formatCurrency(details?.indemnite_maintien)}
            </p>
            <p>
              <span className="text-muted-foreground">1/10e : </span>
              {formatCurrency(details?.indemnite_dixieme)}
            </p>
          </div>
          {details?.periode_reference && (
            <p className="text-xs text-muted-foreground">
              Période de référence : {details.periode_reference}
            </p>
          )}
          {details?.taux_journalier != null && (
            <p className="text-xs text-muted-foreground">
              Taux journalier : {formatCurrency(details.taux_journalier)}
            </p>
          )}
        </div>
      )}

      {montant != null && (
        <p className="text-xs text-muted-foreground">{calcul}</p>
      )}

      {details?.alertes && details.alertes.length > 0 && (
        <Alert variant="default" className="border-amber-200 bg-amber-50 dark:bg-amber-950/30">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-900 dark:text-amber-100">
            <ul className="list-disc pl-4 space-y-1">
              {details.alertes.map((alerte) => (
                <li key={alerte}>{alerte}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
