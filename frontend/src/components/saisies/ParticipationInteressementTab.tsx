// Composant pour le simulateur Participation & Intéressement
import { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Download, Calculator, Info, Save, FolderOpen } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import apiClient from '@/api/apiClient';

// Types
interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  job_title?: string;
  hire_date?: string;
  salaire_de_base?: {
    valeur?: number;
    type?: string; // 'mensuel' ou 'annuel'
  } | null;
}

interface EmployeeData extends Employee {
  annualSalary: number;
  presenceDays: number;
  presencePercent: number;
  seniorityYears: number;
}

interface CalculationResult {
  employeeId: string;
  employeeName: string;
  participationAmount: number;
  interessementAmount: number;
  totalAmount: number;
}

// Constantes
const PASS_2026_DEFAULT = 48060; // Valeur par défaut si non trouvée dans Supabase

type DistributionMode = 'uniforme' | 'salaire' | 'presence' | 'combinaison';

export function ParticipationInteressementTab() {
  const { toast } = useToast();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeData, setEmployeeData] = useState<Map<string, EmployeeData>>(new Map());
  const [isLoading, setIsLoading] = useState(true);
  const [employeesData, setEmployeesData] = useState<any[]>([]); // Stocker les données brutes de l'API
  const [passValue, setPassValue] = useState<number>(PASS_2026_DEFAULT);

  // Données entreprise (année N)
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [beneficeNet, setBeneficeNet] = useState<string>('');
  const [capitauxPropres, setCapitauxPropres] = useState<string>('');
  const [salairesBruts, setSalairesBruts] = useState<string>('');
  const [valeurAjoutee, setValeurAjoutee] = useState<string>('');

  // Paramètres Participation
  const [participationMode, setParticipationMode] = useState<DistributionMode>('salaire');
  const [participationSalairePercent, setParticipationSalairePercent] = useState<number>(50);
  const [participationPresencePercent, setParticipationPresencePercent] = useState<number>(50);
  // Plafond individuel calculé automatiquement depuis PASS (non modifiable)
  const plafondIndividuel = passValue * 0.75;

  // Paramètres Intéressement
  const [interessementEnabled, setInteressementEnabled] = useState<boolean>(false);
  const [interessementEnvelope, setInteressementEnvelope] = useState<string>('');
  const [interessementMode, setInteressementMode] = useState<DistributionMode>('salaire');
  const [interessementSalairePercent, setInteressementSalairePercent] = useState<number>(50);
  const [interessementPresencePercent, setInteressementPresencePercent] = useState<number>(50);

  // Gestion des simulations sauvegardées
  const [savedSimulations, setSavedSimulations] = useState<Array<{id: string, year: number, simulation_name: string, created_at: string}>>([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [simulationName, setSimulationName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [selectedSimulationId, setSelectedSimulationId] = useState<string>('');

  // Charger le PASS depuis Supabase
  useEffect(() => {
    const fetchPASS = async () => {
      try {
        const res = await apiClient.get<Record<string, { config_data: any }>>('/api/rates/all');
        const pssConfig = res.data['pss'];
        if (pssConfig?.config_data?.annuel) {
          setPassValue(pssConfig.config_data.annuel);
        } else {
          console.warn('PASS non trouvé dans Supabase, utilisation de la valeur par défaut');
        }
      } catch (error) {
        console.error('Erreur lors du chargement du PASS:', error);
        // On garde la valeur par défaut en cas d'erreur
      }
    };
    fetchPASS();
  }, []);

  // Charger les données réelles des employés depuis l'endpoint dédié
  useEffect(() => {
    const fetchEmployeeData = async () => {
      setIsLoading(true);
      try {
        // Appel à l'endpoint backend qui calcule tout
        const res = await apiClient.get<{
          employees: Array<{
            employee_id: string;
            first_name: string;
            last_name: string;
            annual_salary: number;
            presence_days: number;
            seniority_years: number;
            has_real_salary?: boolean;
            has_real_presence?: boolean;
          }>;
          year: number;
        }>(`/api/participation/employee-data/${year}`);
        
        const employeesDataFromApi = res.data.employees || [];
        
        // Stocker les données brutes pour vérifier les indicateurs
        setEmployeesData(employeesDataFromApi);
        
        // Initialiser les données des employés avec les valeurs réelles
        const initialData = new Map<string, EmployeeData>();
        const employeesList: Employee[] = [];
        
        employeesDataFromApi.forEach(empData => {
          employeesList.push({
            id: empData.employee_id,
            first_name: empData.first_name,
            last_name: empData.last_name,
            job_title: undefined,
            hire_date: undefined,
            salaire_de_base: undefined,
          });
          
          initialData.set(empData.employee_id, {
            id: empData.employee_id,
            first_name: empData.first_name,
            last_name: empData.last_name,
            job_title: undefined,
            hire_date: undefined,
            salaire_de_base: undefined,
            annualSalary: empData.annual_salary,
            presenceDays: empData.presence_days,
            presencePercent: (empData.presence_days / 218) * 100,
            seniorityYears: empData.seniority_years,
          });
        });
        
        // Log pour debug
        console.log(`[Participation] Données chargées pour ${year}:`, {
          employeesCount: employeesDataFromApi.length,
          salaries: employeesDataFromApi.map((e: any) => ({ 
            name: `${e.first_name} ${e.last_name}`, 
            salary: e.annual_salary, 
            hasReal: e.has_real_salary 
          })),
          presences: employeesDataFromApi.map((e: any) => ({ 
            name: `${e.first_name} ${e.last_name}`, 
            days: e.presence_days, 
            hasReal: e.has_real_presence 
          }))
        });
        
        setEmployees(employeesList);
        setEmployeeData(initialData);
      } catch (error) {
        console.error(error);
        toast({ 
          title: "Erreur", 
          description: "Impossible de charger les données réelles des employés. Les valeurs par défaut seront utilisées.", 
          variant: "destructive" 
        });
      } finally {
        setIsLoading(false);
      }
    };
    
    if (year) {
      fetchEmployeeData();
    }
  }, [year, toast]);

  // Charger les simulations sauvegardées
  useEffect(() => {
    const fetchSimulations = async () => {
      try {
        const res = await apiClient.get(`/api/participation/simulations?year=${year}`);
        setSavedSimulations(res.data || []);
      } catch (error) {
        console.error('Erreur lors du chargement des simulations:', error);
      }
    };
    fetchSimulations();
  }, [year]);

  // Fonction pour sauvegarder la simulation
  const handleSaveSimulation = async () => {
    if (!simulationName.trim()) {
      toast({
        title: "Erreur",
        description: "Veuillez saisir un nom pour la simulation.",
        variant: "destructive"
      });
      return;
    }

    setIsSaving(true);
    try {
      // Préparer les résultats
      const results: Record<string, any> = {};
      Array.from(employeeData.values()).forEach(emp => {
        const participation = participationDistribution.get(emp.id) || 0;
        const interessement = interessementDistribution.get(emp.id) || 0;
        results[emp.id] = {
          employeeName: `${emp.first_name} ${emp.last_name}`,
          participationAmount: participation,
          interessementAmount: interessement,
          totalAmount: participation + interessement
        };
      });

      const simulationData = {
        year,
        simulation_name: simulationName.trim(),
        benefice_net: parseFloat(beneficeNet) || 0,
        capitaux_propres: parseFloat(capitauxPropres) || 0,
        salaires_bruts: parseFloat(salairesBruts) || 0,
        valeur_ajoutee: parseFloat(valeurAjoutee) || 0,
        participation_mode: participationMode,
        participation_salaire_percent: participationSalairePercent,
        participation_presence_percent: participationPresencePercent,
        interessement_enabled: interessementEnabled,
        interessement_envelope: interessementEnabled ? (parseFloat(interessementEnvelope) || 0) : null,
        interessement_mode: interessementEnabled ? interessementMode : null,
        interessement_salaire_percent: interessementSalairePercent,
        interessement_presence_percent: interessementPresencePercent,
        results_data: results
      };

      await apiClient.post('/api/participation/simulations', simulationData);
      
      toast({
        title: "Succès",
        description: "Simulation sauvegardée avec succès."
      });
      
      setShowSaveDialog(false);
      setSimulationName('');
      
      // Recharger la liste des simulations
      const res = await apiClient.get(`/api/participation/simulations?year=${year}`);
      setSavedSimulations(res.data || []);
    } catch (error: any) {
      console.error('Erreur lors de la sauvegarde:', error);
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Erreur lors de la sauvegarde de la simulation.",
        variant: "destructive"
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Fonction pour charger une simulation
  const handleLoadSimulation = async (simulationId: string) => {
    try {
      const res = await apiClient.get(`/api/participation/simulations/${simulationId}`);
      const sim = res.data;
      
      // Charger les données dans le formulaire
      setYear(sim.year);
      setBeneficeNet(sim.benefice_net.toString());
      setCapitauxPropres(sim.capitaux_propres.toString());
      setSalairesBruts(sim.salaires_bruts.toString());
      setValeurAjoutee(sim.valeur_ajoutee.toString());
      setParticipationMode(sim.participation_mode);
      setParticipationSalairePercent(sim.participation_salaire_percent);
      setParticipationPresencePercent(sim.participation_presence_percent);
      setInteressementEnabled(sim.interessement_enabled);
      setInteressementEnvelope(sim.interessement_envelope?.toString() || '');
      setInteressementMode(sim.interessement_mode || 'salaire');
      setInteressementSalairePercent(sim.interessement_salaire_percent);
      setInteressementPresencePercent(sim.interessement_presence_percent);
      
      toast({
        title: "Succès",
        description: `Simulation "${sim.simulation_name}" chargée avec succès.`
      });
    } catch (error) {
      console.error('Erreur lors du chargement:', error);
      toast({
        title: "Erreur",
        description: "Erreur lors du chargement de la simulation.",
        variant: "destructive"
      });
    }
  };

  // Calcul de la RSP (Réserve Spéciale de Participation)
  const calculateRSP = useMemo(() => {
    const B = parseFloat(beneficeNet) || 0;
    const C = parseFloat(capitauxPropres) || 0;
    const S = parseFloat(salairesBruts) || 0;
    const VA = parseFloat(valeurAjoutee) || 0;

    if (VA === 0) return 0;

    const base = B - (0.05 * C);
    if (base < 0) return 0;

    return 0.5 * base * (S / VA);
  }, [beneficeNet, capitauxPropres, salairesBruts, valeurAjoutee]);

  // Répartition de la Participation
  const participationDistribution = useMemo(() => {
    if (calculateRSP === 0) return new Map<string, number>();

    const distribution = new Map<string, number>();
    const employeesList = Array.from(employeeData.values());

    if (employeesList.length === 0) return distribution;

    switch (participationMode) {
      case 'uniforme': {
        const amountPerEmployee = calculateRSP / employeesList.length;
        employeesList.forEach(emp => {
          distribution.set(emp.id, Math.min(amountPerEmployee, plafondIndividuel));
        });
        break;
      }
      case 'salaire': {
        const plafondSalaire = passValue * 3; // 3 × PASS
        const salairesPlafonnes = employeesList.map(emp => ({
          id: emp.id,
          salaire: Math.min(emp.annualSalary, plafondSalaire)
        }));
        const totalSalaire = salairesPlafonnes.reduce((sum, e) => sum + e.salaire, 0);
        
        if (totalSalaire > 0) {
          salairesPlafonnes.forEach(({ id, salaire }) => {
            const amount = (calculateRSP * salaire) / totalSalaire;
            distribution.set(id, Math.min(amount, plafondIndividuel));
          });
        }
        break;
      }
      case 'presence': {
        const totalPresence = employeesList.reduce((sum, emp) => sum + emp.presenceDays, 0);
        if (totalPresence > 0) {
          employeesList.forEach(emp => {
            const amount = (calculateRSP * emp.presenceDays) / totalPresence;
            distribution.set(emp.id, Math.min(amount, plafondIndividuel));
          });
        }
        break;
      }
      case 'combinaison': {
        const plafondSalaire = passValue * 3;
        const salairesPlafonnes = employeesList.map(emp => ({
          id: emp.id,
          salaire: Math.min(emp.annualSalary, plafondSalaire),
          presence: emp.presenceDays
        }));
        const totalSalaire = salairesPlafonnes.reduce((sum, e) => sum + e.salaire, 0);
        const totalPresence = salairesPlafonnes.reduce((sum, e) => sum + e.presence, 0);
        
        if (totalSalaire > 0 && totalPresence > 0) {
          const salaireWeight = participationSalairePercent / 100;
          const presenceWeight = participationPresencePercent / 100;
          
          salairesPlafonnes.forEach(({ id, salaire, presence }) => {
            const partSalaire = (salaire / totalSalaire) * salaireWeight;
            const partPresence = (presence / totalPresence) * presenceWeight;
            const amount = calculateRSP * (partSalaire + partPresence);
            distribution.set(id, Math.min(amount, plafondIndividuel));
          });
        }
        break;
      }
    }

    return distribution;
  }, [calculateRSP, employeeData, participationMode, participationSalairePercent, participationPresencePercent, passValue, plafondIndividuel]);

  // Répartition de l'Intéressement
  const interessementDistribution = useMemo(() => {
    if (!interessementEnabled) return new Map<string, number>();
    const envelope = parseFloat(interessementEnvelope) || 0;
    if (envelope === 0) return new Map<string, number>();

    const distribution = new Map<string, number>();
    const employeesList = Array.from(employeeData.values());

    if (employeesList.length === 0) return distribution;

    switch (interessementMode) {
      case 'uniforme': {
        const amountPerEmployee = envelope / employeesList.length;
        employeesList.forEach(emp => {
          distribution.set(emp.id, Math.min(amountPerEmployee, plafondIndividuel));
        });
        break;
      }
      case 'salaire': {
        const plafondSalaire = passValue * 3;
        const salairesPlafonnes = employeesList.map(emp => ({
          id: emp.id,
          salaire: Math.min(emp.annualSalary, plafondSalaire)
        }));
        const totalSalaire = salairesPlafonnes.reduce((sum, e) => sum + e.salaire, 0);
        
        if (totalSalaire > 0) {
          salairesPlafonnes.forEach(({ id, salaire }) => {
            const amount = (envelope * salaire) / totalSalaire;
            distribution.set(id, Math.min(amount, plafondIndividuel));
          });
        }
        break;
      }
      case 'presence': {
        const totalPresence = employeesList.reduce((sum, emp) => sum + emp.presenceDays, 0);
        if (totalPresence > 0) {
          employeesList.forEach(emp => {
            const amount = (envelope * emp.presenceDays) / totalPresence;
            distribution.set(emp.id, Math.min(amount, plafondIndividuel));
          });
        }
        break;
      }
      case 'combinaison': {
        const plafondSalaire = passValue * 3;
        const salairesPlafonnes = employeesList.map(emp => ({
          id: emp.id,
          salaire: Math.min(emp.annualSalary, plafondSalaire),
          presence: emp.presenceDays
        }));
        const totalSalaire = salairesPlafonnes.reduce((sum, e) => sum + e.salaire, 0);
        const totalPresence = salairesPlafonnes.reduce((sum, e) => sum + e.presence, 0);
        
        if (totalSalaire > 0 && totalPresence > 0) {
          const salaireWeight = interessementSalairePercent / 100;
          const presenceWeight = interessementPresencePercent / 100;
          
          salairesPlafonnes.forEach(({ id, salaire, presence }) => {
            const partSalaire = (salaire / totalSalaire) * salaireWeight;
            const partPresence = (presence / totalPresence) * presenceWeight;
            const amount = envelope * (partSalaire + partPresence);
            distribution.set(id, Math.min(amount, plafondIndividuel));
          });
        }
        break;
      }
    }

    return distribution;
  }, [interessementEnabled, interessementEnvelope, employeeData, interessementMode, interessementSalairePercent, interessementPresencePercent, passValue, plafondIndividuel]);

  // Résultats finaux
  const results = useMemo<CalculationResult[]>(() => {
    return Array.from(employeeData.values()).map(emp => {
      const participation = participationDistribution.get(emp.id) || 0;
      const interessement = interessementDistribution.get(emp.id) || 0;
      return {
        employeeId: emp.id,
        employeeName: `${emp.first_name} ${emp.last_name}`,
        participationAmount: participation,
        interessementAmount: interessement,
        totalAmount: participation + interessement,
      };
    });
  }, [employeeData, participationDistribution, interessementDistribution]);

  // Export CSV
  const exportToCSV = () => {
    const headers = [
      'Nom',
      'Salaire annuel (€)',
      'Jours de présence',
      'Ancienneté (années)',
      'Participation (€)',
      'Intéressement (€)',
      'Total (€)'
    ];

    const rows = results.map(r => {
      const emp = employeeData.get(r.employeeId);
      return [
        r.employeeName,
        (emp?.annualSalary || 0).toFixed(2),
        (emp?.presenceDays || 0).toString(),
        (emp?.seniorityYears || 0).toString(),
        r.participationAmount.toFixed(2),
        r.interessementAmount.toFixed(2),
        r.totalAmount.toFixed(2)
      ];
    });

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `participation_interessement_${year}.csv`;
    link.click();
  };


  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(amount);
  };

  if (isLoading) {
    return <div className="flex justify-center items-center h-48">Chargement...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Paramètres entreprise */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <Calculator className="h-4 w-4" />
            Données entreprise
            <div className="flex items-center gap-2">
              <Label htmlFor="year-select" className="text-sm font-normal text-muted-foreground">
                Année
              </Label>
              <Select value={year.toString()} onValueChange={(value) => setYear(parseInt(value))}>
                <SelectTrigger id="year-select" className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(() => {
                    const currentYear = new Date().getFullYear();
                    return Array.from({ length: 11 }, (_, i) => currentYear - i)
                      .filter((y) => y >= currentYear - 10)
                      .map((y) => (
                        <SelectItem key={y} value={y.toString()}>
                          {y}
                        </SelectItem>
                      ));
                  })()}
                </SelectContent>
              </Select>
            </div>
          </CardTitle>
          <CardDescription>
            Saisissez les données financières de l'exercice pour calculer la Réserve Spéciale de Participation (RSP)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Actions : Charger une simulation */}
          <div className="flex items-center gap-2 pb-2 border-b">
            <Label className="text-sm text-muted-foreground">Charger une simulation :</Label>
            <Select 
              value={selectedSimulationId || undefined} 
              onValueChange={(value) => {
                setSelectedSimulationId(value);
                if (value && value !== 'none') {
                  handleLoadSimulation(value);
                  // Réinitialiser après un court délai pour permettre de re-sélectionner
                  setTimeout(() => setSelectedSimulationId(''), 100);
                }
              }}
            >
              <SelectTrigger className="w-[250px]">
                <SelectValue placeholder="Sélectionner une simulation..." />
              </SelectTrigger>
              <SelectContent>
                {savedSimulations.length === 0 ? (
                  <div className="px-2 py-1.5 text-sm text-muted-foreground">Aucune simulation sauvegardée</div>
                ) : (
                  savedSimulations.map((sim) => (
                    <SelectItem key={sim.id} value={sim.id}>
                      {sim.simulation_name} ({sim.year})
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="benefice">Bénéfice net fiscal (B) *</Label>
              <Input
                id="benefice"
                type="number"
                value={beneficeNet}
                onChange={(e) => setBeneficeNet(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="capitaux">Capitaux propres (C) *</Label>
              <Input
                id="capitaux"
                type="number"
                value={capitauxPropres}
                onChange={(e) => setCapitauxPropres(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="salaires">Salaires bruts versés (S) *</Label>
              <Input
                id="salaires"
                type="number"
                value={salairesBruts}
                onChange={(e) => setSalairesBruts(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="va">Valeur ajoutée (VA) *</Label>
              <Input
                id="va"
                type="number"
                value={valeurAjoutee}
                onChange={(e) => setValeurAjoutee(e.target.value)}
                placeholder="0"
              />
            </div>
          </div>

          {/* Résultat RSP */}
          {valeurAjoutee && parseFloat(valeurAjoutee) > 0 && (
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription>
                <div className="space-y-2">
                  <div className="font-semibold">RSP calculée : {formatCurrency(calculateRSP)}</div>
                  <div className="text-sm text-muted-foreground">
                    Formule : RSP = 1/2 × (B − 5% × C) × (S / VA)
                    {calculateRSP === 0 && parseFloat(beneficeNet) > 0 && (
                      <span className="block mt-1 text-orange-600">
                        ⚠️ (B − 5% × C) est négatif, la RSP est donc nulle.
                      </span>
                    )}
                  </div>
                </div>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Paramètres de répartition */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Participation */}
        <Card>
          <CardHeader>
            <CardTitle>Répartition Participation</CardTitle>
            <CardDescription>Mode de répartition de la RSP entre les collaborateurs</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Mode de répartition</Label>
              <Select value={participationMode} onValueChange={(v) => setParticipationMode(v as DistributionMode)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="uniforme">Uniforme (même montant)</SelectItem>
                  <SelectItem value="salaire">Proportionnelle au salaire</SelectItem>
                  <SelectItem value="presence">Proportionnelle à la présence</SelectItem>
                  <SelectItem value="combinaison">Combinaison salaire + présence</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {participationMode === 'combinaison' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Salaire (%)</Label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={participationSalairePercent}
                    onChange={(e) => {
                      const val = parseInt(e.target.value) || 0;
                      setParticipationSalairePercent(val);
                      setParticipationPresencePercent(100 - val);
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Présence (%)</Label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={participationPresencePercent}
                    onChange={(e) => {
                      const val = parseInt(e.target.value) || 0;
                      setParticipationPresencePercent(val);
                      setParticipationSalairePercent(100 - val);
                    }}
                  />
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label>PASS (Plafond Annuel Sécurité Sociale)</Label>
              <div className="px-3 py-2 bg-muted rounded-md text-sm">
                {formatCurrency(passValue)} (valeur standard {year})
              </div>
              <p className="text-xs text-muted-foreground">
                Plafond salaire pris en compte : 3 × PASS = {formatCurrency(passValue * 3)}
              </p>
            </div>

            <div className="space-y-2">
              <Label>Plafond individuel (75% PASS)</Label>
              <div className="px-3 py-2 bg-muted rounded-md text-sm">
                {formatCurrency(plafondIndividuel)}
              </div>
              <p className="text-xs text-muted-foreground">
                Calculé automatiquement : 75% × PASS
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Intéressement */}
        <Card>
          <CardHeader>
            <CardTitle>Intéressement</CardTitle>
            <CardDescription>Enveloppe et répartition de l'intéressement</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="interessement-enabled"
                checked={interessementEnabled}
                onChange={(e) => setInteressementEnabled(e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="interessement-enabled" className="cursor-pointer">
                Activer l'intéressement
              </Label>
            </div>

            {interessementEnabled && (
              <>
                <div className="space-y-2">
                  <Label>Enveloppe annuelle (€)</Label>
                  <Input
                    type="number"
                    value={interessementEnvelope}
                    onChange={(e) => setInteressementEnvelope(e.target.value)}
                    placeholder="0"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Mode de répartition</Label>
                  <Select value={interessementMode} onValueChange={(v) => setInteressementMode(v as DistributionMode)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="uniforme">Uniforme (même montant)</SelectItem>
                      <SelectItem value="salaire">Proportionnelle au salaire</SelectItem>
                      <SelectItem value="presence">Proportionnelle à la présence</SelectItem>
                      <SelectItem value="combinaison">Combinaison salaire + présence</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {interessementMode === 'combinaison' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Salaire (%)</Label>
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={interessementSalairePercent}
                        onChange={(e) => {
                          const val = parseInt(e.target.value) || 0;
                          setInteressementSalairePercent(val);
                          setInteressementPresencePercent(100 - val);
                        }}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Présence (%)</Label>
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={interessementPresencePercent}
                        onChange={(e) => {
                          const val = parseInt(e.target.value) || 0;
                          setInteressementPresencePercent(val);
                          setInteressementSalairePercent(100 - val);
                        }}
                      />
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Données employés */}
      <Card>
        <CardHeader>
          <CardTitle>Données employés (Année {year})</CardTitle>
          <CardDescription>
            Données réelles calculées depuis les cumuls annuels (décembre) ou les bulletins de paie, et les plannings de l'année {year}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nom</TableHead>
                  <TableHead className="text-right">Salaire annuel (€)</TableHead>
                  <TableHead className="text-right">Jours présence</TableHead>
                  <TableHead className="text-right">Ancienneté (ans)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from(employeeData.values()).map(emp => (
                  <TableRow key={emp.id}>
                    <TableCell className="font-medium">{emp.first_name} {emp.last_name}</TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(emp.annualSalary)}
                    </TableCell>
                    <TableCell className="text-right">
                      {emp.presenceDays}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {emp.seniorityYears}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Résultats */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Résultats de la simulation</CardTitle>
              <CardDescription>
                Répartition calculée pour l'année {year}
              </CardDescription>
            </div>
            <Button onClick={exportToCSV} variant="outline">
              <Download className="h-4 w-4 mr-2" />
              Exporter CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employé</TableHead>
                  <TableHead className="text-right">Participation (€)</TableHead>
                  <TableHead className="text-right">Intéressement (€)</TableHead>
                  <TableHead className="text-right font-bold">Total (€)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.length > 0 ? (
                  results.map((result) => (
                    <TableRow key={result.employeeId}>
                      <TableCell className="font-medium">{result.employeeName}</TableCell>
                      <TableCell className="text-right">{formatCurrency(result.participationAmount)}</TableCell>
                      <TableCell className="text-right">{formatCurrency(result.interessementAmount)}</TableCell>
                      <TableCell className="text-right font-bold">{formatCurrency(result.totalAmount)}</TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-muted-foreground">
                      Aucun résultat disponible. Remplissez les données entreprise pour calculer.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {results.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <div className="flex justify-between items-center">
                <span className="font-semibold">Total distribué :</span>
                <span className="text-lg font-bold">
                  {formatCurrency(results.reduce((sum, r) => sum + r.totalAmount, 0))}
                </span>
              </div>
              <div className="flex justify-between items-center mt-2 text-sm text-muted-foreground">
                <span>Dont Participation :</span>
                <span>{formatCurrency(results.reduce((sum, r) => sum + r.participationAmount, 0))}</span>
              </div>
              {interessementEnabled && (
                <div className="flex justify-between items-center mt-2 text-sm text-muted-foreground">
                  <span>Dont Intéressement :</span>
                  <span>{formatCurrency(results.reduce((sum, r) => sum + r.interessementAmount, 0))}</span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Bouton de sauvegarde en bas de page */}
      <div className="flex justify-end pt-4">
        <Button 
          onClick={() => setShowSaveDialog(true)} 
          size="lg"
        >
          <Save className="h-4 w-4 mr-2" />
          Sauvegarder la simulation
        </Button>
      </div>

      {/* Dialog pour sauvegarder une simulation */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sauvegarder la simulation</DialogTitle>
            <DialogDescription>
              Donnez un nom à cette simulation pour pouvoir la réutiliser plus tard.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="simulation-name">Nom de la simulation *</Label>
              <Input
                id="simulation-name"
                value={simulationName}
                onChange={(e) => setSimulationName(e.target.value)}
                placeholder="Ex: Simulation 2026 - Scénario optimiste"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && simulationName.trim()) {
                    handleSaveSimulation();
                  }
                }}
              />
            </div>
            <div className="text-sm text-muted-foreground">
              Année : {year}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => {
              setShowSaveDialog(false);
              setSimulationName('');
            }}>
              Annuler
            </Button>
            <Button onClick={handleSaveSimulation} disabled={isSaving || !simulationName.trim()}>
              {isSaving ? "Sauvegarde..." : "Sauvegarder"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
