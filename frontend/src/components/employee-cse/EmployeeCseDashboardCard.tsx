import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  getDelegationHours,
  getDelegationQuota,
  getMeetings,
  getMyElectedStatus,
} from '@/api/cse';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { formatCseDate, pickNextMeeting } from '@/lib/employeeCseUtils';
import { useAuth } from '@/contexts/AuthContext';
import { ArrowRight, Calendar, Clock, Handshake } from 'lucide-react';

export function EmployeeCseDashboardCard() {
  const { user } = useAuth();

  const { data: electedStatus, isLoading: loadingStatus } = useQuery({
    queryKey: ['cse', 'my-elected-status'],
    queryFn: () => getMyElectedStatus(),
    enabled: !!user,
  });

  const isElected = electedStatus?.is_elected === true;

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    .toISOString()
    .split('T')[0];
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    .toISOString()
    .split('T')[0];

  const { data: meetings = [] } = useQuery({
    queryKey: ['cse', 'my-meetings'],
    queryFn: () => getMeetings(),
    enabled: isElected,
  });

  const { data: quota } = useQuery({
    queryKey: ['cse', 'my-delegation-quota'],
    queryFn: () => getDelegationQuota(),
    enabled: isElected,
  });

  const { data: hours = [] } = useQuery({
    queryKey: ['cse', 'my-delegation-hours', monthStart, monthEnd],
    queryFn: () => getDelegationHours(undefined, monthStart, monthEnd),
    enabled: isElected,
  });

  if (loadingStatus) {
    return null;
  }

  if (!isElected) {
    return null;
  }

  const nextMeeting = pickNextMeeting(meetings);
  const consumedHours = hours.reduce((sum, h) => sum + h.duration_hours, 0);
  const quotaHours = quota?.quota_hours_per_month ?? 0;
  const remainingHours = quotaHours - consumedHours;
  const isLowQuota =
    quotaHours > 0 && remainingHours <= quotaHours * 0.2 && remainingHours >= 0;

  return (
    <Card className="border-blue-200/80 bg-blue-50/50 dark:border-blue-900/50 dark:bg-blue-950/20">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Handshake className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          Mon mandat CSE
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {nextMeeting ? (
          <div className="text-sm">
            <p className="font-medium text-muted-foreground">Prochaine réunion</p>
            <p className="flex items-center gap-1.5 font-semibold">
              <Calendar className="h-4 w-4 shrink-0" />
              {formatCseDate(nextMeeting.meeting_date)} — {nextMeeting.title}
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Aucune réunion à venir planifiée.</p>
        )}

        {quotaHours > 0 ? (
          <div className="text-sm">
            <p className="font-medium text-muted-foreground">Délégation (mois en cours)</p>
            <p
              className={`flex items-center gap-1.5 font-semibold ${
                isLowQuota ? 'text-amber-600' : ''
              }`}
            >
              <Clock className="h-4 w-4 shrink-0" />
              {remainingHours.toFixed(1)} h restantes sur {quotaHours} h
            </p>
          </div>
        ) : null}

        <Button variant="outline" size="sm" asChild className="w-full sm:w-auto">
          <Link to="/cse">
            Accéder à CSE / BDES
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
