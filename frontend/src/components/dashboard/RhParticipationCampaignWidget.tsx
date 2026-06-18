import { useQuery } from '@tanstack/react-query';
import { Megaphone } from 'lucide-react';
import { Link } from 'react-router-dom';

import { listCampaigns } from '@/api/participation';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

export function RhParticipationCampaignWidget() {
  const companyId = useActiveCompanyId();
  const year = new Date().getFullYear();

  const { data: campaigns = [] } = useQuery({
    queryKey: ['participation-campaigns', year, companyId],
    queryFn: () => listCampaigns(year),
    enabled: Boolean(companyId),
    refetchInterval: 120_000,
  });

  const open = campaigns.find((c) => c.status === 'open');
  if (!open) return null;

  const late = open.stats.sent;

  return (
    <Card className="border-amber-200 bg-amber-50/60 dark:border-amber-900/40 dark:bg-amber-950/15">
      <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="flex items-start gap-2">
          <Megaphone className="mt-0.5 h-5 w-5 text-amber-700" />
          <div>
            <p className="text-sm font-medium">Campagne participation {open.year}</p>
            <p className="text-sm text-muted-foreground">
              {open.stats.responded + open.stats.default_pee}/{open.stats.total} réponses
              {late > 0 ? ` — ${late} en attente` : ''}
            </p>
          </div>
        </div>
        <Button variant="secondary" size="sm" asChild>
          <Link to="/saisies">Suivre</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
