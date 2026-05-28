import { Badge } from '@/components/ui/badge';
import type { SalaryAdvanceStatus } from '@/api/saisiesAvances';
import { getStatusBadgeConfig } from '@/lib/employeeSalaryAdvancesUtils';

export function EmployeeSalaryAdvanceStatusBadge({
  status,
}: {
  status: SalaryAdvanceStatus;
}) {
  const { variant, icon: Icon, label } = getStatusBadgeConfig(status);
  return (
    <Badge variant={variant}>
      <Icon className="mr-1 h-3 w-3" />
      {label}
    </Badge>
  );
}
