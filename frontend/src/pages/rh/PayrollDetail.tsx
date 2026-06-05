import { Navigate, useParams } from 'react-router-dom';

/**
 * Deep-link legacy : /payroll/:employeeId → /payroll?employee=:id
 */
export default function PayrollDetail() {
  const { employeeId } = useParams<{ employeeId: string }>();
  if (!employeeId) {
    return <Navigate to="/payroll" replace />;
  }
  return <Navigate to={`/payroll?employee=${encodeURIComponent(employeeId)}`} replace />;
}
