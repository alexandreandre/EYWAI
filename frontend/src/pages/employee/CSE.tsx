// Page CSE/BDES pour les élus (espace salarié)

import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { CSEBadge } from '@/components/CSEBadge';
import { DelegationHourModal } from '@/components/cse/DelegationHourModal';
import { EmployeeCseDelegationBanner } from '@/components/employee-cse/EmployeeCseDelegationBanner';
import { EmployeeCseDelegationTab } from '@/components/employee-cse/EmployeeCseDelegationTab';
import { EmployeeCseDocumentsTab } from '@/components/employee-cse/EmployeeCseDocumentsTab';
import { EmployeeCseMeetingsTab } from '@/components/employee-cse/EmployeeCseMeetingsTab';
import { EmployeeCsePageSkeleton } from '@/components/skeletons/EmployeeCsePageSkeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  getBDESDocuments,
  getDelegationCredit,
  getDelegationHours,
  getMeetings,
  getMyElectedStatus,
} from '@/api/cse';
import {
  isEmployeeCseTab,
  mandateDaysRemaining,
  type EmployeeCseTab,
} from '@/lib/employeeCseUtils';
import { formatCseDate } from '@/lib/employeeCseUtils';
import { cn } from '@/lib/utils';
import { Calendar, Clock, FileText, Home, Info } from 'lucide-react';

