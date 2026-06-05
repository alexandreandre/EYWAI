import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fr } from 'date-fns/locale';
import {
  CalendarDays,
  CheckCircle,
  CircleX,
  Clock,
  Euro,
  FileText,
  GraduationCap,
  Hourglass,
  Info,
  Receipt,
  ScanLine,
  TrendingUp,
  User,
  Wallet,
} from 'lucide-react';
import type { AbsenceRequest } from '@/api/absences';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { PendingSignaturesWidget } from '@/components/dashboard/PendingSignaturesWidget';
import { EmployeeBadgeuseDashboardCard } from '@/components/dashboard/EmployeeBadgeuseDashboardCard';
import { EmployeeCseDashboardCard } from '@/components/employee-cse/EmployeeCseDashboardCard';
import { EmployeeAbsenceBalanceRow } from '@/components/employee-absences/EmployeeAbsenceBalanceRow';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import {
  useEmployeeAbsencesPageQuery,
  useEmployeeCumulsQuery,
  useEmployeeExpensesQuery,
  useEmployeePayslipsQuery,
  useEmployeeProfileQuery,
} from '@/hooks/queries/useEmployeeDashboardQueries';
import {
  ABSENCE_CALENDAR_MODIFIERS_CLASS_NAMES,
  buildAbsenceCalendarModifiers,
  CALENDAR_LEGEND,
  formatCurrency,
  formatCumulsMonthLabel,
  formatMonthYear,
  getNextValidatedAbsenceDate,
  pickDisplayPayslip,
} from '@/lib/employeeDashboardUtils';
import { cn } from '@/lib/utils';

function DashboardMetricCardLoader() {
  return (
    <CardContent className="flex min-h-[88px] items-center justify-center">
      <SharkFinLoader variant="compact" label="" />
    </CardContent>
  );
}

function ExpenseStatusLink({
  to,
  count,
  label,
  icon: Icon,
  iconClassName,
  subdued,
}: {
  to: string;
  count: number;
  label: string;
  icon: typeof Hourglass;
  iconClassName: string;
  subdued?: boolean;
}) {
  return (
    <Link
      to={to}
      className={cn(
        'flex flex-1 items-center gap-2 rounded-md p-3 text-center transition-colors hover:bg-muted justify-center',
        subdued && 'opacity-70'
      )}
    >
      <Icon className={cn('h-5 w-5 shrink-0', iconClassName)} />
      <div>
        <p className="text-xl font-bold">{count}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </Link>
  );
}

