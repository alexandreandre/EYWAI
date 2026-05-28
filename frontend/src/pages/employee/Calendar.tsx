import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { format, startOfWeek } from 'date-fns';
import type { Shift } from '@/api/planning';
import { useAuth } from '@/contexts/AuthContext';
import { useCalendar } from '@/hooks/useCalendar';
import { useEmployeeMonthShifts } from '@/hooks/useEmployeeMonthShifts';
import { useEmployeeProfileQuery } from '@/hooks/queries/useEmployeeDashboardQueries';
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { CalendarKpiBand } from '@/components/employee-detail/CalendarKpiBand';
import { CalendarAbsencesHint } from '@/components/employee-detail/CalendarAbsencesHint';
import { YearCalendarView } from '@/components/schedules/YearCalendarView';
import { EmployeeCalendarDayCell } from '@/components/EmployeeCalendarDayCell';
import { EmployeeCalendarLegend } from '@/components/employee-calendar/EmployeeCalendarLegend';
import { EmployeeCalendarGridSkeleton } from '@/components/employee-calendar/EmployeeCalendarGridSkeleton';
import { EmployeeCalendarMonthList } from '@/components/employee-calendar/EmployeeCalendarMonthList';
import { EmployeeCalendarDaySheet } from '@/components/employee-calendar/EmployeeCalendarDaySheet';
import { EmployeePlanningWeekView } from '@/components/employee-calendar/EmployeePlanningWeekView';
import {
  ChevronLeft,
  ChevronRight,
  CalendarDays,
  Grid3x3,
  Plane,
  ScanLine,
  AlertCircle,
  CalendarClock,
} from 'lucide-react';
import { isMonthUnfilledByRh, monthHasSignificantEcart } from '@/lib/employeeCalendarUtils';
import {
  type CalendarHubView,
  parseCalendarHubView,
  defaultWeekStartIso,
  weekStartFromYearMonth,
  yearMonthFromWeekStart,
} from '@/lib/employeeCalendarPlanning';

const DAY_HEADERS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

