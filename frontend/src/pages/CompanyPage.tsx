import { useState, useEffect, useLayoutEffect, useRef } from "react";
import apiClient from "@/api/apiClient";
import { useAuth } from "@/contexts/AuthContext";

// --- Composants UI ---
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, AlertTriangle, Users, Euro, FileText, Building, Percent, CalendarDays, PlusCircle, Trash2, Edit2, HeartHandshake } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { ChevronsUpDown, Check } from "lucide-react";
import CollectiveAgreementCard from "@/components/CollectiveAgreementCard";
import { mutuelleTypesApi, MutuelleType, MutuelleTypeCreate, MutuelleTypeUpdate } from "@/api/mutuelleTypes";



// --- Types de Données (basés sur votre API et schéma BDD) ---
interface CompanyDetails {
  id: string;
  company_name: string;
  raison_sociale: string | null;
  siret: string | null;
  siren: string | null;
  code_naf: string | null;
  naf_ape: string | null;
  legal_form: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  urssaf_number: string | null;
  collective_agreement: string | null;
  idcc: string | null;
  effectif: number | null;
  paie_jour_de_fin: number | null;
  paie_occurrence: number | null;
  taux_at_mp: number | null;
  taux_vm: number | null;
  taux_fnal: number | null;
  adresse_rue: string | null;
  adresse_code_postal: string | null;
  adresse_ville: string | null;
  settings?: { medical_follow_up_enabled?: boolean };
}

interface MonthlyEvolution {
  month: string;
  masse_salariale_brute: number;
  net_verse: number;
  charges_totales: number;
  cout_total_employeur: number;
}

interface CompanyKPIs {
  total_employees: number;
  last_month_gross_salary: number;
  last_month_net_salary: number;
  last_month_employer_charges: number;
  last_month_employee_charges: number;
  last_month_total_cost: number;
  last_month_total_charges: number;
  annual_gross_salary: number;
  annual_total_cost: number;
  contract_distribution: Record<string, number>;
  job_distribution: Record<string, number>;
  new_hires_last_30_days: number;
  payroll_tax_rate: number;
  average_cost_per_employee: number;
  evolution_12_months: MonthlyEvolution[];
}

interface CompanyData {
  company_data: CompanyDetails;
  kpis: CompanyKPIs;
}
/**
 * Traduit l'index du jour de paie en langage naturel.
 * (Hypothèse: 0=Lundi, 1=Mardi, ..., 4=Vendredi)
 */
const formatPayday = (day: number | null | undefined): string => {
  if (day === null || day === undefined) return "Non défini";
  const dayMap: Record<number, string> = {
    "0": "Lundi",
    "1": "Mardi",
    "2": "Mercredi",
    "3": "Jeudi",
    "4": "Vendredi",
    "5": "Samedi",
    "6": "Dimanche"
  };
  return dayMap[day] || String(day);
};

/**
 * Traduit l'index d'occurrence en langage naturel.
 * (Hypothèse: -1=Dernier, -2=Avant-dernier)
 */
const formatOccurrence = (occ: number | null | undefined): string => {
  if (occ === null || occ === undefined) return "Non défini";
  const occurrenceMap: Record<number, string> = {
    "-1": "Dernier du mois",
    "-2": "Avant-dernier du mois",
    "-3": "Antepénultième du mois",
    "1": "Premier du mois",
    "2": "Deuxième du mois",
    "3": "Troisième du mois",
    "4": "Quatrième du mois",
    "5": "Cinquième du mois",
  };
  return occurrenceMap[occ] || String(occ);
};

// Helper pour formater les pourcentages
const formatPercentage = (value: number | null | undefined) => {
  if (value === null || value === undefined) return "N/A";
  // On suppose que les taux sont stockés en décimal (ex: 0.05 pour 5%)
  const percent = value > 1 ? value : value * 100;
  return `${percent.toFixed(2)} %`;
};

