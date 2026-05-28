import { Badge } from '@/components/ui/badge';
import { CheckCircle, CircleX, Clock } from 'lucide-react';
import type { ExpenseStatus } from '@/api/expenses';
import { EXPENSE_STATUS_LABELS } from '@/lib/employeeExpensesUtils';

export function ExpenseStatusBadge({ status }: { status: ExpenseStatus }) {
  switch (status) {
    case 'validated':
      return (
        <Badge variant="success">
          <CheckCircle className="mr-1 h-3 w-3" />
          {EXPENSE_STATUS_LABELS.validated}
        </Badge>
      );
    case 'pending':
      return (
        <Badge variant="secondary">
          <Clock className="mr-1 h-3 w-3" />
          {EXPENSE_STATUS_LABELS.pending}
        </Badge>
      );
    case 'rejected':
      return (
        <Badge variant="destructive">
          <CircleX className="mr-1 h-3 w-3" />
          {EXPENSE_STATUS_LABELS.rejected}
        </Badge>
      );
    default:
      return <Badge>{status}</Badge>;
  }
}
