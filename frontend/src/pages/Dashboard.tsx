import { useEffect, useState } from "react";
import apiClient from '@/api/apiClient';
import { useAuth } from "@/contexts/AuthContext";
import { Link, useNavigate } from "react-router-dom";
import { CopilotModalAgent } from "@/components/CopilotModalAgent";

// --- Composants Shadcn/UI ---
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Checkbox } from "@/components/ui/checkbox";
import { Kbd } from "@/components/ui/kbd";
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartConfig } from "@/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Legend, Tooltip as RechartsTooltip } from "recharts";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";

// --- Icônes Lucide ---
import {
  Loader2,
  AlertTriangle,
  Inbox,
  Sparkles,
  ChevronRight,
  CalendarCheck,
  CreditCard,
  FileWarning,
  UserPlus,
  Briefcase,
  PartyPopper,
  Plane,
  HeartPulse,
  Landmark,
  Stethoscope,
  FlaskConical,
  FileDown,
  TrendingUp,
  Clock,
  Users,
  SlidersHorizontal,
} from "lucide-react";

// --- Formulaires (que tu as fournis) ---
import { NewEmployeeForm } from "@/components/forms/NewEmployeeForm";
// --- Alertes RIB ---
import * as ribAlertsApi from "@/api/ribAlerts";
import { CSEDashboardBlock } from "@/components/CSEDashboardBlock";
import { getMedicalSettings, getKPIs, type KPIs } from "@/api/medicalFollowUp";
import { getRecruitmentSettings, getJobs, getCandidates } from "@/api/recruitment";
import { useQuery } from "@tanstack/react-query";

// --- 1. Définition des Types de Données ---

interface KpiData {
  coutTotal: number;
  netVerse: number;
  effectifActif: number;
  tauxAbsenteisme: number;
  currentMonth: string;
  cdiCount: number;
  cddCount: number;
  contractDistribution?: Record<string, number>;
  hommesCount?: number | null;
  femmesCount?: number | null;
  handicapesCount?: number | null;
}

interface ChartDataPoint {
  name: string;
  Net_Verse: number;
  Charges: number;
}

interface ActionItems {
  pendingAbsences: number;
  pendingExpenses: number;
}

interface AlertItems {
  obsoleteRates: number;
  expiringContracts: number;
  endOfTrialPeriods: number;
}

interface TeamPulseEmployee {
  id: string;
  first_name: string;
  last_name: string;
  // avatar_url?: string; <-- Suppression
  status: string; 
}

interface TeamPulseEvent {
  id: string;
  type: 'birthday' | 'work_anniversary';
  employee_name: string;
  date: string; // ISO date
  detail: string; 
}

type SimpleEmployee = {
  id: string;
  first_name: string;
  last_name: string;
};

interface DashboardData {
  kpis: KpiData;
  chartData: ChartDataPoint[];
  actions: ActionItems;
  alerts: AlertItems;
  teamPulse: {
    absentToday: TeamPulseEmployee[];
    upcomingEvents: TeamPulseEvent[];
  };
  employees: SimpleEmployee[];
  payrollStatus: {
    currentMonth: string;
    step: number;
    totalSteps: number;
  };
}


// --- 2. Composant Principal: Dashboard ---

