import { useNavigate } from 'react-router-dom';
import { usePayrollEmployeesQuery } from '@/hooks/queries/useEmployeesQuery';
import { GeneratePayrollModal } from '@/features/dashboard/widgets/GeneratePayrollModal';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';

export default function PayrollGenerate() {
  const navigate = useNavigate();
  const employeesQuery = usePayrollEmployeesQuery();
  const employees = (employeesQuery.data ?? []).map((employee) => ({
    id: employee.id,
    first_name: employee.first_name,
    last_name: employee.last_name,
  }));

  const handleClose = () => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate('/');
  };

  return (
    <>
      <PageFetchIndicator isFetching={employeesQuery.isFetching} />
      <GeneratePayrollModal isOpen onClose={handleClose} employees={employees} />
    </>
  );
}
