import { Link } from 'react-router-dom';
import { AlertCircle, ScanLine, ArrowRight, Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getMyBadgeQr } from '@/api/badgeuse';
import { useEmployeeBadgeuseTodayQuery } from '@/hooks/queries/useEmployeeDashboardQueries';
import { BadgeQrDisplay } from '@/components/badgeuse/BadgeQrDisplay';
import { formatSecondsToHoursMinutes } from '@/lib/badgeuseFormat';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/contexts/AuthContext';

export function EmployeeBadgeuseDashboardCard() {
  const { user } = useAuth();
  const { data, isLoading, isError } = useEmployeeBadgeuseTodayQuery(user?.id);

  const { data: qrFallback } = useQuery({
    queryKey: ['badgeuse', 'my-qr'],
    queryFn: getMyBadgeQr,
    enabled: Boolean(user?.id) && Boolean(data?.is_eligible_for_badgeuse) && !data?.qr_payload,
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Chargement de la badgeuse…
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="border-destructive/40 bg-destructive/5">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <p className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            Impossible de charger le statut badgeuse.
          </p>
          <Button variant="outline" size="sm" asChild>
            <Link to="/badgeuse">Ouvrir la badgeuse</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  if (!data.is_eligible_for_badgeuse) return null;

  const inPresence = data.next_action === 'SORTIE';
  const totalLabel =
    data.total_seconds != null
      ? formatSecondsToHoursMinutes(data.total_seconds)
      : null;
  const qrPayload = data.qr_payload ?? qrFallback?.qr_payload;
  const qrDisplayName =
    data.employee_display_name ?? qrFallback?.employee_display_name;
  const qrUsername = data.badge_username ?? qrFallback?.badge_username;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <ScanLine className="h-5 w-5 text-primary" />
          Ma badgeuse aujourd&apos;hui
        </CardTitle>
        <Button variant="ghost" size="sm" asChild className="h-8 gap-1 px-2">
          <Link to="/badgeuse">
            Ouvrir
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="flex flex-wrap items-start gap-4">
        {qrPayload && (
          <BadgeQrDisplay
            payload={qrPayload}
            displayName={qrDisplayName}
            username={qrUsername}
            size={120}
            className="p-4 shadow-none"
          />
        )}
        <div className="flex min-w-[180px] flex-1 flex-col gap-3">
          <Badge variant={inPresence ? 'success' : 'secondary'}>
            {data.status_label ?? (inPresence ? 'En présence' : 'Hors présence')}
          </Badge>
          {totalLabel && (
            <span className="text-sm text-muted-foreground">
              Temps pointé : <strong className="text-foreground">{totalLabel}</strong>
            </span>
          )}
          {data.next_action && (
            <span className="text-xs text-muted-foreground">
              Prochaine action :{' '}
              {data.next_action === 'ENTREE' ? 'Pointer entrée' : 'Pointer sortie'}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
