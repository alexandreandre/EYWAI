// src/pages/PayrollDetail.tsx

import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import apiClient from '../api/apiClient';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Loader2, AlertCircle, Rocket, Download, ArrowLeft, Trash2, Edit } from "lucide-react";
interface Employee { 
  id: string; 
  first_name: string; 
  last_name: string; 
}
interface Payslip { 
  id: string;
  month: number; 
  year: number; 
  url: string; 
}
interface MonthStatus { 
  status: 'idle' | 'loading' | 'success' | 'error'; 
  url?: string; 
  payslipId?: string;
}

const months = Array.from({ length: 12 }, (_, i) => i + 1);

export default function PayrollDetail() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [allPayslips, setAllPayslips] = useState<Payslip[]>([]);
  const [statuses, setStatuses] = useState<{ [month: number]: MonthStatus }>({});
  const [loading, setLoading] = useState(true);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());

  const fetchPayslipData = async () => {
    if (!employeeId) return;
    setLoading(true);
    try {
      console.log("--- DÉBOGAGE (Frontend): Lancement de la récupération des données ---");
      const [employeeRes, payslipsRes] = await Promise.all([
        apiClient.get(`/api/employees/${employeeId}`),
        apiClient.get(`/api/employees/${employeeId}/payslips`)
      ]);
      
      console.log("DEBUG (Frontend): Données de l'employé reçues:", employeeRes.data);
      console.log("DEBUG (Frontend): Liste des bulletins reçue:", payslipsRes.data);

      setEmployee(employeeRes.data);
      setAllPayslips(payslipsRes.data);

      // Déterminer l'année à utiliser : si l'année sélectionnée n'a pas de bulletins,
      // utiliser l'année la plus récente disponible
      const availableYears = [...new Set(payslipsRes.data.map((p: Payslip) => p.year))].sort((a, b) => b - a);
      let yearToUse = selectedYear;
      if (availableYears.length > 0 && !availableYears.includes(selectedYear)) {
        yearToUse = availableYears[0];
        setSelectedYear(availableYears[0]);
      } else if (availableYears.length === 0) {
        // Si aucun bulletin n'existe, utiliser l'année actuelle
        yearToUse = new Date().getFullYear();
        setSelectedYear(yearToUse);
      }

      // Filtrer les bulletins pour l'année à utiliser et mettre à jour les statuts
      const filteredPayslips = payslipsRes.data.filter((p: Payslip) => p.year === yearToUse);
      const initialStatuses = months.reduce((acc, month) => {
        const generated = filteredPayslips.find((p: Payslip) => p.month === month);
        if (generated) {
            console.log(`DEBUG (Frontend): Bulletin trouvé pour le mois ${month}, URL: ${generated.url}`);
            acc[month] = { status: 'success', url: generated.url, payslipId: generated.id };
        } else {
            acc[month] = { status: 'idle' };
        }
        return acc;
      }, {} as { [month: number]: MonthStatus });
      
      setStatuses(initialStatuses);
    } catch (error) { 
      console.error("--- ❌ ERREUR (Frontend): Échec de la récupération des données ---", error); 
    } 
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchPayslipData();
  }, [employeeId]);

  // Mettre à jour les statuts quand l'année sélectionnée change
  useEffect(() => {
    if (allPayslips.length > 0) {
      const filteredPayslips = allPayslips.filter((p: Payslip) => p.year === selectedYear);
      const updatedStatuses = months.reduce((acc, month) => {
        const generated = filteredPayslips.find((p: Payslip) => p.month === month);
        if (generated) {
          acc[month] = { status: 'success', url: generated.url, payslipId: generated.id };
        } else {
          acc[month] = { status: 'idle' };
        }
        return acc;
      }, {} as { [month: number]: MonthStatus });
      setStatuses(updatedStatuses);
    }
  }, [selectedYear, allPayslips]);

  const handleRunPayroll = async (monthToCalculate: number) => {
    if (!employeeId) return;
    setStatuses(prev => ({ ...prev, [monthToCalculate]: { status: 'loading' } }));
    try {
      await apiClient.post('/api/actions/generate-payslip', {
        employee_id: employeeId,
        year: selectedYear,
        month: monthToCalculate
      });
      await fetchPayslipData();
    } catch (error) {
      setStatuses(prev => ({ ...prev, [monthToCalculate]: { status: 'error' } }));
    }
  };

  const handleDeletePayslip = async (payslipIdToDelete: string) => {
    try {
      await apiClient.delete(`/api/payslips/${payslipIdToDelete}`);
      await fetchPayslipData();
    } catch (error) {
      console.error("Erreur lors de la suppression", error);
      alert("La suppression a échoué.");
    }
  };

  const renderMonthActions = (month: number) => {
    const monthInfo = statuses[month] || { status: 'idle' };
    switch (monthInfo.status) {
      case 'loading': 
        return <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />;
      
      case 'success':
        return (
          <div className="flex items-center gap-1">
            {/* Bouton Modifier */}
            <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
              <Link to={`/payslips/${monthInfo.payslipId}/edit`}>
                <Edit className="h-4 w-4" />
              </Link>
            </Button>

            {/* Bouton Télécharger */}
            <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
              <a href={monthInfo.url} download>
                <Download className="h-4 w-4" />
              </a>
            </Button>

            {/* Bouton Regénérer SUPPRIMÉ */}

            {/* Bouton Supprimer */}
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Êtes-vous sûr ?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Cette action est irréversible. Le bulletin sera supprimé.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Annuler</AlertDialogCancel>
                  <AlertDialogAction onClick={() => handleDeletePayslip(monthInfo.payslipId!)}>
                    Confirmer la suppression
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        );

      case 'error': 
        return <Button variant="destructive" size="sm" onClick={() => handleRunPayroll(month)}>Réessayer</Button>;
      
      default: 
        return <Button size="sm" variant="outline" onClick={() => handleRunPayroll(month)}>Générer</Button>;
    }
  };

  if (loading) return <div className="flex justify-center items-center h-48"><Loader2 className="h-8 w-8 animate-spin" /></div>;
  
  return (
    <div className="space-y-6">
      <Link to="/payroll" className="flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste
      </Link>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Paie pour {employee?.first_name} {employee?.last_name}</h1>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="year-select" className="text-sm font-medium">
            Année :
          </Label>
          <Select value={selectedYear.toString()} onValueChange={(value) => setSelectedYear(parseInt(value))}>
            <SelectTrigger id="year-select" className="w-[140px]">
              <SelectValue placeholder="Sélectionner une année" />
            </SelectTrigger>
            <SelectContent>
              {(() => {
                // Générer les années disponibles : années des bulletins existants + années récentes
                const availableYears = [...new Set(allPayslips.map((p: Payslip) => p.year))];
                const currentYear = new Date().getFullYear();
                const yearsToShow = new Set<number>();
                
                // Ajouter les années des bulletins existants
                availableYears.forEach(year => yearsToShow.add(year));
                
                // Ajouter les 3 dernières années et les 2 prochaines années
                for (let i = currentYear - 3; i <= currentYear + 2; i++) {
                  yearsToShow.add(i);
                }
                
                return Array.from(yearsToShow).sort((a, b) => b - a).map(year => (
                  <SelectItem key={year} value={year.toString()}>
                    {year}
                  </SelectItem>
                ));
              })()}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle>Gestion Mensuelle</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {months.map(month => (
              <div key={month} className="p-4 border rounded-lg flex justify-between items-center">
                <span className="font-medium capitalize">
                  {new Date(selectedYear, month - 1, 1).toLocaleString('fr-FR', { month: 'long' })}
                </span>
                {renderMonthActions(month)}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}