import { format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';
import { AlertTriangle, Check } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export interface PayrollSyncStatusProps {
  transmitted: boolean;
  transmittedAt?: string;
  weekStatus: string;
  onRetry?: () => void;
}

function formatTransmittedAt(iso: string): string {
  try {
    const d = parseISO(iso);
    return format(d, "d/MM/yyyy 'à' HH:mm", { locale: fr });
  } catch {
    return iso;
  }
}

export function PayrollSyncStatus({
  transmitted,
  transmittedAt,
  weekStatus,
  onRetry,
}: PayrollSyncStatusProps) {
  if (weekStatus !== 'locked') {
    return null;
  }

  if (transmitted) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge className="gap-1 bg-green-100 text-green-900 hover:bg-green-100 dark:bg-green-950 dark:text-green-100">
          <Check className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>Transmis à la paie</span>
        </Badge>
        {transmittedAt ? (
          <span className="text-muted-foreground">le {formatTransmittedAt(transmittedAt)}</span>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Badge variant="destructive" className="gap-1 font-medium">
        <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
        Transmission en attente
      </Badge>
      {onRetry ? (
        <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={onRetry}>
          Réessayer
        </Button>
      ) : null}
    </div>
  );
}
