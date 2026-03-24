// Composant pour l'onglet Primes (contenu actuel de Saisies.tsx)
import { useState, useEffect, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, PlusCircle, Trash2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { SaisieModal } from "@/components/SaisieModal";
import * as saisiesApi from '@/api/saisies';
import apiClient from '@/api/apiClient';

// --- Types & Interfaces ---
interface Employee { id: string; first_name: string; last_name: string; job_title: string; }
type MonthlyInput = saisiesApi.MonthlyInput;
type MonthlyInputCreate = saisiesApi.MonthlyInputCreate;

interface PrimesTabProps {
  selectedYear: number;
  selectedMonth: number;
  onYearChange: (year: number) => void;
  onMonthChange: (month: number) => void;
}

export function PrimesTab({ selectedYear, selectedMonth, onYearChange, onMonthChange }: PrimesTabProps) {
  const { toast } = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [monthlyInputs, setMonthlyInputs] = useState<MonthlyInput[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Helper pour générer les listes des sélecteurs
  const yearOptions = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i);
  const monthOptions = [
    { value: 1, label: "Janvier" }, { value: 2, label: "Février" },
    { value: 3, label: "Mars" }, { value: 4, label: "Avril" },
    { value: 5, label: "Mai" }, { value: 6, label: "Juin" },
    { value: 7, label: "Juillet" }, { value: 8, label: "Août" },
    { value: 9, label: "Septembre" }, { value: 10, label: "Octobre" },
    { value: 11, label: "Novembre" }, { value: 12, label: "Décembre" },
  ];

  // Utilisation de useCallback pour la stabilité
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [inputsRes, employeesRes] = await Promise.all([
        saisiesApi.getAllMonthlyInputs(selectedYear, selectedMonth), 
        apiClient.get<Employee[]>('/api/employees')
      ]);
      setMonthlyInputs(inputsRes.data);
      setEmployees(employeesRes.data);
    } catch (error) {
      console.error(error);
      toast({ title: "Erreur", description: "Impossible de charger les données.", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [selectedYear, selectedMonth, toast]); 

  useEffect(() => { 
    fetchData(); 
  }, [fetchData]);

  const handleSaveSaisie = async (payloadsFromModal: MonthlyInputCreate[]) => {
    try {
      // On s'assure que chaque saisie envoyée utilise le mois et l'année
      // sélectionnés sur la page, peu importe ce que le modal a pu générer.
      const correctedPayloads = payloadsFromModal.map(payload => ({
        ...payload,
        year: selectedYear,
        month: selectedMonth,
      }));

      await saisiesApi.createMonthlyInputs(correctedPayloads);
      
      toast({ title: "Succès", description: "Saisie(s) ajoutée(s) avec succès." });
      fetchData();
      setModalOpen(false);
    } catch (error) {
      toast({ title: "Erreur", description: "Échec de l'ajout de la saisie.", variant: "destructive" });
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Supprimer cette saisie ?")) return;
    try {
      await saisiesApi.deleteMonthlyInput(id);
      toast({ title: "Supprimée", description: "La saisie a été supprimée." });
      fetchData();
    } catch (error) {
      toast({ title: "Erreur", description: "Impossible de supprimer la saisie.", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      {/* Sélecteurs de date */}
      <div className="flex flex-col md:flex-row justify-between md:items-start gap-4">
        <div>
          <p className="text-muted-foreground">
            Éléments variables pour {new Date(selectedYear, selectedMonth - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' })}
          </p>
          
          <div className="flex items-center gap-2 mt-4">
            <Select
              value={String(selectedMonth)}
              onValueChange={(val) => onMonthChange(Number(val))}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Mois" />
              </SelectTrigger>
              <SelectContent>
                {monthOptions.map(opt => (
                  <SelectItem key={opt.value} value={String(opt.value)}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={String(selectedYear)}
              onValueChange={(val) => onYearChange(Number(val))}
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Année" />
              </SelectTrigger>
              <SelectContent>
                {yearOptions.map(year => (
                  <SelectItem key={year} value={String(year)}>
                    {year}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <Button onClick={() => setModalOpen(true)} className="w-full md:w-auto">
          <PlusCircle className="mr-2 h-4 w-4" /> Nouvelle saisie
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Saisies enregistrées</CardTitle>
          <CardDescription>Liste de toutes les saisies ponctuelles pour le mois en cours.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center items-center h-48"><Loader2 className="h-8 w-8 animate-spin" /></div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employé</TableHead>
                  <TableHead>Nom</TableHead>
                  <TableHead>Montant</TableHead>
                  <TableHead>Soumis Cotisations</TableHead>
                  <TableHead>Soumis Impôt</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {monthlyInputs.length > 0 ? (
                  monthlyInputs.map((input) => {
                    const emp = employees.find(e => e.id === input.employee_id);
                    return (
                      <TableRow key={input.id}>
                        <TableCell>{emp ? `${emp.first_name} ${emp.last_name}` : "Inconnu"}</TableCell>
                        <TableCell className="font-medium">{input.name}</TableCell>
                        <TableCell>{new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(input.amount)}</TableCell>
                        <TableCell>
                          <Badge variant={input.is_socially_taxed ? "default" : "secondary"}>
                            {input.is_socially_taxed ? 'Oui' : 'Non'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={input.is_taxable ? "default" : "secondary"}>
                            {input.is_taxable ? 'Oui' : 'Non'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="icon" onClick={() => handleDelete(input.id)} title="Supprimer">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center h-24">Aucune saisie enregistrée pour ce mois.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      
      <SaisieModal 
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSaveSaisie}
        employees={employees}
        year={selectedYear}
        month={selectedMonth}
      />
    </div>
  );
}
