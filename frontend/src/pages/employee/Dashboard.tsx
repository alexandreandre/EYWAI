// src/pages/employee/Dashboard.tsx 

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import {
  FileText,
  CalendarDays,
  Receipt,
  Wallet,
  TrendingUp,
  Hourglass,
  CircleX,
  Loader2,
  Info,
  Euro,
  CheckCircle,
  GraduationCap,
  IdCard,
  FolderOpen,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Calendar } from '@/components/ui/calendar'; // Renommé ShadCalendar en Calendar
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import apiClient from '@/api/apiClient';
import type * as absencesApi from '@/api/absences'; // Import types
import { EmployeePriorityFocus } from '@/components/dashboard/EmployeePriorityFocus';

// --- Interfaces (simplifiées pour le dashboard) ---
interface PayslipInfo {
  id: string; month: number; year: number; name: string; url: string; net_a_payer?: number | null;
}
interface EmployeeSalaryInfo {
  salaire_de_base?: { valeur?: number } | null;
  job_title?: string | null;
  hire_date?: string | null;
}
interface ExpenseInfo {
  id: string; status: 'pending' | 'validated' | 'rejected'; date: string; amount: number; type: string;
}
interface AbsenceBalance { type: string; total_allocated: number; taken: number; remaining: number; }
interface AbsenceRequest { id: string; type: string; selected_days: string[]; status: 'pending' | 'validated' | 'rejected'; employee: { balances: AbsenceBalance[] }; }
interface CumulsData {
  periode?: { annee_en_cours?: number; dernier_mois_calcule?: number };
  cumuls?: { brut_total?: number; net_imposable?: number };
}

// --- Fonctions Utilitaires ---
const formatCurrency = (amount: number | undefined | null): string => {
    if (amount == null || isNaN(amount)) return 'N/A';
    return amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
};
const formatMonthYear = (month: number, year: number) => {
  return new Date(year, month - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' });
};
const formatDate = (dateString: string | undefined | null) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'N/A';
      return date.toLocaleDateString('fr-FR');
    } catch (e) { return 'N/A'; }
};

