// frontend/src/components/saisies-avances/SalaryAdvanceRequestForm.tsx

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { Loader2 } from "lucide-react";
import { createSalaryAdvance, getMyAdvanceAvailable } from '@/api/saisiesAvances';
import type { SalaryAdvanceCreate } from '@/api/saisiesAvances';
import { useAuth } from '@/contexts/AuthContext';
import apiClient from '@/api/apiClient';

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
}

interface SalaryAdvanceRequestFormProps {
  onClose: () => void;
  onSuccess: () => void;
  /** ID de l'employé pré-sélectionné (pour les demandes d'employés) */
  employeeId?: string;
  /** Si true, masque le sélecteur d'employé (pour les demandes d'employés) */
  hideEmployeeSelector?: boolean;
}

export function SalaryAdvanceRequestForm({ 
  onClose, 
  onSuccess, 
  employeeId,
  hideEmployeeSelector = false 
}: SalaryAdvanceRequestFormProps) {
  const { toast } = useToast();
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [availableAmount, setAvailableAmount] = useState<number | null>(null);
  const [formData, setFormData] = useState<Partial<SalaryAdvanceCreate>>({
    employee_id: employeeId,
    repayment_mode: 'single', // Valeur par défaut, non affichée dans l'interface
    repayment_months: 1, // Valeur par défaut, non affichée dans l'interface
  });

  // Mettre à jour employee_id si employeeId change
  useEffect(() => {
    if (employeeId) {
      setFormData(prev => ({ ...prev, employee_id: employeeId }));
    }
  }, [employeeId]);

  // Charger la liste des employés seulement si le sélecteur est visible (RH)
  useEffect(() => {
    if (!hideEmployeeSelector) {
      const fetchEmployees = async () => {
        try {
          const response = await apiClient.get('/api/employees');
          setEmployees(response.data || []);
        } catch (error) {
          console.error('Erreur chargement employés:', error);
        }
      };
      fetchEmployees();
    }
  }, [hideEmployeeSelector]);

  // Charger le montant disponible quand employee_id change
  useEffect(() => {
    const fetchAvailable = async () => {
      const targetEmployeeId = formData.employee_id || employeeId;
      if (targetEmployeeId) {
        try {
          // Si c'est l'employé connecté, utiliser getMyAdvanceAvailable
          // Sinon, il faudrait créer un endpoint pour calculer le disponible pour un employé spécifique
          if (targetEmployeeId === user?.id) {
            const available = await getMyAdvanceAvailable();
            // Convertir en nombre car Pydantic sérialise les Decimal en chaînes
            setAvailableAmount(Number(available.available_amount || 0));
          } else {
            // Pour les RH qui créent une demande pour un autre employé
            // On ne peut pas calculer le disponible facilement ici
            // TODO: Créer un endpoint pour calculer le disponible pour un employé spécifique
            setAvailableAmount(null);
          }
        } catch (error) {
          console.error('Erreur calcul montant disponible:', error);
          setAvailableAmount(null);
        }
      } else {
        setAvailableAmount(null);
      }
    };
    fetchAvailable();
  }, [formData.employee_id, employeeId, user?.id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Utiliser employeeId si fourni, sinon formData.employee_id
    const finalEmployeeId = employeeId || formData.employee_id;
    
    if (!finalEmployeeId || !formData.requested_amount || !formData.requested_date) {
      toast({
        title: "Erreur",
        description: "Veuillez remplir tous les champs obligatoires.",
        variant: "destructive",
      });
      return;
    }

    if (availableAmount !== null && formData.requested_amount > Number(availableAmount)) {
      toast({
        title: "Erreur",
        description: `Le montant demandé dépasse le disponible (${Number(availableAmount).toFixed(2)}€).`,
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    try {
      // S'assurer que employee_id est bien défini dans les données envoyées
      const submitData: SalaryAdvanceCreate = {
        ...formData,
        employee_id: finalEmployeeId,
      } as SalaryAdvanceCreate;
      
      await createSalaryAdvance(submitData);
      toast({
        title: "Succès",
        description: "Demande d'avance créée avec succès.",
      });
      onSuccess();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible de créer la demande.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Déterminer si c'est une demande (employé) ou une création (RH)
  const isEmployeeRequest = hideEmployeeSelector && user?.role === 'collaborateur';
  const dialogTitle = isEmployeeRequest ? 'Nouvelle demande d\'avance' : 'Nouvelle avance';

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {!hideEmployeeSelector && (
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
          )}

          {availableAmount !== null && (
            <div className="p-3 bg-blue-50 rounded-md">
              <p className="text-sm text-blue-900">
                <strong>Montant disponible :</strong> {Number(availableAmount).toFixed(2)}€
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Montant demandé (€) *</Label>
              <Input
                type="number"
                step="0.01"
                value={formData.requested_amount || ''}
                onChange={(e) => setFormData({ ...formData, requested_amount: parseFloat(e.target.value) })}
                placeholder="0.00"
              />
            </div>

            <div>
              <Label>Date de versement souhaitée *</Label>
              <Input
                type="date"
                value={formData.requested_date || ''}
                onChange={(e) => setFormData({ ...formData, requested_date: e.target.value })}
              />
            </div>
          </div>

          <div>
            <Label>Motif (optionnel)</Label>
            <Textarea
              value={formData.request_comment || ''}
              onChange={(e) => setFormData({ ...formData, request_comment: e.target.value })}
              placeholder="Motif de la demande..."
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {isEmployeeRequest ? 'Créer la demande' : 'Créer l\'avance'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
