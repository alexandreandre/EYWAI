import { Badge } from '@/components/ui/badge';
import {
  TRANSMISSION_STATUS_LABELS,
  type TransmissionStatus,
} from '@/api/accountingIntegration';

const VARIANT: Record<
  TransmissionStatus,
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  generated: 'outline',
  queued: 'secondary',
  sent: 'default',
  transmitted: 'default',
  acknowledged: 'default',
  rejected: 'destructive',
  manual: 'secondary',
  failed: 'destructive',
};

export function TransmissionStatusBadge({ status }: { status: TransmissionStatus }) {
  const label = TRANSMISSION_STATUS_LABELS[status] ?? status;
  return <Badge variant={VARIANT[status] ?? 'outline'}>{label}</Badge>;
}