export default function EmployeeDashboard() {
  const { user } = useAuth();
  const userId = user?.id;
  const [currentMonth, setCurrentMonth] = useState(() => new Date());

  const calendarYear = currentMonth.getFullYear();
  const calendarMonth = currentMonth.getMonth() + 1;

  const payslipsQuery = useEmployeePayslipsQuery(userId);
  const expensesQuery = useEmployeeExpensesQuery(userId);
  const absencesQuery = useEmployeeAbsencesPageQuery(
    userId,
    calendarYear,
    calendarMonth
  );
  const cumulsQuery = useEmployeeCumulsQuery(userId);
  const profileQuery = useEmployeeProfileQuery(userId);

  const initialAbsencesQuery = useEmployeeAbsencesPageQuery(
    userId,
    new Date().getFullYear(),
    new Date().getMonth() + 1
  );

  const partialError =
    payslipsQuery.isError ||
    expensesQuery.isError ||
    initialAbsencesQuery.isError ||
    profileQuery.isError ||
    cumulsQuery.isError;

  const displayPayslip = useMemo(
    () => pickDisplayPayslip(payslipsQuery.data ?? []),
    [payslipsQuery.data]
  );

  const expenses = expensesQuery.data ?? [];
  const pendingExpensesCount = expenses.filter((e) => e.status === 'pending').length;
  const rejectedExpensesCount = expenses.filter(
    (e) => e.status === 'rejected'
  ).length;
  const validatedExpensesCount = expenses.filter(
    (e) => e.status === 'validated'
  ).length;

  const absencePage = absencesQuery.data ?? initialAbsencesQuery.data;
  const leaveBalances =
    initialAbsencesQuery.data?.balances ?? absencePage?.balances ?? [];
  const calendarDays = absencePage?.calendar_days ?? [];
  const absenceHistory: AbsenceRequest[] =
    initialAbsencesQuery.data?.history ?? absencePage?.history ?? [];

  const pendingAbsences = absenceHistory.filter((a) => a.status === 'pending');
  const cumuls = cumulsQuery.data;
  const employeeInfo = profileQuery.data;

  const nextAbsenceDate = useMemo(
    () => getNextValidatedAbsenceDate(absenceHistory),
    [absenceHistory]
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

  const cumulsMonthLabel = formatCumulsMonthLabel(
    cumuls?.periode?.dernier_mois_calcule
  );
  const payslipHref = displayPayslip?.payslip.id
    ? `/employee/payslips/${displayPayslip.payslip.id}`
    : '/payslips';

  const payslipPeriodLabel = displayPayslip
    ? displayPayslip.label === 'm1'
      ? `${formatMonthYear(displayPayslip.payslip.month, displayPayslip.payslip.year)} (M-1)`
      : `Dernier bulletin — ${formatMonthYear(displayPayslip.payslip.month, displayPayslip.payslip.year)}`
    : 'Aucun bulletin disponible';

  const showExpensesEmptyState =
    !expensesQuery.isLoading &&
    pendingExpensesCount === 0 &&
    rejectedExpensesCount === 0;

  if (!userId) {
    return (
      <p className="text-sm text-muted-foreground">
        Connectez-vous pour accéder à votre tableau de bord.
      </p>
    );
  }

  return (
    <EmployeePageShell className="space-y-8">
      <EmployeePageHeader
        title={`Bonjour, ${user?.first_name || 'Utilisateur'} !`}
        description={
          profileQuery.isLoading
            ? 'Votre tableau de bord personnel.'
            : (employeeInfo?.job_title ?? 'Votre tableau de bord personnel.')
        }
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to="/profile">
              <User className="mr-2 h-4 w-4" />
              Mon profil
            </Link>
          </Button>
        }
      />

      {partialError && (
        <Card className="border-destructive bg-destructive/10">
          <CardContent className="flex items-center gap-2 pt-6 text-sm font-medium text-destructive">
            <Info className="h-4 w-4 shrink-0" />
            Certaines informations du tableau de bord n&apos;ont pas pu être
            chargées.
          </CardContent>
        </Card>
      )}

      <section className="space-y-4" aria-labelledby="dashboard-urgent-heading">
        <h2 id="dashboard-urgent-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          À traiter
        </h2>
        <PendingSignaturesWidget mode="employee" />

        {pendingAbsences.length > 0 && (
          <Card className="border-amber-200 bg-amber-50/80 dark:border-amber-900/50 dark:bg-amber-950/20">
            <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-amber-600" />
                <p className="text-sm font-medium">
                  {pendingAbsences.length} demande
                  {pendingAbsences.length > 1 ? 's' : ''} d&apos;absence en
                  attente de validation
                </p>
              </div>
              <Button variant="secondary" size="sm" asChild>
                <Link to="/absences">Voir mes absences</Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {(pendingExpensesCount > 0 || rejectedExpensesCount > 0) && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Notes de frais à suivre</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-2 sm:flex-row sm:justify-around">
                <ExpenseStatusLink
                  to="/expenses?status=pending"
                  count={pendingExpensesCount}
                  label="En attente"
                  icon={Hourglass}
                  iconClassName="text-amber-500"
                />
                <ExpenseStatusLink
                  to="/expenses?status=rejected"
                  count={rejectedExpensesCount}
                  label="Refusée(s)"
                  icon={CircleX}
                  iconClassName="text-destructive"
                />
              </div>
            </CardContent>
          </Card>
        )}
      </section>

      <section className="space-y-6" aria-labelledby="dashboard-suivi-heading">
        <h2 id="dashboard-suivi-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Suivi
        </h2>

        <EmployeeBadgeuseDashboardCard />

        <EmployeeCseDashboardCard />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div className="-mx-1 flex gap-4 overflow-x-auto pb-2 snap-x snap-mandatory lg:mx-0 lg:grid lg:grid-cols-3 lg:gap-4 lg:overflow-visible lg:pb-0">
              <Card
                className={cn(
                  'min-w-[85%] shrink-0 snap-center transition-colors sm:min-w-[45%] lg:min-w-0',
                  displayPayslip &&
                    'cursor-pointer hover:border-primary/50 hover:bg-muted/30'
                )}
              >
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">
                    Dernier net à payer
                  </CardTitle>
                  <Wallet className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                {payslipsQuery.isLoading ? (
                  <DashboardMetricCardLoader />
                ) : displayPayslip ? (
                  <Link to={payslipHref} className="block h-full">
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {formatCurrency(displayPayslip.payslip.net_a_payer)}
                      </div>
                      <p className="text-xs capitalize text-muted-foreground">
                        {payslipPeriodLabel}
                      </p>
                    </CardContent>
                  </Link>
                ) : (
                  <CardContent>
                    <div className="text-2xl font-bold">N/A</div>
                    <p className="text-xs text-muted-foreground">
                      {payslipPeriodLabel}
                    </p>
                  </CardContent>
                )}
              </Card>

              <Card className="min-w-[85%] shrink-0 snap-center sm:min-w-[45%] lg:min-w-0">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">
                    Net imposable annuel
                  </CardTitle>
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                {cumulsQuery.isLoading ? (
                  <DashboardMetricCardLoader />
                ) : (
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {formatCurrency(cumuls?.cumuls?.net_imposable)}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Année{' '}
                      {cumuls?.periode?.annee_en_cours ?? new Date().getFullYear()}
                      {cumulsMonthLabel
                        ? ` · Arrêté au ${cumulsMonthLabel}`
                        : ''}
                    </p>
                  </CardContent>
                )}
              </Card>

              <Card className="min-w-[85%] shrink-0 snap-center border-dashed sm:min-w-[45%] lg:min-w-0">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Salaire de base
                  </CardTitle>
                  <Euro className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                {profileQuery.isLoading ? (
                  <DashboardMetricCardLoader />
                ) : (
                  <CardContent>
                    <div className="text-xl font-semibold text-muted-foreground">
                      {formatCurrency(employeeInfo?.salaire_de_base?.valeur)}
                    </div>
                    <p className="text-xs text-muted-foreground">Mensuel brut</p>
                    <Button
                      variant="link"
                      size="sm"
                      asChild
                      className="mt-1 h-auto p-0 text-xs"
                    >
                      <Link to="/payslips">Voir ma rémunération →</Link>
                    </Button>
                  </CardContent>
                )}
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Accès rapides</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <Button
                    asChild
                    variant="secondary"
                    className="h-20 flex-col gap-1 border-2 border-transparent text-sm transition-all hover:scale-[1.02] hover:border-primary"
                  >
                    <Link to="/absences">
                      <CalendarDays className="mb-1 h-5 w-5" />
                      Demander une absence
                    </Link>
                  </Button>
                  <Button
                    asChild
                    variant="secondary"
                    className="h-20 flex-col gap-1 border-2 border-transparent text-sm transition-all hover:scale-[1.02] hover:border-primary"
                  >
                    <Link to="/expenses?action=new">
                      <Receipt className="mb-1 h-5 w-5" />
                      Déclarer une note
                    </Link>
                  </Button>
                  <Button
                    asChild
                    variant="secondary"
                    className="h-20 flex-col gap-1 border-2 border-transparent text-sm transition-all hover:scale-[1.02] hover:border-primary"
                  >
                    <Link to="/payslips">
                      <FileText className="mb-1 h-5 w-5" />
                      Voir mes bulletins
                    </Link>
                  </Button>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Button asChild variant="outline" size="sm" className="h-auto flex-col gap-1 py-3 text-xs">
                    <Link to="/employee/formation">
                      <GraduationCap className="h-4 w-4" />
                      Ma formation
                    </Link>
                  </Button>
                  <Button asChild variant="outline" size="sm" className="h-auto flex-col gap-1 py-3 text-xs">
                    <Link to="/employee/documents">
                      <FileText className="h-4 w-4" />
                      Mes documents
                    </Link>
                  </Button>
                  <Button asChild variant="outline" size="sm" className="h-auto flex-col gap-1 py-3 text-xs">
                    <Link to="/badgeuse">
                      <ScanLine className="h-4 w-4" />
                      Ma badgeuse
                    </Link>
                  </Button>
                  <Button asChild variant="outline" size="sm" className="h-auto flex-col gap-1 py-3 text-xs">
                    <Link to="/calendar?view=week">
                      <CalendarDays className="h-4 w-4" />
                      Calendrier et planning
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Mes notes de frais</CardTitle>
              </CardHeader>
              <CardContent>
                {expensesQuery.isLoading ? (
                  <div className="flex min-h-[88px] items-center justify-center">
                    <SharkFinLoader variant="compact" label="" />
                  </div>
                ) : showExpensesEmptyState ? (
                  <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-6 text-center">
                    <CheckCircle className="h-8 w-8 text-emerald-600" />
                    <p className="text-sm font-medium">Aucune note en cours</p>
                    <Button variant="link" size="sm" asChild>
                      <Link to="/expenses">Voir l&apos;historique</Link>
                    </Button>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2 sm:flex-row sm:justify-around">
                    <ExpenseStatusLink
                      to="/expenses?status=pending"
                      count={pendingExpensesCount}
                      label="En attente"
                      icon={Hourglass}
                      iconClassName="text-amber-500"
                    />
                    <ExpenseStatusLink
                      to="/expenses?status=rejected"
                      count={rejectedExpensesCount}
                      label="Refusée(s)"
                      icon={CircleX}
                      iconClassName="text-destructive"
                    />
                    <ExpenseStatusLink
                      to="/expenses?status=validated"
                      count={validatedExpensesCount}
                      label="Acceptée(s)"
                      icon={CheckCircle}
                      iconClassName="text-green-600"
                      subdued
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Mes soldes</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {initialAbsencesQuery.isLoading ? (
                  <div className="flex min-h-[72px] items-center justify-center">
                    <SharkFinLoader variant="compact" label="" />
                  </div>
                ) : leaveBalances.length > 0 ? (
                  leaveBalances.map((balance) => (
                    <EmployeeAbsenceBalanceRow key={balance.type} balance={balance} />
                  ))
                ) : !partialError ? (
                  <p className="text-sm text-muted-foreground">
                    Soldes non disponibles.
                  </p>
                ) : null}
                <Button variant="link" size="sm" asChild className="h-auto p-0 text-xs">
                  <Link to="/absences">Voir détails / Faire une demande</Link>
                </Button>
              </CardContent>
            </Card>

            <Card className="relative">
              <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 space-y-0">
                <CardTitle className="text-lg">Calendrier des congés</CardTitle>
                <Button size="sm" asChild>
                  <Link to="/absences">Demander une absence</Link>
                </Button>
              </CardHeader>
              <CardContent className="flex flex-col items-center">
                {initialAbsencesQuery.isLoading ? (
                  <div className="flex min-h-[280px] w-full items-center justify-center">
                    <SharkFinLoader variant="section" label="Chargement du calendrier…" />
                  </div>
                ) : (
                  <>
                {absencesQuery.isFetching && !absencesQuery.isLoading && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-background/50">
                    <span className="sr-only">Chargement du calendrier</span>
                  </div>
                )}
                {nextAbsenceDate && (
                  <p className="mb-3 w-full text-center text-xs text-muted-foreground">
                    Prochaine absence validée :{' '}
                    <Badge variant="outline" className="ml-1 font-normal">
                      {nextAbsenceDate.toLocaleDateString('fr-FR')}
                    </Badge>
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
                />
                <div className="mt-4 w-full space-y-2 border-t pt-4">
                  {Object.entries(CALENDAR_LEGEND).map(([key, { label, color }]) => (
                    <div key={key} className="flex items-center text-sm">
                      <span
                        className={cn('mr-2 h-3 w-3 rounded-full', color)}
                      />
                      <span>{label}</span>
                    </div>
                  ))}
                </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </EmployeePageShell>
  );
}
