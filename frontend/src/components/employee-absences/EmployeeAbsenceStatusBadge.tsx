import { CheckCircle, CircleX, Clock, Ban } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { AbsenceRequest } from '@/api/absences';

export function EmployeeAbsenceStatusBadge({
  status,
}: {
  status: AbsenceRequest['status'];
}) {
  if (status === 'validated') {
    return (
      <Badge variant="success">
        <CheckCircle className="mr-1 h-3 w-3" />
        Validée
      </Badge>
    );
  }
  if (status === 'rejected') {
    return (
      <Badge variant="destructive">
        <CircleX className="mr-1 h-3 w-3" />
        Rejetée
      </Badge>
    );
  }
  if (status === 'cancelled') {
    return (
      <Badge variant="outline">
        <Ban className="mr-1 h-3 w-3" />
        Annulée
      </Badge>
    );
  }
  return (
    <Badge variant="secondary">
      <Clock className="mr-1 h-3 w-3" />
      En attente
    </Badge>
  );
}
