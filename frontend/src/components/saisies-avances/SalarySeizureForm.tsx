// frontend/src/components/saisies-avances/SalarySeizureForm.tsx

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { Loader2 } from "lucide-react";
import { createSalarySeizure } from '@/api/saisiesAvances';
import type { SalarySeizureCreate } from '@/api/saisiesAvances';
import apiClient from '@/api/apiClient';

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
}

interface SalarySeizureFormProps {
  onClose: () => void;
  onSuccess: () => void;
}

export function SalarySeizureForm({ onClose, onSuccess }: SalarySeizureFormProps) {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [formData, setFormData] = useState<Partial<SalarySeizureCreate>>({
    type: 'saisie_arret',
    calculation_mode: 'barème_legal',
    priority: 4,
  });

  useEffect(() => {
    const fetchEmployees = async () => {
      try {
        const response = await apiClient.get('/api/employees');
        setEmployees(response.data || []);
      } catch (error) {
        console.error('Erreur chargement employés:', error);
      }
    };
    fetchEmployees();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.employee_id || !formData.start_date) {
      toast({
        title: "Erreur",
        description: "Veuillez remplir tous les champs obligatoires.",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    try {
      await createSalarySeizure(formData as SalarySeizureCreate);
      toast({
        title: "Succès",
        description: "Saisie créée avec succès.",
      });
      onSuccess();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible de créer la saisie.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle saisie sur salaire</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Employé *</Label>
              <Select
                value={formData.employee_id || ''}
                onValueChange={(value) => setFormData({ ...formData, employee_id: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner un employé" />
                </SelectTrigger>
                <SelectContent>
                  {employees.map((emp) => (
                    <SelectItem key={emp.id} value={emp.id}>
                      {emp.first_name} {emp.last_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>Type de saisie *</Label>
              <Select
                value={formData.type || ''}
                onValueChange={(value: any) => setFormData({ ...formData, type: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="saisie_arret">Saisie-arrêt</SelectItem>
                  <SelectItem value="pension_alimentaire">Pension alimentaire</SelectItem>
                  <SelectItem value="atd">Avis à tiers détenteur</SelectItem>
                  <SelectItem value="satd">Saisie administrative</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label>Nom du créancier *</Label>
            <Input
              value={formData.creditor_name || ''}
              onChange={(e) => setFormData({ ...formData, creditor_name: e.target.value })}
              placeholder="Nom du créancier"
            />
          </div>

          <div>
            <Label>IBAN du créancier</Label>
            <Input
              value={formData.creditor_iban || ''}
              onChange={(e) => setFormData({ ...formData, creditor_iban: e.target.value })}
              placeholder="FR76..."
            />
          </div>

          <div>
            <Label>Référence légale</Label>
            <Input
              value={formData.reference_legale || ''}
              onChange={(e) => setFormData({ ...formData, reference_legale: e.target.value })}
              placeholder="Référence de la décision de justice"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Mode de calcul *</Label>
              <Select
                value={formData.calculation_mode || 'barème_legal'}
                onValueChange={(value: any) => setFormData({ ...formData, calculation_mode: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fixe">Montant fixe</SelectItem>
                  <SelectItem value="pourcentage">Pourcentage</SelectItem>
                  <SelectItem value="barème_legal">Barème légal</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.calculation_mode === 'fixe' && (
              <div>
                <Label>Montant (€)</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={formData.amount || ''}
                  onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) })}
                />
              </div>
            )}

            {formData.calculation_mode === 'pourcentage' && (
              <div>
                <Label>Pourcentage (%)</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={formData.percentage || ''}
                  onChange={(e) => setFormData({ ...formData, percentage: parseFloat(e.target.value) })}
                />
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Date de début *</Label>
              <Input
                type="date"
                value={formData.start_date || ''}
                onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
              />
            </div>

            <div>
              <Label>Date de fin</Label>
              <Input
                type="date"
                value={formData.end_date || ''}
                onChange={(e) => setFormData({ ...formData, end_date: e.target.value || undefined })}
              />
            </div>
          </div>

          <div>
            <Label>Priorité</Label>
            <Select
              value={String(formData.priority || 4)}
              onValueChange={(value) => setFormData({ ...formData, priority: parseInt(value) })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">1 - Pension alimentaire</SelectItem>
                <SelectItem value="2">2 - Créances d'aliments</SelectItem>
                <SelectItem value="3">3 - Remboursement avances/prêts employeur</SelectItem>
                <SelectItem value="4">4 - Autres créances</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Notes</Label>
            <Textarea
              value={formData.notes || ''}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              placeholder="Notes internes..."
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Créer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
