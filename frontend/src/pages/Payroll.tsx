// src/pages/Payroll.tsx

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import apiClient from '../api/apiClient';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Loader2, ChevronRight, Sparkles } from "lucide-react"; // Ajout de Sparkles
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";


interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
}
// --- ✅ COPIE TOUT CE BLOC DEPUIS DASHBOARD.TSX ---

// Types nécessaires pour le modal
type SimpleEmployee = {
  id: string;
  first_name: string;
  last_name: string;
};

// --- Modal de Génération de Paie ---
function GeneratePayrollModal({ isOpen, onClose, employees }: { isOpen: boolean, onClose: () => void, employees: SimpleEmployee[] }) {
  const [selectedEmployees, setSelectedEmployees] = useState<Set<string>>(new Set());
  const [selectedMonth, setSelectedMonth] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<{ success: string[], errors: { id: string, name: string, error: string }[] }>({ success: [], errors: [] });

  // Générer les options de mois
  const generateMonthOptions = () => {
    const options = [];
    const now = new Date();
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

    if (errorsList.length === 0) {
      setTimeout(() => {
        onClose();
      }, 2000);
    }
  };

  const isAllSelected = employees.length > 0 && selectedEmployees.size === employees.length;

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
// --- FIN DU BLOC COPIÉ ---

export default function Payroll() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);

  useEffect(() => {
    const fetchEmployees = async () => {
      try {
        setLoading(true);
        const response = await apiClient.get<Employee[]>('/api/employees');
        setEmployees(response.data);
      } catch (err) {
        setError("Erreur : Impossible de récupérer la liste des collaborateurs.");
      } finally {
        setLoading(false);
      }
    };
    fetchEmployees();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Gestion de la Paie</h1>
        <p className="text-muted-foreground mt-2">
          Sélectionnez un collaborateur pour gérer ses bulletins de paie mensuels.
        </p>
      </div>
      <Card>
        <CardHeader>
           <CardTitle>Génération groupée</CardTitle>
        </CardHeader>
        <CardContent>
          <button
            onClick={() => setIsGenerateModalOpen(true)}
            className="w-full group relative overflow-hidden rounded-lg border-2 border-indigo-200 bg-white hover:border-indigo-400 transition-all duration-300 shadow-sm hover:shadow-md"
          >
            <div className="flex items-center justify-center py-3 px-4">
              <Sparkles className="mr-2.5 h-5 w-5 text-indigo-500 group-hover:text-indigo-600 transition-colors" />
              <span className="text-sm font-semibold text-gray-800 group-hover:text-indigo-900 transition-colors">
                Générer la Paie (Mode groupé)
              </span>
            </div>
            <div className="absolute inset-0 -z-10 bg-gradient-to-r from-indigo-50 to-purple-50 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          </button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Liste des Collaborateurs</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Collaborateur</TableHead><TableHead>Poste</TableHead><TableHead className="text-right"></TableHead></TableRow></TableHeader>
            <TableBody>
              {loading && <TableRow><TableCell colSpan={3} className="h-24 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></TableCell></TableRow>}
              {error && <TableRow><TableCell colSpan={3} className="h-24 text-center text-red-500">{error}</TableCell></TableRow>}
              {!loading && !error && employees.map((employee) => (
                <TableRow key={employee.id} className="cursor-pointer hover:bg-muted/50">
                  <TableCell>
                    <Link to={`/payroll/${employee.id}`} className="flex items-center gap-3">
                      <Avatar className="h-8 w-8"><AvatarFallback>{employee.first_name.charAt(0)}{employee.last_name.charAt(0)}</AvatarFallback></Avatar>
                      <span className="font-medium">{employee.first_name} {employee.last_name}</span>
                    </Link>
                  </TableCell>
                  <TableCell>
                     <Link to={`/payroll/${employee.id}`} className="block w-full h-full">{employee.job_title}</Link>
                  </TableCell>
                  <TableCell className="text-right">
                    <Link to={`/payroll/${employee.id}`}><ChevronRight className="h-4 w-4" /></Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <GeneratePayrollModal
        isOpen={isGenerateModalOpen}
        onClose={() => setIsGenerateModalOpen(false)}
        employees={employees}
      />
    </div>
  );
}