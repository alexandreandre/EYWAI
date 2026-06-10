import { ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { PAYROLL_REQUIRED_FIELD_LABELS } from '@/features/payroll/constants';
import type { PayrollGenerateEmployee } from '@/features/payroll/types';

type PayrollIncompleteEmployeeListProps = {
  employees: PayrollGenerateEmployee[];
  onGoToEmployee: (employeeId: string) => void;
};

function missingFieldsFor(emp: PayrollGenerateEmployee): string[] {
  const fromApi = emp.missing_payroll_fields?.filter(Boolean) ?? [];
  if (fromApi.length > 0) return fromApi;
  if (emp.employment_status === 'en_onboarding') {
    return [...PAYROLL_REQUIRED_FIELD_LABELS];
  }
  return [...PAYROLL_REQUIRED_FIELD_LABELS];
}

export function PayrollIncompleteEmployeeList({
  employees,
  onGoToEmployee,
}: PayrollIncompleteEmployeeListProps) {
  if (employees.length === 0) return null;

  return (
    <ul className="divide-y divide-border/60 rounded-lg border bg-background/80">
      {employees.map((emp) => {
        const missing = missingFieldsFor(emp);
        return (
          <li key={emp.id} className="px-3 py-3 first:rounded-t-lg last:rounded-b-lg">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-2">
                <p className="text-sm font-medium leading-tight text-foreground">
                  {emp.first_name} {emp.last_name}
                </p>
                <div className="flex flex-wrap gap-1">
                  {missing.map((field) => (
                    <Badge
                      key={field}
                      variant="outline"
                      className="border-amber-200/80 bg-amber-50/50 text-[11px] font-normal text-amber-900/90"
                    >
                      {field}
                    </Badge>
                  ))}
                </div>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 shrink-0 gap-1 text-xs"
                onClick={() => onGoToEmployee(emp.id)}
              >
                Compléter les infos
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
