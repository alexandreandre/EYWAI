import { AlertTriangle, Info } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import type { PayslipBulletinData } from '@/api/payslips';

type EngineAlert = {
  code?: string;
  message?: string;
  critique?: boolean;
  severity?: string;
};

function collectAlerts(data: PayslipBulletinData | null | undefined): Array<{
  id: string;
  message: string;
  critical: boolean;
}> {
  if (!data) return [];

  const out: Array<{ id: string; message: string; critical: boolean }> = [];

  for (const raw of (data.alertes_baremes as EngineAlert[] | undefined) ?? []) {
    const message = String(raw.message ?? '').trim();
    if (!message) continue;
    out.push({
      id: `bareme-${raw.code ?? out.length}`,
      message,
      critical: Boolean(raw.critique),
    });
  }

  for (const msg of data.synthese_net?.alertes_maintien ?? []) {
    const message = String(msg).trim();
    if (!message) continue;
    out.push({
      id: `maintien-${out.length}`,
      message,
      critical: false,
    });
  }

  return out;
}

export function PayslipAlertsBanner({
  data,
}: {
  data: PayslipBulletinData | null | undefined;
}) {
  const alerts = collectAlerts(data);
  if (alerts.length === 0) return null;

  const hasCritical = alerts.some((a) => a.critical);

  return (
    <Alert
      variant={hasCritical ? 'destructive' : 'default'}
      className={
        hasCritical
          ? undefined
          : 'border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100'
      }
    >
      {hasCritical ? (
        <AlertTriangle className="h-4 w-4" />
      ) : (
        <Info className="h-4 w-4 text-amber-600" />
      )}
      <AlertTitle>
        {hasCritical
          ? 'Alertes paie — action requise'
          : 'Alertes paie — à vérifier'}
      </AlertTitle>
      <AlertDescription>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-sm">
          {alerts.map((alert) => (
            <li key={alert.id}>{alert.message}</li>
          ))}
        </ul>
        <p className="mt-3 text-xs opacity-80">
          Consultez aussi l&apos;onglet Comparaison pour les écarts N-1 et les
          alertes de validation.
        </p>
      </AlertDescription>
    </Alert>
  );
}