export default function EmployeeCalendarPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const hubView = parseCalendarHubView(searchParams.get('view'));
  const weekFromUrl = searchParams.get('week');

  const [weekStart, setWeekStart] = useState(() => weekFromUrl?.slice(0, 10) || defaultWeekStartIso());
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetShifts, setSheetShifts] = useState<Shift[]>([]);

  const {
    data: profile,
    isLoading: isProfileLoading,
    isError: isProfileError,
  } = useEmployeeProfileQuery(user?.id);
  const resolvedEmployeeId = profile?.id;
  const employeeStatut = profile?.statut ?? undefined;
  const needsEmployeeProfile = hubView === 'month' || hubView === 'year';
  const profileUnavailable =
    needsEmployeeProfile &&
    Boolean(user?.id) &&
    !isProfileLoading &&
    (isProfileError || !resolvedEmployeeId);

  const {
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    actualHours,
    isLoading: isCalendarLoading,
    loadError,
    refetch,
    monthCompletionStatus,
    isForfaitJour,
  } = useCalendar(resolvedEmployeeId, employeeStatut);

  const setHubView = useCallback(
    (view: CalendarHubView) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set('view', view);
          if (view === 'week') {
            next.set('week', weekStart.slice(0, 10));
          } else {
            next.delete('week');
          }
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams, weekStart]
  );

  const handleWeekStartChange = useCallback(
    (iso: string) => {
      setWeekStart(iso);
      if (hubView === 'week') {
        setSearchParams(
          (prev) => {
            const next = new URLSearchParams(prev);
            next.set('view', 'week');
            next.set('week', iso.slice(0, 10));
            return next;
          },
          { replace: true }
        );
      }
      const { year, month } = yearMonthFromWeekStart(iso);
      setSelectedDate({ year, month });
    },
    [hubView, setSearchParams, setSelectedDate]
  );

  const handleViewChange = useCallback(
    (view: CalendarHubView) => {
      if (view === 'month' || view === 'year') {
        const { year, month } = yearMonthFromWeekStart(weekStart);
        setSelectedDate({ year, month });
      }
      if (view === 'week') {
        const anchor = new Date(selectedDate.year, selectedDate.month - 1, 1);
        const monday = format(startOfWeek(anchor, { weekStartsOn: 1 }), 'yyyy-MM-dd');
        setWeekStart(monday);
      }
      setHubView(view);
    },
    [weekStart, selectedDate.year, selectedDate.month, setSelectedDate, setHubView]
  );

  const year = selectedDate.year;
  const monthIndex = selectedDate.month - 1;
  const firstDay = new Date(year, monthIndex, 1);
  const lastDay = new Date(year, selectedDate.month, 0);
  const daysInMonth = lastDay.getDate();
  const startDayOfWeek = (firstDay.getDay() + 6) % 7;

  const monthLabel = new Date(year, monthIndex).toLocaleString('fr-FR', {
    month: 'long',
    year: 'numeric',
  });

  const {
    shiftsByDay: monthShiftsByDay,
    isLoading: isMonthShiftsLoading,
  } = useEmployeeMonthShifts(year, selectedDate.month, hubView === 'month');

  const showMonthUnfilled = useMemo(
    () =>
      !isCalendarLoading &&
      !loadError &&
      isMonthUnfilledByRh(plannedCalendar, year, selectedDate.month),
    [isCalendarLoading, loadError, plannedCalendar, year, selectedDate.month]
  );

  const showMonthEcart = useMemo(
    () =>
      !isCalendarLoading &&
      !loadError &&
      monthHasSignificantEcart(plannedCalendar, actualHours, isForfaitJour),
    [isCalendarLoading, loadError, plannedCalendar, actualHours, isForfaitJour]
  );

  const handlePrevious = () => {
    if (hubView === 'month') {
      const d = new Date(year, monthIndex - 1, 1);
      setSelectedDate({ month: d.getMonth() + 1, year: d.getFullYear() });
    } else if (hubView === 'year') {
      setSelectedDate({ month: selectedDate.month, year: year - 1 });
    }
  };

  const handleNext = () => {
    if (hubView === 'month') {
      const d = new Date(year, monthIndex + 1, 1);
      setSelectedDate({ month: d.getMonth() + 1, year: d.getFullYear() });
    } else if (hubView === 'year') {
      setSelectedDate({ month: selectedDate.month, year: year + 1 });
    }
  };

  const goToCurrentMonth = () => {
    const now = new Date();
    setSelectedDate({ month: now.getMonth() + 1, year: now.getFullYear() });
    setHubView('month');
  };

  const openDaySheet = useCallback(
    (day: number, shifts: Shift[] = []) => {
      setSelectedDay(day);
      setSheetShifts(shifts);
      setSheetOpen(true);
    },
    []
  );

  const handleDayClick = (day: number) => {
    openDaySheet(day, monthShiftsByDay[day] ?? []);
  };

  const handleWeekDayClick = useCallback(
    (payload: {
      iso: string;
      day: number;
      year: number;
      month: number;
      shifts: Shift[];
    }) => {
      if (
        payload.year !== selectedDate.year ||
        payload.month !== selectedDate.month
      ) {
        setSelectedDate({ year: payload.year, month: payload.month });
      }
      openDaySheet(payload.day, payload.shifts);
    },
    [selectedDate.year, selectedDate.month, setSelectedDate, openDaySheet]
  );

  const handleViewWeekFromSheet = useCallback(
    (iso: string) => {
      setWeekStart(iso);
      setHubView('week');
    },
    [setHubView]
  );

  useEffect(() => {
    const urlView = searchParams.get('view');
    const urlWeek = searchParams.get('week');
    if (urlWeek && urlWeek.slice(0, 10) !== weekStart.slice(0, 10)) {
      setWeekStart(urlWeek.slice(0, 10));
    }
    if (!urlView) {
      const params: Record<string, string> = { view: hubView };
      if (hubView === 'week') params.week = weekStart.slice(0, 10);
      setSearchParams(params, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- init URL une fois au montage
  }, []);

  const selectedPlanned = selectedDay
    ? plannedCalendar.find((d) => d.jour === selectedDay)
    : undefined;
  const selectedActual = selectedDay
    ? actualHours.find((d) => d.jour === selectedDay)
    : undefined;

  const resolvedSheetShifts =
    sheetShifts.length > 0
      ? sheetShifts
      : selectedDay
        ? monthShiftsByDay[selectedDay] ?? []
        : [];

  const headerStatusBadge = useMemo(() => {
    if (hubView === 'month' && !isCalendarLoading && !loadError) {
      return (
        <Badge
          variant={monthCompletionStatus === 'saisi' ? 'secondary' : 'outline'}
          className="text-xs font-normal"
        >
          {monthCompletionStatus === 'saisi' ? 'Mois renseigné RH' : 'Mois en cours de saisie RH'}
        </Badge>
      );
    }
    return null;
  }, [hubView, isCalendarLoading, loadError, monthCompletionStatus]);

  const showPeriodNav = hubView === 'month' || hubView === 'year';

  return (
    <EmployeePageShell>
      <EmployeePageHeader
        title="Calendrier et planning"
        description="Vos horaires publiés et votre suivi mensuel paie (lecture seule)"
        icon={<CalendarDays />}
        afterDescription={headerStatusBadge ?? undefined}
        actions={
          <>
            <Button variant="outline" size="sm" asChild>
              <Link to="/absences">
                <Plane className="mr-2 h-4 w-4" />
                Congés & absences
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/badgeuse">
                <ScanLine className="mr-2 h-4 w-4" />
                Ma badgeuse
              </Link>
            </Button>
          </>
        }
      />

      <ToggleGroup
        type="single"
        value={hubView}
        onValueChange={(v) => v && handleViewChange(v as CalendarHubView)}
        className="flex w-full justify-start rounded-lg border p-1"
      >
        <ToggleGroupItem
          value="week"
          className="flex h-9 min-w-0 flex-1 justify-center gap-1.5 px-2"
        >
          <CalendarClock className="h-4 w-4 shrink-0" />
          <span className="text-xs">Semaine</span>
        </ToggleGroupItem>
        <ToggleGroupItem
          value="month"
          className="flex h-9 min-w-0 flex-1 justify-center gap-1.5 px-2"
        >
          <CalendarDays className="h-4 w-4 shrink-0" />
          <span className="text-xs">Mois</span>
        </ToggleGroupItem>
        <ToggleGroupItem
          value="year"
          className="flex h-9 min-w-0 flex-1 justify-center gap-1.5 px-2"
        >
          <Grid3x3 className="h-4 w-4 shrink-0" />
          <span className="text-xs">Année</span>
        </ToggleGroupItem>
      </ToggleGroup>

      {isForfaitJour && hubView === 'month' && (
        <div className="rounded-md border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
          <span className="font-medium">Forfait jour</span>
          {' — '}
          les durées sont exprimées en jours travaillés (oui / non).
        </div>
      )}

      {hubView === 'week' ? (
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <EmployeePlanningWeekView
              weekStart={weekStart}
              onWeekStartChange={handleWeekStartChange}
              onDayClick={handleWeekDayClick}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader className="pb-3">
            {showPeriodNav && (
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex flex-1 items-center justify-center gap-1 sm:justify-start">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handlePrevious}
                    aria-label={hubView === 'month' ? 'Mois précédent' : 'Année précédente'}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="min-w-[9rem] text-center text-lg font-semibold capitalize">
                    {hubView === 'month' ? monthLabel : selectedDate.year}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleNext}
                    aria-label={hubView === 'month' ? 'Mois suivant' : 'Année suivante'}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
                {hubView === 'month' && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs sm:ml-auto"
                    onClick={goToCurrentMonth}
                  >
                    Mois en cours
                  </Button>
                )}
              </div>
            )}
          </CardHeader>

          <CardContent className="space-y-3 p-4 md:p-6">
            {hubView === 'month' && resolvedEmployeeId && (
              <CalendarAbsencesHint
                employeeId={resolvedEmployeeId}
                year={selectedDate.year}
                month={selectedDate.month}
              />
            )}

            {hubView === 'month' && showMonthEcart && (
              <div className="flex items-start gap-2 rounded-md border border-amber-200/80 bg-amber-50/80 px-3 py-2 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <p>Écart notable entre le total prévu et le total réalisé sur ce mois.</p>
              </div>
            )}

            {profileUnavailable ? (
              <div className="rounded-md border border-amber-200/80 bg-amber-50/90 px-4 py-8 text-center text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
                <p className="font-medium">Fiche salarié introuvable</p>
                <p className="mt-2 text-muted-foreground">
                  Votre compte n&apos;est pas relié à une fiche dans cette entreprise.
                  Contactez le service RH pour accéder à votre calendrier paie.
                </p>
              </div>
            ) : needsEmployeeProfile && isProfileLoading ? (
              <EmployeeCalendarGridSkeleton />
            ) : hubView === 'month' && loadError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-8 text-center">
                <p className="text-sm text-destructive">
                  Impossible de charger votre calendrier paie.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => void refetch()}
                >
                  Réessayer
                </Button>
              </div>
            ) : hubView === 'month' && isCalendarLoading ? (
              <EmployeeCalendarGridSkeleton />
            ) : hubView === 'year' && resolvedEmployeeId ? (
              <YearCalendarView
                year={selectedDate.year}
                employeeId={resolvedEmployeeId}
                isForfaitJour={isForfaitJour}
                onMonthClick={(m) => {
                  setSelectedDate({ year: selectedDate.year, month: m });
                  setWeekStart(weekStartFromYearMonth(selectedDate.year, m));
                  setHubView('month');
                }}
              />
            ) : hubView === 'month' ? (
              <>
                <CalendarKpiBand
                  plannedCalendar={plannedCalendar}
                  actualHours={actualHours}
                  isForfaitJour={isForfaitJour}
                  className="px-0"
                />

                {showMonthUnfilled && (
                  <p className="rounded-md border border-dashed bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                    Votre service RH n&apos;a pas encore renseigné ce mois.
                  </p>
                )}

                {isMonthShiftsLoading && (
                  <p className="text-xs text-muted-foreground">Chargement des créneaux publiés…</p>
                )}

                <EmployeeCalendarMonthList
                  year={year}
                  month={monthIndex}
                  daysInMonth={daysInMonth}
                  plannedCalendar={plannedCalendar}
                  actualHours={actualHours}
                  isForfaitJour={isForfaitJour}
                  shiftsByDay={monthShiftsByDay}
                  onDayClick={handleDayClick}
                />

                <div className="hidden flex-col gap-3 md:flex">
                  <div className="grid grid-cols-7 text-center text-xs font-medium text-muted-foreground">
                    {DAY_HEADERS.map((name) => (
                      <div key={name}>{name}</div>
                    ))}
                  </div>
                  <div className="grid grid-cols-7 gap-1.5">
                    {Array.from({ length: startDayOfWeek }).map((_, i) => (
                      <div key={`empty-${i}`} className="min-h-[5.5rem]" />
                    ))}
                    {Array.from({ length: daysInMonth }).map((_, i) => {
                      const day = i + 1;
                      const date = new Date(year, monthIndex, day);
                      const isToday = date.toDateString() === new Date().toDateString();
                      return (
                        <EmployeeCalendarDayCell
                          key={day}
                          day={day}
                          isToday={isToday}
                          plannedCalendar={plannedCalendar}
                          actualHours={actualHours}
                          isForfaitJour={isForfaitJour}
                          dayShifts={monthShiftsByDay[day] ?? []}
                          onDayClick={handleDayClick}
                        />
                      );
                    })}
                  </div>
                </div>

                <EmployeeCalendarLegend showPlanningPastille />
              </>
            ) : null}
          </CardContent>
        </Card>
      )}

      <EmployeeCalendarDaySheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        day={selectedDay}
        year={year}
        month={selectedDate.month}
        planned={selectedPlanned}
        actual={selectedActual}
        isForfaitJour={isForfaitJour}
        dayShifts={resolvedSheetShifts}
        isPayrollLoading={isCalendarLoading && sheetOpen}
        onViewWeek={handleViewWeekFromSheet}
      />
    </EmployeePageShell>
  );
}
