import { Badge } from '@/components/ui/badge';
import type { IjssAbsenceStatus } from '@/api/ijssTracking';
import { IJSS_ABSENCE_STATUS_LABELS } from '@/api/ijssTracking';

interface AbsenceIjssStatusBadgeProps {
  status: IjssAbsenceStatus;
}

export function AbsenceIjssStatusBadge({ status }: AbsenceIjssStatusBadgeProps) {
  if (status.applied_to_payslip_at) {
    return (
      <Badge className="w-fit border-0 bg-emerald-600 text-white hover:bg-emerald-600">
        IJSS appliquée bulletin
      </Badge>
    );
  }

  if (status.ijss_brut_validated != null) {
    return (
      <Badge className="w-fit border-0 bg-blue-600 text-white hover:bg-blue-600">
        Brut CPAM validé
      </Badge>
    );
  }

  const label = IJSS_ABSENCE_STATUS_LABELS[status.status] ?? status.status;
  const variant =
    status.status === 'ok' || status.status === 'justified'
      ? 'default'
      : status.status === 'variance' || status.status === 'partial'
        ? 'destructive'
        : 'secondary';

  return (
    <Badge variant={variant} className="w-fit">
      {label}
    </Badge>
  );
}