interface ResidencePermitStats {
  total_expire: number;
  total_a_renouveler: number;
  total_a_renseigner: number;
  total_valide: number;
}

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [residencePermitStats, setResidencePermitStats] = useState<ResidencePermitStats | null>(null);
  const [residencePermitLoading, setResidencePermitLoading] = useState(true);
  const [ribAlerts, setRibAlerts] = useState<ribAlertsApi.RibAlert[]>([]);
  const [ribAlertsLoading, setRibAlertsLoading] = useState(true);
  const [medicalModuleEnabled, setMedicalModuleEnabled] = useState(false);
  const [medicalKpis, setMedicalKpis] = useState<KPIs | null>(null);
  const [medicalKpisLoading, setMedicalKpisLoading] = useState(true);

  const [isGeneratePayrollModalOpen, setIsGeneratePayrollModalOpen] = useState(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.get<DashboardData>('/api/dashboard/all');
        setData(response.data);
      } catch (e: any) {
        const errorMsg = e.response?.data?.detail || e.message || "Une erreur est survenue.";
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  useEffect(() => {
    const fetchResidencePermitStats = async () => {
      try {
        setResidencePermitLoading(true);
        const response = await apiClient.get<ResidencePermitStats>('/api/dashboard/residence-permit-stats');
        setResidencePermitStats(response.data);
      } catch (e: any) {
        // En cas d'erreur, on garde les stats à null (la carte affichera 0)
        console.error("Erreur lors de la récupération des stats de titres de séjour:", e);
        setResidencePermitStats({
          total_expire: 0,
          total_a_renouveler: 0,
          total_a_renseigner: 0,
          total_valide: 0
        });
      } finally {
        setResidencePermitLoading(false);
      }
    };
    fetchResidencePermitStats();
  }, []);

  useEffect(() => {
    const fetchMedical = async () => {
      try {
        setMedicalKpisLoading(true);
        const settings = await getMedicalSettings();
        setMedicalModuleEnabled(settings.enabled);
        if (settings.enabled) {
          const kpis = await getKPIs();
          setMedicalKpis(kpis);
        } else {
          setMedicalKpis(null);
        }
      } catch {
        setMedicalModuleEnabled(false);
        setMedicalKpis(null);
      } finally {
        setMedicalKpisLoading(false);
      }
    };
    fetchMedical();
  }, []);

  useEffect(() => {
    const fetchRibAlerts = async () => {
      try {
        setRibAlertsLoading(true);
        const response = await ribAlertsApi.getRibAlerts({
          is_read: false,
          is_resolved: false,
          limit: 5,
        });
        setRibAlerts(response.data.alerts || []);
      } catch (e: any) {
        console.error("Erreur lors de la récupération des alertes RIB:", e);
        setRibAlerts([]);
      } finally {
        setRibAlertsLoading(false);
      }
    };
    fetchRibAlerts();
  }, []);

  // Gère le raccourci clavier global (Cmd+K) pour le Copilote
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setIsCopilotOpen((open) => !open) // Inverse l'état (ouvre ou ferme)
      }
    }
    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, []) // Le tableau de dépendances est vide, il est global

  // --- Rendu des États (Chargement, Erreur, Vide) ---
  if (loading) {
    return (
      <div className="flex justify-center items-center h-[calc(100vh-200px)]">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-500/50 bg-red-500/5">
        <CardHeader>
          <CardTitle className="flex items-center text-red-600"><AlertTriangle className="mr-2 h-5 w-5" />Échec du chargement</CardTitle>
        </CardHeader>
        <CardContent className="text-red-500">
          <p>L'API a retourné une erreur :</p>
          <p className="font-mono bg-red-500/10 p-2 rounded-md mt-2 text-sm">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-col justify-center items-center h-64 text-muted-foreground">
        <Inbox className="h-10 w-10" />
        <span className="mt-4 text-lg font-medium">Aucune donnée de dashboard</span>
        <span className="text-sm">Impossible de récupérer les informations de pilotage.</span>
      </div>
    );
  }

  // --- Rendu Principal du Dashboard ---

  return (
    <div className="space-y-6 animate-fade-in">
      <DashboardHeader
        firstName={user?.first_name || "Utilisateur"}
        onCopilotClick={() => setIsCopilotOpen(true)}
      />

      {/* Raccourcis pilotage — 3 cartes compactes (CSE déplacée plus bas) */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <ShortcutSimulationCard />
        <ShortcutExportsCard />
        {medicalModuleEnabled ? (
          <MedicalVisitShortcutCard kpis={medicalKpis} loading={medicalKpisLoading} />
        ) : (
          <MedicalVisitShortcutCard kpis={null} loading={false} />
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Colonne gauche: Actions & alertes */}
        <div className="lg:col-span-1 space-y-6">
          <PayrollCard
            status={data.payrollStatus}
            onGenerateClick={() => setIsGeneratePayrollModalOpen(true)}
          />
          <NotificationsCard actions={data.actions} alerts={data.alerts} />
          <ResidencePermitCard stats={residencePermitStats} loading={residencePermitLoading} />
          {medicalModuleEnabled && (
            <MedicalFollowUpCard kpis={medicalKpis} loading={medicalKpisLoading} />
          )}
          <RibAlertsCard alerts={ribAlerts} loading={ribAlertsLoading} onRefresh={() => {
            ribAlertsApi.getRibAlerts({ is_read: false, is_resolved: false, limit: 5 })
              .then((r) => setRibAlerts(r.data.alerts || []));
          }} />
          <CSEDashboardBlock />
          <ShortcutsCard />
          <DashboardPersonnalisationCard />
        </div>

        {/* Colonne droite: KPIs & pilotage */}
        <div className="lg:col-span-2 space-y-6">
          <CoutsCard kpis={data.kpis} chartData={data.chartData} />
          <EffectifCard kpis={data.kpis} absentsToday={data.teamPulse?.absentToday || []} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <GenderSplitCard kpis={data.kpis} />
            <ContractSplitCard kpis={data.kpis} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <HeuresSupKpiCard />
            <RecruitmentKpisCard />
          </div>
          <PrevisionMasseSalarialeCard kpis={data.kpis} />
        </div>
      </div>

      {/* --- Modaux --- */}
      <CopilotModalAgent
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
      />
      <GeneratePayrollModal
        isOpen={isGeneratePayrollModalOpen}
        onClose={() => setIsGeneratePayrollModalOpen(false)}
        employees={data.employees}
      />

    </div>
  );
}


// --- 3. Sous-Composants du Dashboard ---

// --- Section 1: Header & Copilote ---
function DashboardHeader({ firstName, onCopilotClick }: { firstName: string, onCopilotClick: () => void }) {
  return (
    <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Bonjour {firstName},</h1>
        <p className="text-muted-foreground mt-1">Voici votre cockpit de pilotage RH.</p>
      </div>
      <Button
        className="bg-indigo-600 text-white hover:bg-indigo-700 transition-all shadow-md hover:shadow-lg rounded-lg flex items-center gap-2 px-5 py-2.5 border border-indigo-700"
        size="lg"
        onClick={onCopilotClick}
      >
        <Sparkles className="h-4 w-4 text-cyan-300 group-hover:text-cyan-200 transition-colors" />
        <span className="font-semibold tracking-wide">Demander à l’IA</span>
      </Button>


    </div>
  );
}

// --- Section 2: Centre d'Actions ---

function PayrollCard({ status, onGenerateClick }: { status: DashboardData['payrollStatus'], onGenerateClick: () => void }) {
  return (
    <Card className="shadow-lg border-primary/20">
      <CardHeader>
        <CardTitle>Gestion de la Paie</CardTitle>
      </CardHeader>
      <CardContent>
        <button
          onClick={onGenerateClick}
          className="w-full group relative overflow-hidden rounded-lg border-2 border-indigo-200 bg-white hover:border-indigo-400 transition-all duration-300 shadow-sm hover:shadow-md"
        >
          <div className="flex items-center justify-center py-3 px-4">
            <Sparkles className="mr-2.5 h-5 w-5 text-indigo-500 group-hover:text-indigo-600 transition-colors" />
            <span className="text-sm font-semibold text-gray-800 group-hover:text-indigo-900 transition-colors">
              Générer la Paie
            </span>
          </div>
          <div className="absolute inset-0 -z-10 bg-gradient-to-r from-indigo-50 to-purple-50 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        </button>
      </CardContent>
    </Card>
  );
}

function NotificationsCard({ actions, alerts }: { actions: ActionItems, alerts: AlertItems }) {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Notifications</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <button
          onClick={() => navigate('/leaves')}
          className="w-full flex justify-between items-center p-3 rounded-lg hover:bg-muted transition-colors"
        >
          <div className="flex items-center">
            <CalendarCheck className={`h-5 w-5 mr-3 ${actions.pendingAbsences > 0 ? 'text-red-500' : 'text-foreground'}`} />
            <span className={`font-medium ${actions.pendingAbsences > 0 ? 'text-red-500' : 'text-foreground'}`}>Demandes d'absences</span>
          </div>
          <div className="flex items-center">
            <Badge className={actions.pendingAbsences > 0 ? 'bg-red-500 text-white' : 'bg-muted text-foreground'}>{actions.pendingAbsences}</Badge>
            <ChevronRight className="h-4 w-4 text-muted-foreground ml-2" />
          </div>
        </button>
        <button
          onClick={() => navigate('/expenses')}
          className="w-full flex justify-between items-center p-3 rounded-lg hover:bg-muted transition-colors"
        >
          <div className="flex items-center">
            <CreditCard className={`h-5 w-5 mr-3 ${actions.pendingExpenses > 0 ? 'text-red-500' : 'text-foreground'}`} />
            <span className={`font-medium ${actions.pendingExpenses > 0 ? 'text-red-500' : 'text-foreground'}`}>Notes de frais</span>
          </div>
          <div className="flex items-center">
            <Badge className={actions.pendingExpenses > 0 ? 'bg-red-500 text-white' : 'bg-muted text-foreground'}>{actions.pendingExpenses}</Badge>
            <ChevronRight className="h-4 w-4 text-muted-foreground ml-2" />
          </div>
        </button>
        <button
          onClick={() => navigate('/rates')}
          className="w-full flex justify-between items-center p-3 rounded-lg hover:bg-muted transition-colors"
        >
          <div className="flex items-center">
            <FileWarning className={`h-5 w-5 mr-3 ${alerts.obsoleteRates > 0 ? 'text-red-500' : 'text-foreground'}`} />
            <span className={`font-medium ${alerts.obsoleteRates > 0 ? 'text-red-500' : 'text-foreground'}`}>Taux de cotisations</span>
          </div>
          <div className="flex items-center">
            <Badge className={alerts.obsoleteRates > 0 ? 'bg-red-500 text-white' : 'bg-muted text-foreground'}>{alerts.obsoleteRates}</Badge>
            <ChevronRight className="h-4 w-4 text-muted-foreground ml-2" />
          </div>
        </button>
      </CardContent>
    </Card>
  );
}


