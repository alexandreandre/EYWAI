import { useEffect } from 'react';
import { AlertTriangle, UserRoundPlus } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { isProfileIncomplete } from '@/features/employee-detail/components/employeeProfileFormUtils';
import type { Employee } from '@/features/employee-detail/types';

const SESSION_AUTO_OPEN_KEY = (employeeId: string) =>
  `onboarding-completion-auto-opened:${employeeId}`;

export interface EmployeeOnboardingCompletionProps {
  employeeId: string;
  employee: Employee;
  onOpenEdit: () => void;
}

export function EmployeeOnboardingCompletion({
  employeeId,
  employee,
  onOpenEdit,
}: EmployeeOnboardingCompletionProps) {
  const incomplete = isProfileIncomplete(employee);
  const missingFields = employee.missing_payroll_fields ?? [];

  useEffect(() => {
    if (!incomplete) return;
    const key = SESSION_AUTO_OPEN_KEY(employeeId);
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, '1');
    onOpenEdit();
  }, [employeeId, incomplete, onOpenEdit]);

  if (!incomplete) return null;

  const fullName = `${employee.first_name} ${employee.last_name}`.trim();

  return (
    <div
      role="alert"
      className="rounded-lg border border-amber-300 bg-amber-50/80 px-4 py-3 text-amber-950"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden />
            <div>
              <p className="font-medium leading-snug">Fiche à compléter — onboarding en cours</p>
              <p className="mt-1 text-sm text-amber-900/90">
                {fullName} a été embauché(e) avec une fiche minimale. Complétez les informations
                en une seule fois pour finaliser l&apos;intégration.
              </p>
            </div>
          </div>
          {missingFields.length > 0 && (
            <div className="flex flex-wrap gap-1 pl-7">
              {missingFields.map((field) => (
                <Badge
                  key={field}
                  variant="outline"
                  className="border-amber-300 bg-white text-[11px] font-normal text-amber-800"
                >
                  {field}
                </Badge>
              ))}
            </div>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          className="shrink-0 gap-1.5 bg-amber-600 hover:bg-amber-700"
          onClick={onOpenEdit}
        >
          <UserRoundPlus className="h-4 w-4" aria-hidden />
          Compléter la fiche
        </Button>
      </div>
    </div>
  );
}
