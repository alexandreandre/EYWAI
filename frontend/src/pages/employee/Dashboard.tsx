// src/pages/employee/Dashboard.tsx 

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { FileText, CalendarDays, Receipt, ArrowRight, Wallet, TrendingUp, Hourglass, CircleX, Loader2, Info, Euro, CheckCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Calendar } from '@/components/ui/calendar'; // Renommé ShadCalendar en Calendar
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import apiClient from '@/api/apiClient';
import { DayPickerSingleProps } from 'react-day-picker'; // Pour typer les modifiers
import { fr } from 'date-fns/locale';
import type * as absencesApi from '@/api/absences'; // Import types

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

  // --- LE JSX RESTE LE MÊME que dans ma réponse précédente, ---
  // --- mais les sections Soldes et Calendrier vont maintenant s'afficher ---
  // --- si les données sont chargées correctement. ---
  return (
    <div className="space-y-6">
      {/* ... (En-tête, Affichage Erreur Globale) ... */}
       <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Bonjour, {user?.first_name || 'Utilisateur'} !</h1>
          <p className="text-muted-foreground">Votre tableau de bord personnel.</p>
        </div>
      </div>
      {error && !isLoading && (
          <Card className="border-destructive bg-destructive/10"><CardContent className="pt-6 text-destructive text-sm font-medium flex items-center gap-2"><Info className="h-4 w-4"/> {error}</CardContent></Card>
      )}


      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          {/* --- Cartes KPI --- */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
             <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2"><CardTitle className="text-sm font-medium">Dernier Net à Payer</CardTitle><Wallet className="h-4 w-4 text-muted-foreground" /></CardHeader>
              <CardContent>
                {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : (
                  <>
                    <div className="text-2xl font-bold">{latestPayslip?.net_a_payer ? formatCurrency(latestPayslip.net_a_payer) : 'N/A'}</div>
                    <p className="text-xs text-muted-foreground capitalize">
                      {latestPayslip ? `${formatMonthYear(latestPayslip.month, latestPayslip.year)} (M-1)` : 'Mois précédent (M-1)'}
                    </p>
                  </>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2"><CardTitle className="text-sm font-medium">Net Imposable Annuel</CardTitle><TrendingUp className="h-4 w-4 text-muted-foreground" /></CardHeader>
              <CardContent>
                 {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : (
                   <>
                    <div className="text-2xl font-bold">{formatCurrency(cumuls?.cumuls?.net_imposable)}</div>
                    <p className="text-xs text-muted-foreground">Année {cumuls?.periode?.annee_en_cours || new Date().getFullYear()}</p>
                   </>
                 )}
              </CardContent>
            </Card>
             <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2"><CardTitle className="text-sm font-medium">Salaire de Base</CardTitle><Euro className="h-4 w-4 text-muted-foreground" /></CardHeader>
              <CardContent>
                 {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : (
                   <>
                    <div className="text-2xl font-bold">{formatCurrency(employeeInfo?.salaire_de_base?.valeur)}</div>
                    <p className="text-xs text-muted-foreground">Mensuel brut</p>
                   </>
                 )}
              </CardContent>
            </Card>
          </div>

          {/* --- Accès Rapides --- */}
          <Card>
              <CardHeader><CardTitle className="text-lg">Accès Rapides</CardTitle></CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-3">
                  <Button asChild variant="secondary" className="h-20 text-sm flex-col gap-1 border-2 border-transparent transition-all duration-200 hover:border-primary hover:scale-[1.02]">
                      <Link to="/absences"><CalendarDays className="h-5 w-5 mb-1"/> Demander une absence</Link>
                  </Button>
                  <Button asChild variant="secondary" className="h-20 text-sm flex-col gap-1 border-2 border-transparent transition-all duration-200 hover:border-primary hover:scale-[1.02]">
                      <Link to="/expenses"><Receipt className="h-5 w-5 mb-1"/> Déclarer une note</Link>
                  </Button>
                  <Button asChild variant="secondary" className="h-20 text-sm flex-col gap-1 border-2 border-transparent transition-all duration-200 hover:border-primary hover:scale-[1.02]">
                      <Link to="/payslips"><FileText className="h-5 w-5 mb-1"/> Voir mes bulletins</Link>
                  </Button>
              </CardContent>
          </Card>

          {/* --- Statut Notes de Frais --- */}
          <Card>
            <CardHeader><CardTitle className="text-lg">Mes Notes de Frais</CardTitle></CardHeader>
            <CardContent>
               {isLoading ? ( <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Chargement...</div> ) : (
                <div className="flex flex-col sm:flex-row gap-4 justify-around">
                    {/* TODO: Ajuster le lien si la page Expenses gère le filtrage par status */}
                    <Link to="/expenses" className="flex items-center gap-2 p-3 rounded-md hover:bg-muted justify-center text-center">
                        <Hourglass className="h-5 w-5 text-amber-500"/>
                        <div><p className="text-xl font-bold">{pendingExpensesCount}</p><p className="text-xs text-muted-foreground">En attente</p></div>
                    </Link>
                    <Link to="/expenses" className="flex items-center gap-2 p-3 rounded-md hover:bg-muted justify-center text-center">
                        <CircleX className="h-5 w-5 text-destructive"/>
                        <div><p className="text-xl font-bold">{rejectedExpensesCount}</p><p className="text-xs text-muted-foreground">Refusée(s)</p></div>
                    </Link>
                    <Link to="/expenses" className="flex items-center gap-2 p-3 rounded-md hover:bg-muted justify-center text-center">
                        <CheckCircle className="h-5 w-5 text-green-600"/>
                        <div><p className="text-xl font-bold">{validatedExpensesCount}</p><p className="text-xs text-muted-foreground">Acceptée(s)</p></div>
                    </Link>
                </div>
               )}
            </CardContent>
          </Card>
        </div>

        {/* --- Colonne Latérale (1/3) --- */}
        <div className="space-y-6">
          {/* --- Soldes Congés (Réactivé) --- */}
          <Card>
            <CardHeader><CardTitle className="text-lg">Mes Soldes</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {isLoading ? ( <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Chargement...</div>
              ) : leaveBalances && leaveBalances.length > 0 ? ( // Vérifie si leaveBalances existe et n'est pas vide
                leaveBalances.map(balance => (
                  <div key={balance.type} className="flex justify-between items-baseline">
                    <span className="text-muted-foreground">{balance.type || 'Type inconnu'}</span>
                    <strong className="text-2xl font-bold">
                        {/* Gère 'N/A' pour Congé sans solde */}
                        {typeof balance.remaining === 'number' ? `${balance.remaining.toFixed(1)} j` : balance.remaining}
                    </strong>
                  </div>
                ))
              ) : !error ? ( // N'affiche "non dispo" que s'il n'y a pas d'erreur globale
                <p className="text-sm text-muted-foreground">Soldes non disponibles.</p>
              ) : null }
              {!isLoading && ( // N'affiche le bouton qu'après le chargement
                <Button variant="link" size="sm" asChild className="p-0 h-auto text-xs mt-2">
                      <Link to="/absences">Voir détails / Faire une demande</Link>
                </Button>
              )}
            </CardContent>
          </Card>

          
          <Card className="relative">
            <CardHeader><CardTitle className="text-lg">Mon Calendrier</CardTitle></CardHeader>
            <CardContent className="flex flex-col items-center">
              {isLoading && <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10 rounded-lg"><Loader2 className="h-6 w-6 animate-spin" /></div>}

              <Calendar
                mode="single"
                month={currentMonth}
                onMonthChange={setCurrentMonth}
                className="rounded-md border p-0"
                weekStartsOn={1}
                modifiers={modifiers}
                modifiersClassNames={modifiersClassNames}
              />
              {/* Légende */}
              <div className="w-full mt-4 space-y-2 border-t pt-4">
                {Object.entries(calendarLegend).map(([key, { label, color }]) => (
                    <div key={key} className="flex items-center text-sm">
                        <span className={`w-3 h-3 rounded-full mr-2 ${color}`}></span>
                        <span>{label}</span>
                    </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}