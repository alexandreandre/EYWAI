// frontend/src/components/saisies-avances/SalaryAdvanceRequestForm.tsx

import { log } from '@/lib/logger';
import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";
import { Info, Loader2 } from "lucide-react";
import { createSalaryAdvance, getEmployeeAdvanceAvailable, getMyAdvanceAvailable } from '@/api/saisiesAvances';
import type { AdvanceAvailableAmount, SalaryAdvanceCreate } from '@/api/saisiesAvances';
import { useAuth } from '@/contexts/AuthContext';
import apiClient from '@/api/apiClient';
import { AdvanceAvailableSummary } from '@/components/saisies-avances/AdvanceAvailableSummary';
import { formatCurrency } from '@/lib/employeeDashboardUtils';

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
  /** Date de versement souhaitée par défaut (AAAA-MM-JJ) */
  defaultRequestedDate?: string;
}

export function SalaryAdvanceRequestForm({
  onClose,
  onSuccess,
  employeeId,
  hideEmployeeSelector = false,
  defaultRequestedDate,
}: SalaryAdvanceRequestFormProps) {
  const { toast } = useToast();
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [availableAmount, setAvailableAmount] = useState<number | null>(null);
  const [availableDetails, setAvailableDetails] = useState<AdvanceAvailableAmount | null>(null);
  const [formData, setFormData] = useState<Partial<SalaryAdvanceCreate>>({
    employee_id: employeeId,
    requested_date: defaultRequestedDate,
    repayment_mode: 'single',
    repayment_months: 1,
  });

  useEffect(() => {
    if (employeeId) {
      setFormData((prev) => ({ ...prev, employee_id: employeeId }));
    }
  }, [employeeId]);

  useEffect(() => {
    if (defaultRequestedDate) {
      setFormData((prev) =>
        prev.requested_date ? prev : { ...prev, requested_date: defaultRequestedDate }
      );
    }
  }, [defaultRequestedDate]);

  useEffect(() => {
    if (!hideEmployeeSelector) {
      const fetchEmployees = async () => {
        try {
          const response = await apiClient.get('/api/employees');
          setEmployees(response.data || []);
        } catch (error) {
          log.error('Erreur chargement employés:', error);
        }
      };
      void fetchEmployees();
    }
  }, [hideEmployeeSelector]);

  useEffect(() => {
    const fetchAvailable = async () => {
      if (hideEmployeeSelector) {
        try {
          const available = await getMyAdvanceAvailable();
          setAvailableDetails(available);
          setAvailableAmount(Number(available.available_amount || 0));
        } catch (error) {
          log.error('Erreur calcul montant disponible:', error);
          setAvailableAmount(null);
          setAvailableDetails(null);
        }
        return;
      }
      const targetEmployeeId = formData.employee_id || employeeId;
      if (!targetEmployeeId) {
        setAvailableAmount(null);
        setAvailableDetails(null);
        return;
      }
      try {
        const requestedDate = formData.requested_date
          ? new Date(formData.requested_date)
          : new Date();
        const available = await getEmployeeAdvanceAvailable(targetEmployeeId, {
          year: requestedDate.getFullYear(),
          month: requestedDate.getMonth() + 1,
        });
        setAvailableDetails(available);
        setAvailableAmount(Number(available.available_amount || 0));
      } catch (error) {
        log.error('Erreur calcul montant disponible:', error);
        setAvailableAmount(null);
        setAvailableDetails(null);
      }
    };
    void fetchAvailable();
  }, [formData.employee_id, formData.requested_date, employeeId, hideEmployeeSelector]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
        description: `Le montant demandé dépasse le disponible (${formatCurrency(availableAmount)}).`,
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    try {
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
    } catch (error: unknown) {
      const detail =
        error && typeof error === 'object' && 'response' in error
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur",
        description: detail || "Impossible de créer la demande.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const isEmployeeRequest = hideEmployeeSelector && user?.role === 'collaborateur';
  const dialogTitle = isEmployeeRequest ? "Nouvelle demande d'avance" : 'Nouvelle avance';

  const applyMaxAmount = () => {
    if (availableAmount !== null && availableAmount > 0) {
      setFormData((prev) => ({ ...prev, requested_amount: availableAmount }));
    }
  };

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

          {availableAmount !== null && availableDetails && (
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription>
                <AdvanceAvailableSummary data={availableDetails} variant="inline" />
              </AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Montant demandé (€) *</Label>
              <div className="flex gap-2">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  className="flex-1"
                  value={formData.requested_amount ?? ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      requested_amount: parseFloat(e.target.value) || undefined,
                    })
                  }
                  placeholder="0.00"
                />
                {isEmployeeRequest && availableAmount !== null && availableAmount > 0 && (
                  <Button type="button" variant="outline" onClick={applyMaxAmount}>
                    Maximum
                  </Button>
                )}
              </div>
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
            <Button type="submit" disabled={isLoading || availableAmount === 0}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEmployeeRequest ? 'Créer la demande' : "Créer l'avance"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
