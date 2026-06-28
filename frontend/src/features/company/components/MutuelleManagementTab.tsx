import { useAuth } from '@/contexts/AuthContext';
import { CompanyMutuelleSection } from '@/features/company/components/CompanyMutuelleSection';

export default function MutuelleManagementTab() {
  const { user } = useAuth();
  const canEdit = Boolean(user?.role && ['admin', 'rh'].includes(user.role));

  return <CompanyMutuelleSection canEdit={canEdit} />;
}