function ResidencePermitCard({ stats, loading }: { stats: ResidencePermitStats | null, loading: boolean }) {
  const displayStats = stats || {
    total_expire: 0,
    total_a_renouveler: 0,
    total_a_renseigner: 0,
    total_valide: 0
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Titres de séjour</CardTitle>
        <p className="text-xs text-muted-foreground mt-1">Suivi des échéances administratives</p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center items-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-3">
            {/* Expiré */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-red-50 border border-red-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-red-500"></div>
                <span className="text-sm font-medium text-red-900">Expiré</span>
              </div>
              <span className="text-lg font-bold text-red-700">{displayStats.total_expire}</span>
            </div>

            {/* À renouveler */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-orange-50 border border-orange-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-orange-500"></div>
                <span className="text-sm font-medium text-orange-900">À renouveler</span>
              </div>
              <span className="text-lg font-bold text-orange-700">{displayStats.total_a_renouveler}</span>
            </div>

            {/* À renseigner */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-gray-500"></div>
                <span className="text-sm font-medium text-gray-900">À renseigner</span>
              </div>
              <span className="text-lg font-bold text-gray-700">{displayStats.total_a_renseigner}</span>
            </div>

            {/* Valide */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 border border-green-200">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500"></div>
                <span className="text-sm font-medium text-green-900">Valide</span>
              </div>
              <span className="text-lg font-bold text-green-700">{displayStats.total_valide}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MedicalFollowUpCard({ kpis, loading }: { kpis: KPIs | null; loading: boolean }) {
  const navigate = useNavigate();
  const overdue = kpis?.overdue_count ?? 0;
  const due30 = kpis?.due_within_30_count ?? 0;
  const totalAVenir = overdue + due30;
  const hasAlert = totalAVenir > 0;

  return (
    <Card className={hasAlert ? "border-teal-200" : ""}>
      <CardHeader>
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Stethoscope className="h-5 w-5 text-teal-600" />
          Suivi visites médicales
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin inline" />
          ) : (
            <>
              <span className={totalAVenir > 0 ? "font-bold text-teal-700" : ""}>
                {totalAVenir > 0 ? `${totalAVenir} visite${totalAVenir > 1 ? "s" : ""} à venir` : "À jour"}
              </span>
            </>
          )}
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center items-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-3">
            {overdue > 0 && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-red-50 border border-red-200">
                <span className="text-sm font-medium text-red-900">En retard</span>
                <span className="text-lg font-bold text-red-700">{overdue}</span>
              </div>
            )}
            {due30 > 0 && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-orange-50 border border-orange-200">
                <span className="text-sm font-medium text-orange-900">Échéance &lt; 30 j</span>
                <span className="text-lg font-bold text-orange-700">{due30}</span>
              </div>
            )}
            {!hasAlert && (
              <p className="text-sm text-muted-foreground py-2">Aucune visite à planifier.</p>
            )}
            <Button variant="outline" size="sm" className="w-full mt-2" onClick={() => navigate("/medical-follow-up")}>
              Voir le suivi médical
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RibAlertsCard({
  alerts,
  loading,
  onRefresh,
}: {
  alerts: ribAlertsApi.RibAlert[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const navigate = useNavigate();

  const handleMarkRead = async (id: string) => {
    try {
      await ribAlertsApi.markRibAlertRead(id);
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Landmark className="h-5 w-5" />
            Alertes RIB
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Landmark className="h-5 w-5" />
          Alertes RIB
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">Modification ou doublon de RIB</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.length === 0 ? (
          <p className="text-sm text-muted-foreground py-2">Aucune alerte RIB.</p>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-3 rounded-lg border text-sm ${alert.is_read ? "bg-muted/50 border-muted" : "bg-amber-50/50 border-amber-200"}`}
            >
              <div className="font-medium text-foreground">{alert.title}</div>
              <p className="text-muted-foreground mt-1 line-clamp-2">{alert.message}</p>
              <div className="flex items-center justify-between mt-2 gap-2">
                <span className="text-xs text-muted-foreground">
                  {new Date(alert.created_at).toLocaleDateString("fr-FR")}
                </span>
                <div className="flex gap-1">
                  {alert.employee_id && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => navigate(`/employees/${alert.employee_id}`)}
                    >
                      Fiche
                    </Button>
                  )}
                  {!alert.is_read && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => handleMarkRead(alert.id)}
                    >
                      Marquer lu
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

// --- Raccourcis pilotage (ligne du haut, hauteur compacte identique) ---
const shortcutCardClass = "hover:shadow-md transition-shadow cursor-pointer border-primary/20 h-[72px] flex";
const shortcutContentClass = "px-3 py-2 flex items-center gap-3 w-full min-h-0 flex-1";

function ShortcutSimulationCard() {
  const navigate = useNavigate();
  return (
    <Card className={shortcutCardClass} onClick={() => navigate("/simulation")}>
      <CardContent className={shortcutContentClass}>
        <div className="p-2 rounded-lg bg-indigo-100 text-indigo-600 shrink-0">
          <FlaskConical className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-sm text-foreground leading-tight">Simulation bulletin de paie</p>
          <p className="text-xs text-muted-foreground leading-tight">Calcul inverse & bulletin simulé</p>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
      </CardContent>
    </Card>
  );
}

function ShortcutExportsCard() {
  const navigate = useNavigate();
  return (
    <Card className={shortcutCardClass} onClick={() => navigate("/exports")}>
      <CardContent className={shortcutContentClass}>
        <div className="p-2 rounded-lg bg-emerald-100 text-emerald-600 shrink-0">
          <FileDown className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-sm text-foreground leading-tight">Export & détection anomalie</p>
          <p className="text-xs text-muted-foreground leading-tight">Paie, variables, prévisualisation</p>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
      </CardContent>
    </Card>
  );
}

function MedicalVisitShortcutCard({ kpis, loading }: { kpis: KPIs | null; loading: boolean }) {
  const navigate = useNavigate();
  const totalDue = (kpis?.overdue_count ?? 0) + (kpis?.due_within_30_count ?? 0);
  return (
    <Card className={shortcutCardClass} onClick={() => navigate("/medical-follow-up")}>
      <CardContent className={shortcutContentClass}>
        <div className="p-2 rounded-lg bg-teal-100 text-teal-600 shrink-0">
          <Stethoscope className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-sm text-foreground leading-tight">Suivi visites médicales</p>
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
          ) : (
            <p className="text-xs font-bold text-teal-700 leading-tight">
              {totalDue > 0 ? `${totalDue} visite${totalDue > 1 ? "s" : ""} à venir` : "À jour"}
            </p>
          )}
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
      </CardContent>
    </Card>
  );
}

// --- Répartition Homme / Femme ---
function GenderSplitCard({ kpis }: { kpis: KpiData }) {
  const hommes = kpis.hommesCount ?? null;
  const femmes = kpis.femmesCount ?? null;
  const hasData = hommes != null && femmes != null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          Répartition Homme / Femme
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!hasData ? (
          <p className="text-sm text-muted-foreground">Non renseigné</p>
        ) : (
          <div className="flex gap-6">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-blue-500" />
              <span className="text-sm font-medium">Hommes</span>
              <span className="font-bold text-foreground">{hommes}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-pink-500" />
              <span className="text-sm font-medium">Femmes</span>
              <span className="font-bold text-foreground">{femmes}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// --- Répartition CDD / CDI / Alternant / Stagiaire / Handicapé ---
const CONTRACT_LABELS: Record<string, string> = {
  CDI: "CDI",
  CDD: "CDD",
  Alternance: "Alternant",
  Stage: "Stagiaire",
  Intérim: "Intérim",
  Freelance: "Freelance",
  Autre: "Autre",
};

function ContractSplitCard({ kpis }: { kpis: KpiData }) {
  const dist = kpis.contractDistribution || {};
  const handicap = kpis.handicapesCount ?? 0;
  const types = ["CDI", "CDD", "Alternance", "Stage"].filter((t) => (dist[t] ?? 0) > 0);
  const otherKeys = Object.keys(dist).filter((k) => !["CDI", "CDD", "Alternance", "Stage"].includes(k));
  const hasAny = types.length > 0 || otherKeys.length > 0 || handicap > 0;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Briefcase className="h-4 w-4 text-muted-foreground" />
          Répartition contrats
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!hasAny ? (
          <p className="text-sm text-muted-foreground">Aucune donnée</p>
        ) : (
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {types.map((t) => (
              <span key={t} className="font-medium text-foreground">
                {CONTRACT_LABELS[t] ?? t}: <span className="font-bold">{dist[t] ?? 0}</span>
              </span>
            ))}
            {otherKeys.map((t) => (
              <span key={t} className="font-medium text-foreground">
                {CONTRACT_LABELS[t] ?? t}: <span className="font-bold">{dist[t] ?? 0}</span>
              </span>
            ))}
            {handicap > 0 && (
              <span className="font-medium text-foreground">
                Handicapé: <span className="font-bold">{handicap}</span>
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// --- KPI Coût heures sup (placeholder) ---
function HeuresSupKpiCard() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          Coût heures sup.
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold text-foreground">—</p>
        <p className="text-xs text-muted-foreground mt-1">Mois précédent (à venir)</p>
      </CardContent>
    </Card>
  );
}

// --- KPIs Recrutement ---
function RecruitmentKpisCard() {
  const navigate = useNavigate();
  const { data: settings } = useQuery({ queryKey: ["recruitment", "settings"], queryFn: getRecruitmentSettings });
  const { data: jobs = [] } = useQuery({ queryKey: ["recruitment", "jobs"], queryFn: () => getJobs("active"), enabled: !!settings?.enabled });
  const { data: candidates = [] } = useQuery({ queryKey: ["recruitment", "candidates"], queryFn: getCandidates, enabled: !!settings?.enabled });
  const inProgress = candidates.filter((c) => c.current_stage_type !== "hired" && c.current_stage_type !== "rejected").length;
  const hired = candidates.filter((c) => c.current_stage_type === "hired").length;
  if (!settings?.enabled) return null;
  return (
    <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate("/recruitment")}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <UserPlus className="h-4 w-4 text-muted-foreground" />
          Recrutement
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <p className="text-muted-foreground">Offres actives</p>
            <p className="font-bold text-foreground">{jobs.length}</p>
          </div>
          <div>
            <p className="text-muted-foreground">En cours</p>
            <p className="font-bold text-foreground">{inProgress}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Embauchés</p>
            <p className="font-bold text-foreground">{hired}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={(e) => { e.stopPropagation(); navigate("/recruitment"); }}>
          Voir le recrutement <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </CardContent>
    </Card>
  );
}

// --- Prévision masse salariale ---
function PrevisionMasseSalarialeCard({ kpis }: { kpis: KpiData }) {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          Prévision masse salariale
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-2">
          Évolution et pilotage de la masse salariale (effectif, coûts).
        </p>
        <Button variant="outline" size="sm" onClick={() => navigate("/company")}>
          Voir la fiche entreprise
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </CardContent>
    </Card>
  );
}

function ShortcutsCard() {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4" />
          Raccourcis
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">Accès rapides paie & exports</p>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3">
        <button
          onClick={() => navigate("/simulation")}
          className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-muted transition-colors text-left"
        >
          <span className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-indigo-500" />
            <span className="font-medium text-sm">Simulation bulletin</span>
          </span>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        </button>
        <button
          onClick={() => navigate("/payroll")}
          className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-muted transition-colors text-left"
        >
          <span className="flex items-center gap-2">
            <CreditCard className="h-4 w-4 text-cyan-500" />
            <span className="font-medium text-sm">Ajouter une saisie paie</span>
          </span>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        </button>
        <button
          onClick={() => navigate("/exports")}
          className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-muted transition-colors text-left"
        >
          <span className="flex items-center gap-2">
            <FileDown className="h-4 w-4 text-emerald-500" />
            <span className="font-medium text-sm">Exports & anomalies</span>
          </span>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        </button>
      </CardContent>
    </Card>
  );
}

// --- Personnalisation dashboard ---
function DashboardPersonnalisationCard() {
  return (
    <Card className="border-dashed">
      <CardContent className="p-4 flex items-center gap-3">
        <SlidersHorizontal className="h-5 w-5 text-muted-foreground" />
        <div>
          <p className="font-medium text-sm text-foreground">Personnalisation du dashboard</p>
          <p className="text-xs text-muted-foreground">Choisir les blocs affichés (bientôt)</p>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Section 3: Carte Effectif condensée ---

function EffectifCard({ kpis, absentsToday }: { kpis: KpiData, absentsToday: TeamPulseEmployee[] }) {
  const getAbsenceIcon = (status: string) => {
    if (status.includes('Maladie')) return <HeartPulse className="h-3 w-3 text-red-500" />;
    if (status.includes('Congé')) return <Plane className="h-3 w-3 text-blue-500" />;
    if (status.includes('RTT')) return <CalendarCheck className="h-3 w-3 text-purple-500" />;
    return <CalendarCheck className="h-3 w-3 text-gray-500" />;
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Effectif</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-4 gap-6">
          {/* Effectif Actif */}
          <div className="text-center">
            <p className="text-xs text-muted-foreground font-medium mb-2">Effectif Actif</p>
            <div className="text-3xl font-bold">{kpis.effectifActif}</div>
            {/* Répartition CDI/CDD */}
            <div className="flex items-center justify-center gap-3 pt-2 mt-2 border-t">
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground font-medium">CDI</p>
                <p className="text-sm font-bold text-blue-600">{kpis.cdiCount}</p>
              </div>
              <div className="h-6 w-px bg-border"></div>
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground font-medium">CDD</p>
                <p className="text-sm font-bold text-orange-600">{kpis.cddCount}</p>
              </div>
            </div>
          </div>

          {/* Absents Aujourd'hui */}
          <div className="text-center">
            <p className="text-xs text-muted-foreground font-medium mb-2">Absents Aujourd'hui</p>
            <div className={`text-3xl font-bold ${absentsToday.length > 0 ? 'text-red-500' : 'text-green-600'}`}>
              {absentsToday.length}
            </div>
            {absentsToday.length > 0 && absentsToday.length <= 2 && (
              <div className="space-y-1 pt-2 mt-2 border-t">
                {absentsToday.map((emp) => (
                  <div key={emp.id} className="flex items-center justify-center gap-1.5 text-[10px] text-muted-foreground">
                    {getAbsenceIcon(emp.status)}
                    <span className="font-medium">{emp.first_name} {emp.last_name}</span>
                  </div>
                ))}
              </div>
            )}
            {absentsToday.length > 2 && (
              <div className="text-[10px] text-muted-foreground pt-2 mt-2 border-t">
                {absentsToday.slice(0, 2).map((emp) => emp.first_name).join(', ')}...
              </div>
            )}
          </div>

          {/* Absentéisme (30j) */}
          <div className="text-center col-span-2">
            <p className="text-xs text-muted-foreground font-medium mb-2">Absentéisme (30j)</p>
            <div className={`text-3xl font-bold ${kpis.tauxAbsenteisme > 5 ? 'text-amber-500' : 'text-foreground'}`}>
              {kpis.tauxAbsenteisme.toFixed(1)}%
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

const chartConfig = {
  "Net_Verse": {
    label: "Net Versé",
    color: "hsl(142, 76%, 36%)", // Vert
  },
  "Charges": {
    label: "Charges",
    color: "hsl(0, 80%, 50%)", // Rouge
  },
} satisfies ChartConfig;

// --- Grande carte Coûts combinant Masse Salariale et Evolution ---

function CoutsCard({ kpis, chartData }: { kpis: KpiData, chartData: ChartDataPoint[] }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Coûts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Masse Salariale du mois précédent */}
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Masse Salariale {kpis.currentMonth}</h3>
          <div className="grid grid-cols-2 gap-6">
            <div className="text-center">
              <p className="text-xs text-red-500 font-medium mb-1">Coût Total</p>
              <div className="text-2xl font-bold text-foreground">{kpis.coutTotal.toLocaleString('fr-FR')} €</div>
            </div>
            <div className="text-center">
              <p className="text-xs text-green-600 font-medium mb-1">Net Versé</p>
              <div className="text-2xl font-bold text-foreground">{kpis.netVerse.toLocaleString('fr-FR')} €</div>
            </div>
          </div>
        </div>

        {/* Evolution des Coûts */}
        <div className="pt-4 border-t">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">Évolution (12 derniers mois)</h3>
          <ChartContainer config={chartConfig} className="h-[250px] w-full">
            <BarChart data={chartData}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis
                dataKey="name"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${(value / 1000).toFixed(0)}k€`}
              />
              <RechartsTooltip
                content={<ChartTooltipContent />}
                formatter={(value: number) => `${value.toLocaleString('fr-FR')} €`}
              />
              <Legend />
              <Bar
                dataKey="Net_Verse"
                stackId="a"
                fill="var(--color-Net_Verse)"
                radius={[0, 0, 0, 0]}
                name="Net Versé"
              />
              <Bar
                dataKey="Charges"
                stackId="a"
                fill="var(--color-Charges)"
                radius={[4, 4, 0, 0]}
                name="Charges"
              />
            </BarChart>
          </ChartContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Section 4: Pouls de l'Équipe ---

function AbsenteesCard({ employees }: { employees: TeamPulseEmployee[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Absents Aujourd'hui</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {employees.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun absent aujourd'hui.</p>
        ) : (
          employees.map(emp => (
            <div key={emp.id} className="flex items-center gap-3">
              <Avatar className="h-9 w-9">
                {/* ✅ CORRECTION: AvatarImage supprimé, Fallback utilisé */}
                <AvatarFallback>{emp.first_name[0]}{emp.last_name[0]}</AvatarFallback>
              </Avatar>
              <div>
                <p className="font-medium text-sm">{emp.first_name} {emp.last_name}</p>
                <Badge variant="outline" className="text-xs">
                  {emp.status === 'Maladie' ? <HeartPulse className="h-3 w-3 mr-1 text-red-500" /> : <Plane className="h-3 w-3 mr-1 text-blue-500" />}
                  {emp.status}
                </Badge>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function EventsCard({ events }: { events: TeamPulseEvent[] }) {
  const getIcon = (type: TeamPulseEvent['type']) => {
    if (type === 'birthday') return <PartyPopper className="h-5 w-5 text-pink-500" />;
    return <Briefcase className="h-5 w-5 text-indigo-500" />;
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>Événements & Anniversaires (7j)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun événement à venir.</p>
        ) : (
          events.map(event => (
            <div key={event.id} className="flex items-center gap-3">
              <div className="p-2 bg-muted rounded-full">{getIcon(event.type)}</div>
              <div>
                <p className="font-medium text-sm">{event.employee_name}</p>
                <p className="text-xs text-muted-foreground">{event.detail}</p>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

// --- Modal de Génération de Paie ---

function GeneratePayrollModal({ isOpen, onClose, employees }: { isOpen: boolean, onClose: () => void, employees: SimpleEmployee[] }) {
  const [selectedEmployees, setSelectedEmployees] = useState<Set<string>>(new Set());
  const [selectedMonth, setSelectedMonth] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<{ success: string[], errors: { id: string, name: string, error: string }[] }>({ success: [], errors: [] });

  // Générer les options de mois (12 derniers mois + mois actuel + 2 mois futurs)
  const generateMonthOptions = () => {
    const options = [];
    const now = new Date();

    // Générer 12 mois précédents + mois actuel + 2 mois futurs
    for (let i = -12; i <= 2; i++) {
      const date = new Date(now.getFullYear(), now.getMonth() + i, 1);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const value = `${year}-${month}`;
      const label = date.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
      options.push({ value, label: label.charAt(0).toUpperCase() + label.slice(1) });
    }

    return options;
  };

  const monthOptions = generateMonthOptions();

  // Initialiser avec le mois actuel
  useEffect(() => {
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    setSelectedMonth(currentMonth);
  }, []);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedEmployees(new Set(employees.map(e => e.id)));
    } else {
      setSelectedEmployees(new Set());
    }
  };

  const handleSelect = (id: string, checked: boolean) => {
    const newSet = new Set(selectedEmployees);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedEmployees(newSet);
  };

  const handleGenerate = async () => {
    setIsLoading(true);
    setResults({ success: [], errors: [] });

    const [yearStr, monthStr] = selectedMonth.split('-');
    const year = parseInt(yearStr);
    const month = parseInt(monthStr);

    const successList: string[] = [];
    const errorsList: { id: string, name: string, error: string }[] = [];

    // Générer la paie pour chaque employé sélectionné
    for (const employeeId of Array.from(selectedEmployees)) {
      const employee = employees.find(e => e.id === employeeId);
      const employeeName = employee ? `${employee.first_name} ${employee.last_name}` : employeeId;

      try {
        const response = await apiClient.post('/api/actions/generate-payslip', {
          employee_id: employeeId,
          year,
          month
        });

        if (response.data.status === 'success') {
          successList.push(employeeName);
        } else {
          errorsList.push({
            id: employeeId,
            name: employeeName,
            error: response.data.message || 'Erreur inconnue'
          });
        }
      } catch (error: any) {
        const errorMessage = error.response?.data?.detail || error.message || 'Erreur inconnue';
        errorsList.push({
          id: employeeId,
          name: employeeName,
          error: errorMessage
        });
      }
    }

    setResults({ success: successList, errors: errorsList });
    setIsLoading(false);

    // Si toutes les générations ont réussi, fermer le modal après 2 secondes
    if (errorsList.length === 0) {
      setTimeout(() => {
        onClose();
      }, 2000);
    }
  };

  const isAllSelected = employees.length > 0 && selectedEmployees.size === employees.length;

  // Réinitialiser les résultats quand le modal s'ouvre
  useEffect(() => {
    if (isOpen) {
      setResults({ success: [], errors: [] });
    }
  }, [isOpen]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md p-0">
        <DialogHeader className="p-6 pb-4">
          <DialogTitle>Générer la Paie</DialogTitle>
        </DialogHeader>

        {/* Sélection du mois */}
        <div className="px-6 pb-4">
          <Label htmlFor="month-select" className="text-sm font-medium mb-2 block">
            Mois de paie
          </Label>
          <Select value={selectedMonth} onValueChange={setSelectedMonth}>
            <SelectTrigger id="month-select">
              <SelectValue placeholder="Sélectionner un mois" />
            </SelectTrigger>
            <SelectContent>
              {monthOptions.map(option => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Liste des employés */}
        <Command className="p-2">
          <CommandInput placeholder="Rechercher un employé..." />
          <CommandList className="max-h-[300px] overflow-y-auto">
            <CommandEmpty>Aucun employé trouvé.</CommandEmpty>
            <CommandGroup>
              <CommandItem
                onSelect={() => handleSelectAll(!isAllSelected)}
                className="flex items-center gap-3"
              >
                <Checkbox
                  checked={isAllSelected}
                  onCheckedChange={handleSelectAll}
                />
                <label className="font-medium">Tout sélectionner</label>
              </CommandItem>
              {employees.map(emp => (
                <CommandItem
                  key={emp.id}
                  value={`${emp.first_name} ${emp.last_name}`}
                  onSelect={() => handleSelect(emp.id, !selectedEmployees.has(emp.id))}
                  className="flex items-center gap-3"
                >
                  <Checkbox
                    checked={selectedEmployees.has(emp.id)}
                    onCheckedChange={(checked) => handleSelect(emp.id, !!checked)}
                  />
                  <label>{emp.first_name} {emp.last_name}</label>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>

        {/* Affichage des résultats */}
        {(results.success.length > 0 || results.errors.length > 0) && (
          <div className="px-6 pb-4 space-y-3">
            {results.success.length > 0 && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm font-semibold text-green-800 mb-2">
                  ✓ Générations réussies ({results.success.length})
                </p>
                <ul className="text-xs text-green-700 space-y-1">
                  {results.success.map((name, idx) => (
                    <li key={idx}>• {name}</li>
                  ))}
                </ul>
              </div>
            )}
            {results.errors.length > 0 && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm font-semibold text-red-800 mb-2">
                  ✗ Erreurs ({results.errors.length})
                </p>
                <ul className="text-xs text-red-700 space-y-2">
                  {results.errors.map((err, idx) => (
                    <li key={idx}>
                      <span className="font-medium">{err.name}:</span> {err.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="p-6 pt-2 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            {results.success.length > 0 || results.errors.length > 0 ? 'Fermer' : 'Annuler'}
          </Button>
          <Button
            className="bg-cyan-500 hover:bg-cyan-600 text-white"
            onClick={handleGenerate}
            disabled={isLoading || selectedEmployees.size === 0 || !selectedMonth || results.success.length > 0 || results.errors.length > 0}
          >
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Générer ({selectedEmployees.size})
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}