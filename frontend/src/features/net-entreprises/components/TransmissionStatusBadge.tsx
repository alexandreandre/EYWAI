import { Badge } from '@/components/ui/badge';
import {
  TRANSMISSION_STATUS_LABELS,
  type TransmissionStatus,
} from '@/api/netEntreprises';

type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'danger' | 'outline';

const STATUS_VARIANT: Record<TransmissionStatus, BadgeVariant> = {
  generated: 'secondary',
  manual: 'warning',
  queued: 'secondary',
  sent: 'default',
  acknowledged: 'success',
  rejected: 'danger',
};

export function TransmissionStatusBadge({
  status,
  className,
}: {
  status: TransmissionStatus;
  className?: string;
}) {
  const variant = STATUS_VARIANT[status] ?? 'outline';
  const label = TRANSMISSION_STATUS_LABELS[status] ?? status;
  return (
    <Badge variant={variant} className={className}>
      {label}
    </Badge>
  );
}

export default TransmissionStatusBadge;
