import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getPendingManagerCetApproval } from '@/api/cet';
import { getPendingManagerApproval } from '@/api/absences';
import { RhPageHeader } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useCompany } from '@/contexts/CompanyContext';
import { queryKeys } from '@/lib/queryKeys';

export default function ManagerApprovals() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';

  const { data: absences = [] } = useQuery({
    queryKey: ['absences', 'pending-manager-approval', companyId],
    queryFn: async () => {
      const res = await getPendingManagerApproval(companyId);
      return res.data;
    },
    enabled: Boolean(companyId),
  });

  const { data: cet = [] } = useQuery({
    queryKey: queryKeys.cetPendingManager(companyId),
    queryFn: () => getPendingManagerCetApproval(companyId),
    enabled: Boolean(companyId),
  });

  return (
    <div className="container max-w-3xl py-6 space-y-6">
      <RhPageHeader
        title="Validations en attente"
        description="Congés et compte épargne-temps à traiter pour votre équipe."
      />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Congés ({absences.length})</CardTitle>
          <Link to="/leave-requests" className="text-sm text-primary hover:underline">
            Ouvrir
          </Link>
        </CardHeader>
        <CardContent>
          {absences.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune demande de congé.</p>
          ) : (
            <p className="text-sm">{absences.length} demande(s) en attente.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">CET ({cet.length})</CardTitle>
          <Link to="/cet-requests" className="text-sm text-primary hover:underline">
            Ouvrir
          </Link>
        </CardHeader>
        <CardContent>
          {cet.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune demande CET.</p>
          ) : (
            <p className="text-sm">{cet.length} demande(s) en attente.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