export default function EmployeeDashboard() {
  const { user } = useAuth();
  const { toast } = useToast();

  console.log('DEBUG: [Render] User from useAuth:', user);

  // --- États ---
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestPayslip, setLatestPayslip] = useState<PayslipInfo | null>(null);
  const [pendingExpensesCount, setPendingExpensesCount] = useState(0);
  const [rejectedExpensesCount, setRejectedExpensesCount] = useState(0);
  const [validatedExpensesCount, setValidatedExpensesCount] = useState(0);
  const [leaveBalances, setLeaveBalances] = useState<AbsenceBalance[]>([]);
  const [upcomingAbsences, setUpcomingAbsences] = useState<Date[]>([]); // Dates validées
  const [cumuls, setCumuls] = useState<CumulsData | null>(null);
  const [employeeInfo, setEmployeeInfo] = useState<EmployeeSalaryInfo | null>(null);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [calendarDays, setCalendarDays] = useState<absencesApi.CalendarDay[]>([]);

  // --- Logique de fetch séparée pour le calendrier ---
  const fetchCalendarData = async (date: Date) => {
    try {
      const year = date.getFullYear();
      const month = date.getMonth() + 1;
      // On ne récupère que les `calendar_days` pour le mois donné
      const response = await apiClient.get<absencesApi.AbsencePageData>(`/api/absences/employees/me/page-data?year=${year}&month=${month}`);
      if (response.data?.calendar_days) {
        setCalendarDays(response.data.calendar_days);
        console.log(`DEBUG: [Calendar] Fetched calendar data for ${month}/${year}`);
      }
    } catch (error) {
      console.error("DEBUG: [Calendar] Failed to fetch calendar data.", error);
      // On ne met pas d'erreur globale pour ne pas perturber le reste du dashboard
      setCalendarDays([]); // On vide pour que la logique de fallback s'applique
    }
  };

  useEffect(() => {
    if (user?.id) {
      const fetchDashboardData = async () => {
        setIsLoading(true);
        setError(null);
        try {
          // Utiliser les URLs correctes et AbsencePageData
          const results = await Promise.allSettled([
            apiClient.get<PayslipInfo[]>(`/api/me/payslips`),
            apiClient.get<ExpenseInfo[]>(`/api/expenses/me`), // ✅ URL Corrigée
            // ✅ Utiliser la route "tout-en-un" pour les absences
            apiClient.get<absencesApi.AbsencePageData>(`/api/absences/employees/me/page-data?year=${new Date().getFullYear()}&month=${new Date().getMonth() + 1}`), // Ajout params year/month même si non utilisés par soldes/historique
            apiClient.get<CumulsData>('/api/me/current-cumuls'),
            apiClient.get<EmployeeSalaryInfo>(`/api/employees/${user.id}`),
          ]);

          let fetchError = false;

          // 1. Bulletins -> Bulletin du mois précédent (M-1)
          console.log("DEBUG: Processing Payslips...");
          if (results[0].status === 'fulfilled') {
             const payslipsData = results[0].value.data || [];
             if (payslipsData.length > 0) {
                 // Calculer M-1 (mois précédent)
                 const today = new Date();
                 const previousMonth = today.getMonth() === 0 ? 12 : today.getMonth(); // getMonth() returns 0-11
                 const previousYear = today.getMonth() === 0 ? today.getFullYear() - 1 : today.getFullYear();

                 console.log(`DEBUG: [Payslips] Looking for M-1: ${previousMonth}/${previousYear}`);

                 // Chercher le bulletin du mois précédent
                 const m1Payslip = payslipsData.find(p =>
                   p.month === previousMonth && p.year === previousYear
                 );

                 if (m1Payslip) {
                   console.log(`DEBUG: [Payslips] Found M-1 payslip: ${m1Payslip.month}/${m1Payslip.year}`);
                   setLatestPayslip(m1Payslip);
                 } else {
                   console.log("DEBUG: [Payslips] No M-1 payslip found. Setting to null.");
                   setLatestPayslip(null);
                 }
             } else { setLatestPayslip(null); console.log("DEBUG: [Payslips] Success. No payslips found."); }
          } else { console.error("DEBUG: [Payslips] API call rejected.", results[0].reason); fetchError = true; }

          // 2. Notes de frais -> Compter en attente / rejetées
          console.log("DEBUG: Processing Expenses...");
          if (results[1].status === 'fulfilled') {
            const expenses = results[1].value.data || [];
            setPendingExpensesCount(expenses.filter(e => e.status === 'pending').length);
            setRejectedExpensesCount(expenses.filter(e => e.status === 'rejected').length);
            setValidatedExpensesCount(expenses.filter(e => e.status === 'validated').length);
          } else { console.error("DEBUG: [Expenses] API call rejected.", results[1].reason); fetchError = true; }

          console.log("DEBUG: Processing Absences...");
          if (results[2].status === 'fulfilled') {
            const absenceData = results[2].value.data;
            if (absenceData?.balances) {
                setLeaveBalances(absenceData.balances);
            } else { setLeaveBalances([]); }

            // ✅ Store calendarDays for the displayed month
            if (absenceData?.calendar_days) {
                setCalendarDays(absenceData.calendar_days);
            } else { setCalendarDays([]); }

            // Extract validated dates from HISTORY (all validated requests) for modifiers
            const validatedDates = (absenceData?.history || [])
              .filter(a => a.status === 'validated')
              .flatMap(a => a.selected_days || [])
              .map(d => new Date(d));
            // Note: We don't filter by future here, the modifier logic handles display month
            setUpcomingAbsences(validatedDates); // Renaming state might be good, but keep for now

          } else {
            console.error("DEBUG: [Absences] API call rejected.", results[2].reason);
            setLeaveBalances([]);
            setCalendarDays([]);
            setUpcomingAbsences([]);
          }

          // 4. Cumuls
          console.log("DEBUG: Processing Cumuls...");
          const cumulsResultIndex = 3;
          if (results[cumulsResultIndex].status === 'fulfilled') {
            const cumulsData = results[cumulsResultIndex].value.data;
            if (cumulsData && (cumulsData.periode || cumulsData.cumuls)) {
                setCumuls(cumulsData);
            } else { setCumuls(null); console.log("DEBUG: [Cumuls] Success. No cumuls found or data empty."); }
          } else { console.error("DEBUG: [Cumuls] API call rejected.", results[cumulsResultIndex].reason); setCumuls(null); /* fetchError = true; */ } // Erreur non bloquante ?

          // 5. Infos Employé
          console.log("DEBUG: Processing Employee Info...");
           const employeeInfoResultIndex = 4;
           if (results[employeeInfoResultIndex].status === 'fulfilled') {
            setEmployeeInfo(results[employeeInfoResultIndex].value.data);
          } else { console.error("DEBUG: [Employee Info] API call rejected.", results[employeeInfoResultIndex].reason); fetchError = true; }


          if (fetchError) {
             const errorMsg = "Certaines informations du tableau de bord n'ont pas pu être chargées.";
             console.warn("DEBUG: [fetchDashboardData] fetchError was set to true.");
             setError(errorMsg);
          }

        } catch (err) { /* ... (gestion erreur globale inchangée) ... */ }
        finally { setIsLoading(false); }
      };
      fetchDashboardData();
    } else { /* ... (gestion user?.id manquant inchangée) ... */ }
  }, [user?.id, toast]); // Dépendances OK

  // --- ✅ NOUVEAU : useEffect pour recharger les données du calendrier au changement de mois ---
  useEffect(() => {
    // On ne recharge pas au premier rendu car les données sont déjà chargées par fetchDashboardData
    // On vérifie aussi que l'utilisateur est chargé pour éviter un appel inutile
    if (!isLoading && user?.id) {
      fetchCalendarData(currentMonth);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentMonth, isLoading, user?.id]); // On ne veut pas fetchCalendarData dans les deps

  const today = new Date();
  today.setHours(0, 0, 0, 0); // Normalize today for comparison

  const calendarLegend = {
    aujourdhui: { label: "Aujourd'hui", color: 'border-2 border-primary' },
    conge: { label: 'Congé / RTT', color: 'bg-blue-500', textColor: 'text-white' },
    arret_maladie: { label: 'Arrêt maladie', color: 'bg-orange-400', textColor: 'text-white' },
    ferie: { label: 'Jour férié', color: 'bg-green-500', textColor: 'text-white' },
    weekend: { label: 'Weekend', color: 'bg-gray-200 dark:bg-gray-700', textColor: 'text-muted-foreground' },
  };
  type CalendarDayType = keyof typeof calendarLegend;

  const getCalendarModifiers = () => {
      const year = currentMonth.getFullYear();
      const month = currentMonth.getMonth();

      // Si le calendrier de la BDD est vide, on génère un calendrier par défaut avec seulement les week-ends
      if (calendarDays.length === 0) {
          const weekends: Date[] = [];
          const daysInMonth = new Date(year, month + 1, 0).getDate();
          for (let day = 1; day <= daysInMonth; day++) {
              const date = new Date(year, month, day);
              if (date.getDay() === 0 || date.getDay() === 6) {
                  weekends.push(date);
              }
          }
          return { weekend: weekends, aujourdhui: [today] };
      }

      // Sinon, on utilise les données de la BDD comme avant
      const modifiersFromApi = calendarDays.reduce((acc, day) => {
        const type = day.type as CalendarDayType;
        if (!acc[type]) acc[type] = [];
        acc[type].push(new Date(year, month, day.jour));
        return acc;
      }, {} as Record<CalendarDayType, Date[]>);

      return modifiersFromApi;
  };

  const modifiers = getCalendarModifiers();
  modifiers.aujourdhui = [today];

  const modifiersClassNames = {
    aujourdhui: 'border-2 border-primary rounded-md !bg-transparent text-primary',
    conge: 'bg-blue-500 text-white rounded-md',
    arret_maladie: 'bg-orange-400 text-white rounded-md',
    ferie: 'bg-green-500 text-white rounded-md',
    weekend: 'text-muted-foreground opacity-80',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Bonjour, {user?.first_name || "Utilisateur"} !</h1>
          <p className="text-muted-foreground">Votre tableau de bord personnel.</p>
        </div>
      </div>

      <EmployeePriorityFocus />

      <Card className="border-primary/20 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Accès rapides</CardTitle>
          <CardDescription className="text-xs sm:text-sm">
            Raccourcis vers les actions les plus courantes
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Button
            asChild
            variant="secondary"
            className="h-auto min-h-[3.25rem] justify-start gap-3 border border-transparent px-4 py-3 text-left text-sm shadow-none transition-all hover:border-primary/30 hover:bg-secondary"
          >
            <Link to="/absences" className="flex w-full items-center gap-3">
              <CalendarDays className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              <span className="font-medium leading-snug">Demander une absence</span>
            </Link>
          </Button>
          <Button
            asChild
            variant="secondary"
            className="h-auto min-h-[3.25rem] justify-start gap-3 border border-transparent px-4 py-3 text-left text-sm shadow-none transition-all hover:border-primary/30 hover:bg-secondary"
          >
            <Link to="/expenses" className="flex w-full items-center gap-3">
              <Receipt className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              <span className="font-medium leading-snug">Déclarer une note</span>
            </Link>
          </Button>
          <Button
            asChild
            variant="secondary"
            className="h-auto min-h-[3.25rem] justify-start gap-3 border border-transparent px-4 py-3 text-left text-sm shadow-none transition-all hover:border-primary/30 hover:bg-secondary"
          >
            <Link to="/payslips" className="flex w-full items-center gap-3">
              <FileText className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              <span className="font-medium leading-snug">Voir mes bulletins</span>
            </Link>
          </Button>
          <Button
            asChild
            variant="secondary"
            className="h-auto min-h-[3.25rem] justify-start gap-3 border border-transparent px-4 py-3 text-left text-sm shadow-none transition-all hover:border-primary/30 hover:bg-secondary"
          >
            <Link to="/employee/formation" className="flex w-full items-center gap-3">
              <GraduationCap className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              <span className="font-medium leading-snug">Ma formation</span>
            </Link>
          </Button>
          <Button
            asChild
            variant="secondary"
            className="h-auto min-h-[3.25rem] justify-start gap-3 border border-transparent px-4 py-3 text-left text-sm shadow-none transition-all hover:border-primary/30 hover:bg-secondary"
          >
            <Link to="/badgeuse" className="flex w-full items-center gap-3">
              <IdCard className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              <span className="font-medium leading-snug">Ma badgeuse</span>
            </Link>
          </Button>
          <Button
            asChild
            variant="secondary"
            className="h-auto min-h-[3.25rem] justify-start gap-3 border border-transparent px-4 py-3 text-left text-sm shadow-none transition-all hover:border-primary/30 hover:bg-secondary"
          >
            <Link to="/employee/documents" className="flex w-full items-center gap-3">
              <FolderOpen className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              <span className="font-medium leading-snug">Mes documents</span>
            </Link>
          </Button>
        </CardContent>
      </Card>

      {error && !isLoading && (
        <Card className="border-destructive bg-destructive/10">
          <CardContent className="flex items-center gap-2 pt-6 text-sm font-medium text-destructive">
            <Info className="h-4 w-4 shrink-0" aria-hidden />
            {error}
          </CardContent>
        </Card>
      )}

      <section className="space-y-3" aria-labelledby="gestion-temps-heading">
        <h2 id="gestion-temps-heading" className="text-base font-semibold tracking-tight text-foreground">
          Gestion du temps
        </h2>
        <div className="grid gap-6 lg:grid-cols-2 lg:items-stretch">
          <Card className="flex min-h-0 flex-col">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Mes soldes</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col space-y-3">
              {isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Chargement…
                </div>
              ) : leaveBalances && leaveBalances.length > 0 ? (
                <ul className="space-y-3">
                  {leaveBalances.map((balance) => (
                    <li
                      key={balance.type}
                      className="flex items-baseline justify-between gap-3 border-b border-border/60 pb-3 last:border-0 last:pb-0"
                    >
                      <span className="text-sm text-muted-foreground">{balance.type || "Type inconnu"}</span>
                      <strong className="text-lg font-semibold tabular-nums">
                        {typeof balance.remaining === "number"
                          ? `${balance.remaining.toFixed(1)} j`
                          : balance.remaining}
                      </strong>
                    </li>
                  ))}
                </ul>
              ) : !error ? (
                <p className="text-sm text-muted-foreground">Soldes non disponibles.</p>
              ) : null}
              {!isLoading && (
                <Button variant="link" size="sm" asChild className="mt-auto h-auto justify-start p-0 text-xs">
                  <Link to="/absences">Voir détails / Faire une demande</Link>
                </Button>
              )}
            </CardContent>
          </Card>

          <Card className="relative flex min-h-0 flex-col">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Mon calendrier</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col items-center">
              {isLoading && (
                <div
                  className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-background/50"
                  aria-busy
                >
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden />
                </div>
              )}
              <Calendar
                mode="single"
                month={currentMonth}
                onMonthChange={setCurrentMonth}
                className="rounded-md border p-0"
                weekStartsOn={1}
                modifiers={modifiers}
                modifiersClassNames={modifiersClassNames}
              />
              <div className="mt-4 w-full space-y-2 border-t pt-4">
                {Object.entries(calendarLegend).map(([key, { label, color }]) => (
                  <div key={key} className="flex items-center text-sm">
                    <span className={`mr-2 h-3 w-3 shrink-0 rounded-full ${color}`} aria-hidden />
                    <span>{label}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="space-y-3" aria-labelledby="suivi-admin-heading">
        <h2 id="suivi-admin-heading" className="text-base font-semibold tracking-tight text-foreground">
          Suivi administratif
        </h2>
        <div className="grid gap-4 lg:grid-cols-12 lg:items-stretch">
          <Card className="lg:col-span-7 xl:col-span-8">
            <CardHeader className="space-y-0 pb-3 pt-4">
              <CardTitle className="text-sm font-semibold">Rémunération</CardTitle>
              <CardDescription className="text-xs">Indicateurs de paie (M-1 et cumuls)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 pb-4 pt-0">
              <div className="grid gap-2 sm:grid-cols-3">
                <div className="flex items-center gap-3 rounded-lg border border-border/70 bg-muted/25 px-3 py-2.5">
                  <Wallet className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] font-medium leading-tight text-muted-foreground">Dernier net à payer</p>
                    <p className="truncate text-[11px] text-muted-foreground/90 capitalize">
                      {latestPayslip
                        ? `${formatMonthYear(latestPayslip.month, latestPayslip.year)} (M-1)`
                        : "Mois précédent (M-1)"}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden />
                    ) : (
                      <p className="text-sm font-semibold tabular-nums">
                        {latestPayslip?.net_a_payer != null ? formatCurrency(latestPayslip.net_a_payer) : "N/A"}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border border-border/70 bg-muted/25 px-3 py-2.5">
                  <TrendingUp className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] font-medium leading-tight text-muted-foreground">Net imposable annuel</p>
                    <p className="text-[11px] text-muted-foreground/90">
                      Année {cumuls?.periode?.annee_en_cours || new Date().getFullYear()}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden />
                    ) : (
                      <p className="text-sm font-semibold tabular-nums">
                        {formatCurrency(cumuls?.cumuls?.net_imposable)}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border border-border/70 bg-muted/25 px-3 py-2.5 sm:col-span-1">
                  <Euro className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] font-medium leading-tight text-muted-foreground">Salaire de base</p>
                    <p className="text-[11px] text-muted-foreground/90">Mensuel brut</p>
                  </div>
                  <div className="shrink-0 text-right">
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden />
                    ) : (
                      <p className="text-sm font-semibold tabular-nums">
                        {formatCurrency(employeeInfo?.salaire_de_base?.valeur)}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="flex flex-col lg:col-span-5 xl:col-span-4">
            <CardHeader className="space-y-0 pb-3 pt-4">
              <CardTitle className="text-sm font-semibold">Notes de frais</CardTitle>
              <CardDescription className="text-xs">Statut de vos demandes</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col pb-4 pt-0">
              {isLoading ? (
                <div className="flex flex-1 items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Chargement…
                </div>
              ) : (
                <div className="grid flex-1 grid-cols-3 gap-2 sm:gap-3">
                  <Link
                    to="/expenses"
                    className="flex flex-col items-center justify-center gap-1 rounded-lg border border-border/60 bg-background px-2 py-3 text-center transition-colors hover:bg-muted/80"
                  >
                    <Hourglass className="h-4 w-4 text-amber-500" aria-hidden />
                    <p className="text-lg font-semibold tabular-nums leading-none">{pendingExpensesCount}</p>
                    <p className="text-[10px] font-medium text-muted-foreground sm:text-xs">En attente</p>
                  </Link>
                  <Link
                    to="/expenses"
                    className="flex flex-col items-center justify-center gap-1 rounded-lg border border-border/60 bg-background px-2 py-3 text-center transition-colors hover:bg-muted/80"
                  >
                    <CircleX className="h-4 w-4 text-destructive" aria-hidden />
                    <p className="text-lg font-semibold tabular-nums leading-none">{rejectedExpensesCount}</p>
                    <p className="text-[10px] font-medium text-muted-foreground sm:text-xs">Refusée(s)</p>
                  </Link>
                  <Link
                    to="/expenses"
                    className="flex flex-col items-center justify-center gap-1 rounded-lg border border-border/60 bg-background px-2 py-3 text-center transition-colors hover:bg-muted/80"
                  >
                    <CheckCircle className="h-4 w-4 text-green-600" aria-hidden />
                    <p className="text-lg font-semibold tabular-nums leading-none">{validatedExpensesCount}</p>
                    <p className="text-[10px] font-medium text-muted-foreground sm:text-xs">Acceptée(s)</p>
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}