export default function EmployeeCSE() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [hourModalOpen, setHourModalOpen] = useState(false);

  const tabParam = searchParams.get('tab');
  const activeTab: EmployeeCseTab = isEmployeeCseTab(tabParam) ? tabParam : 'meetings';

  const setActiveTab = (tab: string) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (tab === 'meetings') {
          next.delete('tab');
        } else {
          next.set('tab', tab);
        }
        return next;
      },
      { replace: true }
    );
  };

  const { data: electedStatus, isLoading: loadingStatus, isError: statusError } = useQuery({
    queryKey: ['cse', 'my-elected-status'],
    queryFn: () => getMyElectedStatus(),
  });

  const isElected = electedStatus?.is_elected === true;

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

  const {
    data: meetings = [],
    isLoading: loadingMeetings,
    isError: meetingsError,
  } = useQuery({
    queryKey: ['cse', 'my-meetings'],
    queryFn: () => getMeetings(),
    enabled: isElected,
  });

  const {
    data: credit,
    isLoading: loadingCredit,
    isError: creditError,
  } = useQuery({
    queryKey: ['cse', 'my-delegation-credit', now.getFullYear(), now.getMonth() + 1],
    queryFn: () => getDelegationCredit(now.getFullYear(), now.getMonth() + 1),
    enabled: isElected,
  });

  const {
    data: hours = [],
    isLoading: loadingHours,
    isError: hoursError,
  } = useQuery({
    queryKey: ['cse', 'my-delegation-hours', monthStart, monthEnd],
    queryFn: () => getDelegationHours(undefined, monthStart, monthEnd),
    enabled: isElected,
  });

  const {
    data: bdesDocuments = [],
    isLoading: loadingBDES,
    isError: bdesError,
  } = useQuery({
    queryKey: ['cse', 'bdes-documents'],
    queryFn: () => getBDESDocuments(),
    enabled: isElected,
  });

  const meetingsWithMinutes = useMemo(
    () => meetings.filter((m) => m.status === 'terminee' && m.has_minutes),
    [meetings]
  );

  const consumedHours = credit?.consumed_hours ?? hours.reduce((sum, h) => sum + h.duration_hours, 0);
  const quotaHours = credit?.credit_base ?? credit?.quota_hours_per_month ?? 0;
  const remainingHours = credit?.remaining_hours ?? quotaHours - consumedHours;
  const isNearLimit = credit?.is_near_limit ?? (quotaHours > 0 && remainingHours <= quotaHours * 0.2 && remainingHours > 0);
  const isOverLimit = credit?.is_over_limit ?? remainingHours < 0;

  useEffect(() => {
    if (!isElected || loadingCredit || loadingHours) return;
    if ((isNearLimit || isOverLimit) && activeTab === 'meetings' && !tabParam) {
      setActiveTab('delegation');
    }
  }, [isElected, isNearLimit, isOverLimit, loadingCredit, loadingHours, activeTab, tabParam]);

  if (loadingStatus) {
    return <EmployeeCsePageSkeleton />;
  }

  if (statusError) {
    return (
      <Alert variant="destructive">
        <Info className="h-4 w-4" />
        <AlertDescription>
          Impossible de vérifier votre statut CSE. Réessayez plus tard.
        </AlertDescription>
      </Alert>
    );
  }

  if (!isElected) {
    return (
      <EmployeePageShell className="mx-auto max-w-lg">
        <EmployeePageHeader
          title="CSE / BDES"
          description="Cet espace est réservé aux élus du CSE de votre entreprise."
        />
        <Button variant="outline" className="w-full" asChild>
          <Link to="/">
            <Home className="mr-2 h-4 w-4" />
            Retour au tableau de bord
          </Link>
        </Button>
      </EmployeePageShell>
    );
  }

  const mandate = electedStatus.current_mandate;
  const daysRemaining = mandate?.end_date
    ? mandateDaysRemaining(mandate.end_date)
    : null;

  const partialError = meetingsError || creditError || hoursError || bdesError;

  const bannerProps = {
    creditBase: credit?.credit_base ?? quotaHours,
    reportedAvailable: credit?.reported_available ?? 0,
    transfersIn: credit?.transfers_in ?? 0,
    monthlyCap: credit?.monthly_cap ?? quotaHours * 1.5,
    quotaHours,
    consumedHours,
    remainingHours,
    isNearLimit,
    isOverLimit,
    warnings: credit?.warnings ?? [],
    onSaisirHeure: () => setHourModalOpen(true),
  };

  return (
    <EmployeePageShell>
      <div className="space-y-3">
        <EmployeePageHeader
          title="CSE / BDES"
          description="Réunions, délégation et documents de l'entreprise"
        />
        {mandate ? (
          <div className="flex flex-wrap items-center gap-2">
            <CSEBadge
              role={mandate.role}
              college={mandate.college}
              startDate={mandate.start_date}
              endDate={mandate.end_date}
              daysRemaining={daysRemaining}
            />
            <span className="text-sm text-muted-foreground">
              Mandat du {formatCseDate(mandate.start_date)} au{' '}
              {formatCseDate(mandate.end_date)}
            </span>
            {daysRemaining !== null && daysRemaining <= 90 && (
              <Badge variant={daysRemaining < 0 ? 'destructive' : 'secondary'}>
                {daysRemaining > 0
                  ? `${daysRemaining} j restant${daysRemaining > 1 ? 's' : ''}`
                  : 'Mandat expiré'}
              </Badge>
            )}
          </div>
        ) : null}
      </div>

      {partialError && (
        <Alert variant="destructive">
          <Info className="h-4 w-4" />
          <AlertDescription>
            Certaines informations n&apos;ont pas pu être chargées. Réessayez en
            rafraîchissant la page.
          </AlertDescription>
        </Alert>
      )}

      <div className="lg:hidden">
        <EmployeeCseDelegationBanner {...bannerProps} />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList
          className={cn(
            'inline-flex h-auto w-full max-w-full justify-start gap-1 overflow-x-auto p-1',
            'scrollbar-thin'
          )}
        >
          <TabsTrigger value="meetings" className="shrink-0 gap-1.5">
            <Calendar className="h-4 w-4" />
            Réunions
          </TabsTrigger>
          <TabsTrigger value="delegation" className="shrink-0 gap-1.5">
            <Clock className="h-4 w-4" />
            Délégation
          </TabsTrigger>
          <TabsTrigger value="documents" className="shrink-0 gap-1.5">
            <FileText className="h-4 w-4" />
            Documents
          </TabsTrigger>
        </TabsList>

        <TabsContent value="meetings" className="mt-4 space-y-4">
          <EmployeeCseMeetingsTab
            meetings={meetings}
            isLoading={loadingMeetings}
            isError={meetingsError}
          />
        </TabsContent>

        <TabsContent value="delegation" className="mt-4 space-y-4">
          <div className="hidden lg:block">
            <EmployeeCseDelegationBanner {...bannerProps} compact />
          </div>
          <EmployeeCseDelegationTab
            hours={hours}
            isLoading={loadingHours || loadingCredit}
            isError={hoursError || creditError}
          />
        </TabsContent>

        <TabsContent value="documents" className="mt-4 space-y-4">
          <EmployeeCseDocumentsTab
            documents={bdesDocuments}
            meetingsWithMinutes={meetingsWithMinutes}
            isLoading={loadingBDES || loadingMeetings}
            isError={bdesError || meetingsError}
          />
        </TabsContent>
      </Tabs>

      {hourModalOpen && (
        <DelegationHourModal open={hourModalOpen} onOpenChange={setHourModalOpen} />
      )}
    </EmployeePageShell>
  );
}
