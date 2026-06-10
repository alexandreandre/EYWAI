import { isAxiosError } from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  useEmployeesSummaryQuery,
  usePayrollEmployeesQuery,
} from '@/hooks/queries/useEmployeesQuery';
import { GeneratePayrollModal } from '@/features/dashboard/widgets/GeneratePayrollModal';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';

function employeesQueryErrorMessage(error: unknown): string | null {
  if (!error) return null;
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
  }
  if (error instanceof Error && error.message) return error.message;
  return 'Impossible de charger la liste des collaborateurs.';
}

export default function PayrollGenerate() {
  const navigate = useNavigate();
  const employeesQuery = usePayrollEmployeesQuery();
  const allEmployeesQuery = useEmployeesSummaryQuery('all');
  const employees = (employeesQuery.data ?? []).map((employee) => ({
    id: employee.id,
    first_name: employee.first_name,
    last_name: employee.last_name,
    payroll_eligible: employee.payroll_eligible,
    missing_payroll_fields: employee.missing_payroll_fields,
    employment_status: employee.employment_status,
  }));

  const employeesLoading =
    (employeesQuery.isLoading && !employeesQuery.data) ||
    (allEmployeesQuery.isLoading && !allEmployeesQuery.data);
  const employeesError =
    employeesQueryErrorMessage(employeesQuery.error) ??
    employeesQueryErrorMessage(allEmployeesQuery.error);

  const handleClose = () => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate('/');
  };

  const handleRetryEmployees = () => {
    void employeesQuery.refetch();
    void allEmployeesQuery.refetch();
  };

  const handleNavigateTo = (path: string) => {
    navigate(path);
  };

  return (
    <>
      <PageFetchIndicator isFetching={employeesQuery.isFetching || allEmployeesQuery.isFetching} />
      <GeneratePayrollModal
        isOpen
        onClose={handleClose}
        employees={employees}
        allEmployees={allEmployeesQuery.data ?? []}
        employeesLoading={employeesLoading}
        employeesError={employeesError}
        onRetryEmployees={handleRetryEmployees}
        onNavigateTo={handleNavigateTo}
      />
    </>
  );
}