// --- Composant Principal ---
export default function CompanyPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [data, setData] = useState<CompanyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("informations");
  const scrollPositionRef = useRef<number>(0);

  useEffect(() => {
    const fetchCompanyData = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.get<CompanyData>('/api/company/details');
        setData(response.data);
      } catch (e: any) {
        const errorMsg = e.response?.data?.detail || e.message || "Une erreur est survenue.";
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    };
    fetchCompanyData();
  }, []);

  // Restaurer la position de scroll après le changement d'onglet
  useLayoutEffect(() => {
    if (scrollPositionRef.current > 0) {
      // Utiliser requestAnimationFrame pour s'assurer que le DOM est complètement rendu
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
          const targetScroll = Math.min(scrollPositionRef.current, maxScroll);
          window.scrollTo(0, targetScroll);
        });
      });
    }
  }, [activeTab]);

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
    return <div className="text-center text-muted-foreground py-10">Aucune donnée d'entreprise trouvée.</div>;
  }

  const { company_data, kpis } = data;

  // Formater les montants en euros
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  // Formater les mois pour affichage
  const formatMonth = (monthStr: string) => {
    const [year, month] = monthStr.split('-');
    const monthNames = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'];
    return `${monthNames[parseInt(month) - 1]} ${year}`;
  };

  // --- Rendu Principal ---
  return (
    <div className="space-y-6 animate-fade-in">
      {/* 1. Header */}
      <div className="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-lg p-6 text-white shadow-lg">
        <h1 className="text-3xl font-bold">{company_data.company_name}</h1>
        <p className="mt-2 text-indigo-100">
          Tableau de bord de pilotage - Vue d'ensemble de votre entreprise
        </p>
      </div>

      {/* 2. KPIs Principaux */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="border-l-4 border-l-indigo-500">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Effectif Actif</CardTitle>
              <Users className="h-5 w-5 text-indigo-500" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-indigo-600">{kpis.total_employees}</div>
            <p className="text-xs text-muted-foreground mt-1">collaborateurs</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-amber-500">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Masse Salariale (M-1)</CardTitle>
              <Euro className="h-5 w-5 text-amber-500" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-amber-600">{formatCurrency(kpis.last_month_gross_salary)}</div>
            <p className="text-xs text-muted-foreground mt-1">salaire brut</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-red-500">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Charges Totales (M-1)</CardTitle>
              <Percent className="h-5 w-5 text-red-500" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-red-600">{formatCurrency(kpis.last_month_total_charges)}</div>
            <p className="text-xs text-muted-foreground mt-1">patronales + salariales</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Coût Total Employeur (M-1)</CardTitle>
              <Building className="h-5 w-5 text-purple-500" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-600">{formatCurrency(kpis.last_month_total_cost)}</div>
            <p className="text-xs text-muted-foreground mt-1">coût complet</p>
          </CardContent>
        </Card>
      </div>

      {/* 3. KPIs Secondaires */}
      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Net Versé (M-1)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-green-600">{formatCurrency(kpis.last_month_net_salary)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Charges Patronales</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-orange-600">{formatCurrency(kpis.last_month_employer_charges)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Charges Salariales</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-blue-600">{formatCurrency(kpis.last_month_employee_charges)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Taux de Charges</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-slate-600">{kpis.payroll_tax_rate}%</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Coût Moyen/Employé</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-indigo-600">{formatCurrency(kpis.average_cost_per_employee)}</div>
          </CardContent>
        </Card>
      </div>

      {/* 4. Graphiques et Analyses */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <CalendarDays className="mr-2 h-5 w-5" />
              Évolution 12 Derniers Mois
            </CardTitle>
            <CardDescription>Masse salariale et coût total employeur</CardDescription>
          </CardHeader>
          <CardContent>
            {kpis.evolution_12_months && kpis.evolution_12_months.length > 0 ? (
              <div className="space-y-4">
                {kpis.evolution_12_months.slice(-6).map((month, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{formatMonth(month.month)}</span>
                      <span className="text-muted-foreground">{formatCurrency(month.cout_total_employeur)}</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2">
                      <div
                        className="bg-gradient-to-r from-indigo-500 to-purple-600 h-2 rounded-full transition-all"
                        style={{ width: `${Math.min((month.cout_total_employeur / Math.max(...kpis.evolution_12_months.map(m => m.cout_total_employeur))) * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Aucune donnée disponible</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <FileText className="mr-2 h-5 w-5" />
              Répartition des Contrats
            </CardTitle>
            <CardDescription>Distribution CDI, CDD, etc.</CardDescription>
          </CardHeader>
          <CardContent>
            {Object.keys(kpis.contract_distribution).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(kpis.contract_distribution).map(([type, count]) => (
                  <div key={type} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{type}</span>
                      <Badge variant="secondary">{count} ({Math.round((count / kpis.total_employees) * 100)}%)</Badge>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2">
                      <div
                        className="bg-indigo-500 h-2 rounded-full transition-all"
                        style={{ width: `${(count / kpis.total_employees) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Aucune donnée</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 5. Statistiques Annuelles */}
      <Card className="bg-gradient-to-br from-slate-50 to-slate-100 border-slate-200">
        <CardHeader>
          <CardTitle className="text-lg">Bilan Annuel (12 derniers mois)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Masse Salariale Brute Totale</p>
              <p className="text-2xl font-bold text-amber-600">{formatCurrency(kpis.annual_gross_salary)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Coût Total Employeur</p>
              <p className="text-2xl font-bold text-purple-600">{formatCurrency(kpis.annual_total_cost)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Nouvelles Embauches (30j)</p>
              <p className="text-2xl font-bold text-green-600">+{kpis.new_hires_last_30_days}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 6. Répartition par Poste */}
      {Object.keys(kpis.job_distribution).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Users className="mr-2 h-5 w-5" />
              Répartition par Poste
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {Object.entries(kpis.job_distribution).map(([job, count]) => (
                <div key={job} className="flex justify-between items-center p-2 bg-slate-50 rounded-md">
                  <span className="text-sm font-medium truncate">{job}</span>
                  <Badge variant="outline">{count}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 3. Onglets pour les Données Détaillées */}
      <Tabs value={activeTab} onValueChange={(value) => {
        // Sauvegarder la position de scroll actuelle
        scrollPositionRef.current = window.scrollY;
        setActiveTab(value);
      }}>
        <TabsList className="grid w-full grid-cols-4 max-w-2xl">
          <TabsTrigger value="informations">Informations Légales</TabsTrigger>
          <TabsTrigger value="coordonnees">Coordonnées</TabsTrigger>
          <TabsTrigger value="parametres">Paramètres Paie</TabsTrigger>
          <TabsTrigger value="mutuelle">Mutuelle</TabsTrigger>
        </TabsList>
        
        <TabsContent value="informations" className="mt-4">
          <Card>
            <CardHeader><CardTitle>Informations Légales & Administratives</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableBody>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground w-[250px]">Raison Sociale</TableCell>
                    <TableCell>{company_data.raison_sociale || company_data.company_name}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground">Forme Juridique</TableCell>
                    <TableCell>{company_data.legal_form || "Non renseigné"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground">SIREN</TableCell>
                    <TableCell>{company_data.siren || "Non renseigné"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground">SIRET (Siège)</TableCell>
                    <TableCell>{company_data.siret || "Non renseigné"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground">Code NAF/APE</TableCell>
                    <TableCell>{company_data.naf_ape || company_data.code_naf || "Non renseigné"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground">Numéro URSSAF</TableCell>
                    <TableCell>{company_data.urssaf_number || "Non renseigné"}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="coordonnees" className="mt-4">
          <Card>
            <CardHeader><CardTitle>Coordonnées & Siège Social</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableBody>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground w-[250px]">Adresse</TableCell>
                    <TableCell>
                      {company_data.adresse_rue ? (
                        <address className="not-italic">
                          {company_data.adresse_rue}<br />
                          {company_data.adresse_code_postal} {company_data.adresse_ville}
                        </address>
                      ) : (
                        "Non renseignée"
                      )}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground">Téléphone</TableCell>
                    <TableCell>{company_data.phone || "Non renseigné"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground">Email de contact</TableCell>
                    <TableCell>{company_data.email || "Non renseigné"}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium text-muted-foreground">Site Web</TableCell>
                    <TableCell>{company_data.website || "Non renseigné"}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="parametres" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <CollectiveAgreementCard />

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center"><Percent className="mr-2 h-5 w-5 text-amber-600" /> Taux Spécifiques</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableBody>
                    <TableRow>
                      <TableCell className="font-medium text-muted-foreground">Taux Accident Travail (AT/MP)</TableCell>
                      <TableCell className="font-semibold">{formatPercentage(company_data.taux_at_mp)}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium text-muted-foreground">Taux Versement Mobilité (VM)</TableCell>
                      <TableCell className="font-semibold">{formatPercentage(company_data.taux_vm)}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium text-muted-foreground">Taux FNAL</TableCell>
                      <TableCell className="font-semibold">{formatPercentage(company_data.taux_fnal)}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center"><CalendarDays className="mr-2 h-5 w-5 text-muted-foreground" /> Paramètres de Période</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableBody>
                    <TableRow>
                      <TableCell className="font-medium text-muted-foreground w-[250px]">Jour de fin de période de paie</TableCell>
                      <TableCell className="font-medium">{formatPayday(company_data.paie_jour_de_fin)}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium text-muted-foreground">Occurrence de la paie</TableCell>
                      <TableCell className="font-medium">{formatOccurrence(company_data.paie_occurrence)}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="mutuelle" className="mt-4">
          <MutuelleManagementTab />
        </TabsContent>

      </Tabs>
    </div>
  );
}

// Interface pour un employé simple
interface SimpleEmployee {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
}

// Composant pour la gestion des mutuelles
function MutuelleManagementTab() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [mutuelles, setMutuelles] = useState<MutuelleType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingMutuelle, setEditingMutuelle] = useState<MutuelleType | null>(null);
  const [formData, setFormData] = useState<MutuelleTypeCreate>({
    libelle: '',
    montant_salarial: 0,
    montant_patronal: 0,
    part_patronale_soumise_a_csg: true,
    is_active: true,
    employee_ids: [],
  });
  const [employees, setEmployees] = useState<SimpleEmployee[]>([]);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [employeePopoverOpen, setEmployeePopoverOpen] = useState(false);

  useEffect(() => {
    loadMutuelles();
    loadEmployees();
  }, []);

  const loadEmployees = async () => {
    try {
      setLoadingEmployees(true);
      const response = await apiClient.get<SimpleEmployee[]>('/api/employees');
      setEmployees(response.data);
    } catch (error: any) {
      console.error("Erreur lors du chargement des employés:", error);
    } finally {
      setLoadingEmployees(false);
    }
  };

  const loadMutuelles = async () => {
    try {
      setLoading(true);
      const data = await mutuelleTypesApi.getMutuelleTypes();
      setMutuelles(data);
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible de charger les mutuelles",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (mutuelle?: MutuelleType) => {
    if (mutuelle) {
      setEditingMutuelle(mutuelle);
      setFormData({
        libelle: mutuelle.libelle,
        montant_salarial: mutuelle.montant_salarial,
        montant_patronal: mutuelle.montant_patronal,
        part_patronale_soumise_a_csg: mutuelle.part_patronale_soumise_a_csg,
        is_active: true, // Non utilisé dans le formulaire, mais gardé pour la structure
        employee_ids: mutuelle.employee_ids || [],
      });
    } else {
      setEditingMutuelle(null);
      setFormData({
        libelle: '',
        montant_salarial: 0,
        montant_patronal: 0,
        part_patronale_soumise_a_csg: true,
        is_active: true, // Toujours true par défaut lors de la création
        employee_ids: [],
      });
    }
    setShowDialog(true);
  };

  const handleCloseDialog = () => {
    setShowDialog(false);
    setEditingMutuelle(null);
  };

  const handleSubmit = async () => {
    if (!formData.libelle || formData.montant_salarial < 0 || formData.montant_patronal < 0) {
      toast({
        title: "Erreur",
        description: "Veuillez remplir tous les champs correctement",
        variant: "destructive",
      });
      return;
    }

    try {
      if (editingMutuelle) {
        // Lors de la modification, ne pas modifier is_active (géré uniquement par le bouton Désactiver/Activer)
        const { is_active, ...updateData } = formData;
        await mutuelleTypesApi.updateMutuelleType(editingMutuelle.id, updateData);
        toast({
          title: "Succès",
          description: "Formule de mutuelle mise à jour",
        });
      } else {
        // Lors de la création, toujours créer avec is_active = true
        const { is_active, ...createData } = formData;
        await mutuelleTypesApi.createMutuelleType({ ...createData, is_active: true });
        toast({
          title: "Succès",
          description: "Formule de mutuelle créée",
        });
      }
      handleCloseDialog();
      loadMutuelles();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Une erreur est survenue",
        variant: "destructive",
      });
    }
  };

  const handleSelectAllEmployees = () => {
    if (formData.employee_ids?.length === employees.length) {
      setFormData({ ...formData, employee_ids: [] });
    } else {
      setFormData({ ...formData, employee_ids: employees.map(e => e.id) });
    }
  };

  const handleToggleEmployee = (employeeId: string) => {
    const currentIds = formData.employee_ids || [];
    const isSelected = currentIds.includes(employeeId);
    const newIds = isSelected
      ? currentIds.filter(id => id !== employeeId)
      : [...currentIds, employeeId];
    setFormData({ ...formData, employee_ids: newIds });
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Êtes-vous sûr de vouloir supprimer cette formule de mutuelle ?")) {
      return;
    }

    try {
      await mutuelleTypesApi.deleteMutuelleType(id);
      toast({
        title: "Succès",
        description: "Formule de mutuelle supprimée",
      });
      loadMutuelles();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible de supprimer la formule",
        variant: "destructive",
      });
    }
  };

  const handleToggleActive = async (mutuelle: MutuelleType) => {
    try {
      await mutuelleTypesApi.updateMutuelleType(mutuelle.id, {
        is_active: !mutuelle.is_active,
      });
      toast({
        title: "Succès",
        description: mutuelle.is_active ? "Formule désactivée" : "Formule activée",
      });
      loadMutuelles();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Une erreur est survenue",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-10">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <div>
            <CardTitle className="flex items-center">
              <HeartHandshake className="mr-2 h-5 w-5" />
              Formules de Mutuelle
            </CardTitle>
            <CardDescription>
              Gérez les formules de mutuelle disponibles pour vos employés
            </CardDescription>
          </div>
          {user?.role && ['admin', 'rh', 'super_admin'].includes(user.role) && (
            <Button onClick={() => handleOpenDialog()}>
              <PlusCircle className="mr-2 h-4 w-4" />
              Ajouter une formule
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {mutuelles.length === 0 ? (
          <div className="text-center py-10 text-muted-foreground">
            Aucune formule de mutuelle définie
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Libellé</TableHead>
                <TableHead>Montant Salarial (€)</TableHead>
                <TableHead>Montant Patronal (€)</TableHead>
                <TableHead>Part Patronale CSG</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mutuelles.map((mutuelle) => (
                <TableRow key={mutuelle.id}>
                  <TableCell className="font-medium">{mutuelle.libelle}</TableCell>
                  <TableCell>{mutuelle.montant_salarial.toFixed(2)}</TableCell>
                  <TableCell>{mutuelle.montant_patronal.toFixed(2)}</TableCell>
                  <TableCell>
                    {mutuelle.part_patronale_soumise_a_csg ? (
                      <Badge variant="default">Oui</Badge>
                    ) : (
                      <Badge variant="secondary">Non</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {mutuelle.is_active ? (
                      <Badge variant="default">Active</Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                    {mutuelle.employee_ids && mutuelle.employee_ids.length > 0 && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({mutuelle.employee_ids.length} employé{mutuelle.employee_ids.length > 1 ? 's' : ''})
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      {user?.role && ['admin', 'rh', 'super_admin'].includes(user.role) && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleToggleActive(mutuelle)}
                            title={mutuelle.is_active ? "Désactiver" : "Activer"}
                          >
                            {mutuelle.is_active ? "Désactiver" : "Activer"}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenDialog(mutuelle)}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(mutuelle.id)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingMutuelle ? "Modifier la formule" : "Nouvelle formule de mutuelle"}
            </DialogTitle>
            <DialogDescription>
              {editingMutuelle
                ? "Modifiez les informations de la formule de mutuelle"
                : "Remplissez les informations pour créer une nouvelle formule de mutuelle"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="libelle">Libellé *</Label>
              <Input
                id="libelle"
                value={formData.libelle}
                onChange={(e) => setFormData({ ...formData, libelle: e.target.value })}
                placeholder="Ex: Mutuelle Collaborateur Seul"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="montant_salarial">Montant Salarial (€) *</Label>
                <Input
                  id="montant_salarial"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.montant_salarial}
                  onChange={(e) =>
                    setFormData({ ...formData, montant_salarial: parseFloat(e.target.value) || 0 })
                  }
                />
              </div>
              <div>
                <Label htmlFor="montant_patronal">Montant Patronal (€) *</Label>
                <Input
                  id="montant_patronal"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.montant_patronal}
                  onChange={(e) =>
                    setFormData({ ...formData, montant_patronal: parseFloat(e.target.value) || 0 })
                  }
                />
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="part_patronale_csg"
                checked={formData.part_patronale_soumise_a_csg}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, part_patronale_soumise_a_csg: checked === true })
                }
              />
              <Label htmlFor="part_patronale_csg" className="cursor-pointer">
                Part patronale soumise à CSG (défiscalisation)
              </Label>
            </div>
            
            {/* Sélection des employés */}
            <div className="space-y-2">
              <Label>Employés souscrivant à cette mutuelle</Label>
              <Popover open={employeePopoverOpen} onOpenChange={setEmployeePopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    className="w-full justify-between font-normal"
                    disabled={loadingEmployees}
                  >
                    {formData.employee_ids && formData.employee_ids.length > 0
                      ? `${formData.employee_ids.length} employé(s) sélectionné(s)`
                      : "Sélectionner des employés..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0 z-[100]" align="start">
                  <Command>
                    <CommandInput placeholder="Rechercher un employé..." />
                    <CommandList className="max-h-[300px] overflow-y-auto">
                      <CommandEmpty>Aucun employé trouvé.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem onSelect={handleSelectAllEmployees} className="cursor-pointer">
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.employee_ids?.length === employees.length ? "opacity-100" : "opacity-0"
                            )}
                          />
                          {formData.employee_ids?.length === employees.length
                            ? "Tout désélectionner"
                            : "Tout sélectionner"}
                        </CommandItem>
                        {employees.map((employee) => (
                          <CommandItem
                            key={employee.id}
                            value={`${employee.first_name} ${employee.last_name}`}
                            onSelect={() => handleToggleEmployee(employee.id)}
                            className="cursor-pointer"
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                formData.employee_ids?.includes(employee.id) ? "opacity-100" : "opacity-0"
                              )}
                            />
                            <div>
                              <p>{employee.first_name} {employee.last_name}</p>
                              {employee.job_title && (
                                <p className="text-xs text-muted-foreground">{employee.job_title}</p>
                              )}
                            </div>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
              {formData.employee_ids && formData.employee_ids.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {formData.employee_ids.length} employé(s) sélectionné(s). Ces employés seront automatiquement associés à cette mutuelle.
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              Annuler
            </Button>
            <Button onClick={handleSubmit}>
              {editingMutuelle ? "Modifier" : "Créer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}