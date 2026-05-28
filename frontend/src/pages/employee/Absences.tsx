import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { fr } from 'date-fns/locale';
import { AlertCircle, Clock, PlusCircle } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import type { AbsenceBalance, AbsenceRequest, SalaryCertificate } from '@/api/absences';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { AbsenceRequestModal } from '@/components/AbsenceRequestModal';
import { EmployeeAbsenceBalanceRow } from '@/components/employee-absences/EmployeeAbsenceBalanceRow';
import { EmployeeAbsenceDaySheet } from '@/components/employee-absences/EmployeeAbsenceDaySheet';
import { EmployeeAbsenceRequestsSection } from '@/components/employee-absences/EmployeeAbsenceRequestsSection';
import { EmployeeAbsencesPageSkeleton } from '@/components/skeletons/EmployeeAbsencesPageSkeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { useEmployeeAbsencesPageQuery } from '@/hooks/queries/useEmployeeDashboardQueries';
import {
  type AbsenceStatusFilter,
  absencesOnCalendarDay,
  filterAbsencesByStatus,
} from '@/lib/employeeAbsencesUtils';
import {
  ABSENCE_CALENDAR_MODIFIERS_CLASS_NAMES,
  buildAbsenceCalendarModifiers,
  CALENDAR_LEGEND,
  formatMonthYear,
  getNextValidatedAbsenceDate,
} from '@/lib/employeeDashboardUtils';
import { queryKeys } from '@/lib/queryKeys';
import { cn } from '@/lib/utils';

const VALID_STATUS_PARAMS = new Set<AbsenceStatusFilter>([
  'pending',
  'validated',
  'rejected',
  'cancelled',
]);

