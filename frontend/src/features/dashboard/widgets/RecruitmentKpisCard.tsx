import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getCandidates, getJobs, getRecruitmentSettings } from '@/api/recruitment';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronRight, UserPlus } from 'lucide-react';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

export function RecruitmentKpisCard() {
  const navigate = useNavigate();
  const companyId = useActiveCompanyId();
  const { data: settings } = useQuery({
    queryKey: queryKeys.recruitmentSettings(companyId),
    queryFn: getRecruitmentSettings,
    enabled: Boolean(companyId),
  });
  const { data: jobs = [] } = useQuery({
    queryKey: [...queryKeys.recruitmentSettings(companyId), 'jobs'],
    queryFn: () => getJobs('active'),
    enabled: Boolean(companyId) && !!settings?.enabled,
  });
  const { data: candidates = [] } = useQuery({
    queryKey: queryKeys.recruitmentCandidates(companyId),
    queryFn: () => getCandidates(),
    enabled: Boolean(companyId) && !!settings?.enabled,
  });
  const inProgress = candidates.filter((c) => c.current_stage_type !== 'hired' && c.current_stage_type !== 'rejected').length;
  const hired = candidates.filter((c) => c.current_stage_type === 'hired').length;
  if (!settings?.enabled) return null;

  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate('/recruitment')}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <UserPlus className="h-4 w-4 text-muted-foreground" />
          Recrutement
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <p className="text-muted-foreground">Offres actives</p>
            <p className="font-bold text-foreground">{jobs.length}</p>
          </div>
          <div>
            <p className="text-muted-foreground">En cours</p>
            <p className="font-bold text-foreground">{inProgress}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Embauchés</p>
            <p className="font-bold text-foreground">{hired}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={(e) => { e.stopPropagation(); navigate('/recruitment'); }}>
          Voir le recrutement <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </CardContent>
    </Card>
  );
}
