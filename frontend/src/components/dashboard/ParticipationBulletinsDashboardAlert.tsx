import { useQuery } from '@tanstack/react-query';
import { Megaphone } from 'lucide-react';
import { Link } from 'react-router-dom';

import { listMyParticipationBulletins } from '@/api/participation';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export function ParticipationBulletinsDashboardAlert() {
  const { data: bulletins = [] } = useQuery({
    queryKey: ['my-participation-bulletins'],
    queryFn: listMyParticipationBulletins,
    refetchInterval: 60_000,
  });

  const pending = bulletins.filter((b) => b.status === 'sent');
  if (pending.length === 0) return null;

  const title =
    pending.length === 1
      ? 'Bulletin d\'option à compléter'
      : `${pending.length} bulletins d'option à compléter`;

  return (
    <Card className="border-amber-200 bg-amber-50/80 dark:border-amber-900/50 dark:bg-amber-950/20">
      <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="flex min-w-0 items-start gap-2">
          <Megaphone className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
          <div className="min-w-0">
            <p className="text-sm font-medium">{title}</p>
            <p className="text-sm text-muted-foreground">
              Indiquez votre choix de placement (PEE ou numéraire) avant l&apos;échéance.
            </p>
          </div>
        </div>
        <Button variant="secondary" size="sm" asChild>
          <Link to="/employee/participation">Répondre</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