export default function AbsencesPage() {
  const { user } = useAuth();
  const userId = user?.id;
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [currentMonth, setCurrentMonth] = useState(() => new Date());
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [certificates, setCertificates] = useState<Record<string, SalaryCertificate>>({});
  const [loadingCertificates, setLoadingCertificates] = useState<Set<string>>(new Set());
  const [selectedCalendarDay, setSelectedCalendarDay] = useState<Date | null>(null);
  const [daySheetOpen, setDaySheetOpen] = useState(false);
  const requestsListRef = useRef<HTMLDivElement>(null);

  const calendarYear = currentMonth.getFullYear();
  const calendarMonth = currentMonth.getMonth() + 1;

  const pageQuery = useEmployeeAbsencesPageQuery(userId, calendarYear, calendarMonth);

  const statusFilter = useMemo((): AbsenceStatusFilter => {
    const raw = searchParams.get('status');
    if (raw && VALID_STATUS_PARAMS.has(raw as AbsenceStatusFilter)) {
      return raw as AbsenceStatusFilter;
    }
    return 'all';
  }, [searchParams]);

  const balances: AbsenceBalance[] = pageQuery.data?.balances ?? [];
  const calendarDays = pageQuery.data?.calendar_days ?? [];
  const myAbsences: AbsenceRequest[] = pageQuery.data?.history ?? [];

  const pendingCount = useMemo(
    () => myAbsences.filter((a) => a.status === 'pending').length,
    [myAbsences]
  );

  const filteredAbsences = useMemo(
    () => filterAbsencesByStatus(myAbsences, statusFilter),
    [myAbsences, statusFilter]
  );

  const nextAbsenceDate = useMemo(
    () => getNextValidatedAbsenceDate(myAbsences),
    [myAbsences]
  );

  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const calendarModifiers = useMemo(
    () =>
      buildAbsenceCalendarModifiers(
        calendarDays,
        currentMonth,
        today,
        nextAbsenceDate
      ),
    [calendarDays, currentMonth, nextAbsenceDate, today]
  );

  const daySheetAbsences = useMemo(() => {
    if (!selectedCalendarDay) return [];
    return absencesOnCalendarDay(myAbsences, selectedCalendarDay);
  }, [myAbsences, selectedCalendarDay]);

  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setIsModalOpen(true);
    }
  }, [searchParams]);

  const handleStatusFilterChange = (filter: AbsenceStatusFilter) => {
    const next = new URLSearchParams(searchParams);
    if (filter === 'all') {
      next.delete('status');
    } else {
      next.set('status', filter);
    }
    setSearchParams(next, { replace: true });
  };

  const openRequestModal = () => {
    setIsModalOpen(true);
    const next = new URLSearchParams(searchParams);
    next.set('new', '1');
    setSearchParams(next, { replace: true });
  };

  const closeRequestModal = () => {
    setIsModalOpen(false);
    const next = new URLSearchParams(searchParams);
    next.delete('new');
    setSearchParams(next, { replace: true });
  };

  const refreshPageData = useCallback(() => {
    if (!userId) return;
    void queryClient.invalidateQueries({
      queryKey: [...queryKeys.employeeDashboard(userId), 'absences'],
    });
  }, [queryClient, userId]);

  const handleCertificateLoaded = (absenceId: string, cert: SalaryCertificate) => {
    setCertificates((prev) => ({ ...prev, [absenceId]: cert }));
  };

  const handleCertificateLoading = (absenceId: string, loading: boolean) => {
    setLoadingCertificates((prev) => {
      const next = new Set(prev);
      if (loading) next.add(absenceId);
      else next.delete(absenceId);
      return next;
    });
  };

  const scrollToRequests = () => {
    requestsListRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    handleStatusFilterChange('pending');
  };

  if (!userId) {
    return (
      <p className="text-sm text-muted-foreground">
        Connectez-vous pour accéder à vos congés et absences.
      </p>
    );
  }

  if (pageQuery.isLoading && !pageQuery.data) {
    return <EmployeeAbsencesPageSkeleton />;
  }

  const isFetchingOverlay = pageQuery.isFetching && !pageQuery.isLoading;

  return (
    <EmployeePageShell>
      <EmployeePageHeader
        title="Congés & Absences"
        description="Soldes, demandes et calendrier du mois"
        actions={
          <Button onClick={openRequestModal}>
            <PlusCircle className="mr-2 h-4 w-4" />
            Faire une demande
          </Button>
        }
      />

      {pendingCount > 0 && (
        <Alert className="border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30">
          <Clock className="h-4 w-4 text-amber-700" />
          <AlertDescription className="flex flex-wrap items-center justify-between gap-2 text-amber-950 dark:text-amber-100">
            <span>
              {pendingCount} demande{pendingCount > 1 ? 's' : ''} en attente de
              validation
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="border-amber-300 bg-white hover:bg-amber-100 dark:bg-transparent"
              onClick={scrollToRequests}
            >
              Voir les demandes
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {pageQuery.isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Impossible de charger les données. Réessayez en changeant de mois ou
            en rafraîchissant la page.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Colonne principale : soldes puis demandes (mobile : calendrier entre les deux via order) */}
        <div className="order-1 space-y-6 lg:order-1 lg:col-span-2">
          <Card className="order-1">
            <CardHeader>
              <CardTitle>Mes soldes</CardTitle>
              <CardDescription>
                Droits acquis et jours restants sur la période en cours
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-1">
              {balances.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Soldes non disponibles.
                </p>
              ) : (
                balances.map((b) => (
                  <EmployeeAbsenceBalanceRow
                    key={b.type}
                    balance={b}
                    showAcquired
                  />
                ))
              )}
            </CardContent>
          </Card>

          {/* Calendrier : visible avant l'historique sur mobile */}
          <Card className="relative order-2 lg:hidden">
            <CardHeader>
              <CardTitle>Calendrier</CardTitle>
              <CardDescription>
                {formatMonthYear(calendarMonth, calendarYear)}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col items-center">
              {isFetchingOverlay && (
                <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-background/50">
                  <span className="sr-only">Chargement du calendrier</span>
                </div>
              )}
              {nextAbsenceDate && (
                <p className="mb-3 w-full text-center text-xs text-muted-foreground">
                  Prochaine absence validée :{' '}
                  <span className="font-medium text-foreground">
                    {nextAbsenceDate.toLocaleDateString('fr-FR')}
                  </span>
                </p>
              )}
              <Calendar
                mode="single"
                locale={fr}
                month={currentMonth}
                onMonthChange={setCurrentMonth}
                className="rounded-md border p-0"
                weekStartsOn={1}
                modifiers={calendarModifiers}
                modifiersClassNames={ABSENCE_CALENDAR_MODIFIERS_CLASS_NAMES}
                onDayClick={(day) => {
                  setSelectedCalendarDay(day);
                  setDaySheetOpen(true);
                }}
              />
              <CalendarLegend />
            </CardContent>
          </Card>

          <div className="order-3">
            <EmployeeAbsenceRequestsSection
              absences={filteredAbsences}
              statusFilter={statusFilter}
              onStatusFilterChange={handleStatusFilterChange}
              certificates={certificates}
              loadingCertificates={loadingCertificates}
              onCertificateLoaded={handleCertificateLoaded}
              onCertificateLoading={handleCertificateLoading}
              listRef={requestsListRef}
            />
          </div>
        </div>

        {/* Calendrier desktop */}
        <Card className="relative order-2 hidden lg:order-2 lg:block">
          <CardHeader>
            <CardTitle>Calendrier</CardTitle>
            <CardDescription>
              {formatMonthYear(calendarMonth, calendarYear)}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center">
            {isFetchingOverlay && (
              <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-background/50">
                <span className="sr-only">Chargement du calendrier</span>
              </div>
            )}
            {nextAbsenceDate && (
              <p className="mb-3 w-full text-center text-xs text-muted-foreground">
                Prochaine absence validée :{' '}
                <span className="font-medium text-foreground">
                  {nextAbsenceDate.toLocaleDateString('fr-FR')}
                </span>
              </p>
            )}
            <Calendar
              mode="single"
              locale={fr}
              month={currentMonth}
              onMonthChange={setCurrentMonth}
              className="rounded-md border p-0"
              weekStartsOn={1}
              modifiers={calendarModifiers}
              modifiersClassNames={ABSENCE_CALENDAR_MODIFIERS_CLASS_NAMES}
              onDayClick={(day) => {
                setSelectedCalendarDay(day);
                setDaySheetOpen(true);
              }}
            />
            <CalendarLegend />
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Cliquez sur un jour pour voir les demandes associées.
            </p>
          </CardContent>
        </Card>
      </div>

      <AbsenceRequestModal
        isOpen={isModalOpen}
        onClose={closeRequestModal}
        onSuccess={refreshPageData}
        balances={balances}
      />

      <EmployeeAbsenceDaySheet
        open={daySheetOpen}
        onOpenChange={setDaySheetOpen}
        day={selectedCalendarDay}
        absences={daySheetAbsences}
      />
    </EmployeePageShell>
  );
}

function CalendarLegend() {
  return (
    <div className="mt-4 w-full space-y-2 border-t pt-4">
      {Object.entries(CALENDAR_LEGEND).map(([key, { label, color }]) => (
        <div key={key} className="flex items-center text-sm">
          <span className={cn('mr-2 h-3 w-3 rounded-full', color)} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
