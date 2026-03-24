/**
 * Dialog pour créer un nouveau processus de sortie de salarié
 */

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { useToast } from '@/hooks/use-toast';
import { createEmployeeExit, ExitType, CreateEmployeeExitRequest } from '@/api/employeeExits';
import apiClient from '@/api/apiClient';
import { Loader2 } from 'lucide-react';

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  job_title?: string;
}

interface CreateExitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export function CreateExitDialog({ open, onOpenChange, onSuccess }: CreateExitDialogProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>([]);

  // Form state
  const [employeeId, setEmployeeId] = useState<string>('');
  const [exitType, setExitType] = useState<ExitType>('demission');
  const [exitRequestDate, setExitRequestDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [lastWorkingDay, setLastWorkingDay] = useState<string>('');
  const [noticePeriodDays, setNoticePeriodDays] = useState<number>(0);
  const [isGrossMisconduct, setIsGrossMisconduct] = useState(false);
  const [noticeIndemnityType, setNoticeIndemnityType] = useState<'paid' | 'waived' | 'not_applicable'>('paid');
  const [exitReason, setExitReason] = useState<string>('');

  // Charger la liste des employés actifs
  useEffect(() => {
    if (open) {
      fetchEmployees();
    }
  }, [open]);

  const fetchEmployees = async () => {
    setLoadingEmployees(true);
    try {
      // Récupérer tous les employés actifs (sans sortie en cours)
      const response = await apiClient.get('/api/employees');
      // Filtrer côté client les employés actifs seulement
      const activeEmployees = response.data.filter((emp: any) =>
        emp.employment_status === 'actif' || !emp.employment_status
      );
      setEmployees(activeEmployees);
    } catch (error) {
      console.error('Erreur lors du chargement des employés:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger la liste des employés',
        variant: 'destructive',
      });
    } finally {
      setLoadingEmployees(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!employeeId) {
      toast({
        title: 'Erreur',
        description: 'Veuillez sélectionner un employé',
        variant: 'destructive',
      });
      return;
    }

    if (!lastWorkingDay) {
      toast({
        title: 'Erreur',
        description: 'Veuillez indiquer le dernier jour de travail',
        variant: 'destructive',
      });
      return;
    }

    // Vérifier que lastWorkingDay >= exitRequestDate
    if (new Date(lastWorkingDay) < new Date(exitRequestDate)) {
      toast({
        title: 'Erreur',
        description: 'Le dernier jour de travail doit être postérieur ou égal à la date de demande',
        variant: 'destructive',
      });
      return;
    }

    setLoading(true);

    try {
      const data: CreateEmployeeExitRequest = {
        employee_id: employeeId,
        exit_type: exitType,
        exit_request_date: exitRequestDate,
        last_working_day: lastWorkingDay,
        notice_period_days: noticePeriodDays,
        is_gross_misconduct: isGrossMisconduct,
        notice_indemnity_type: noticeIndemnityType,
        exit_reason: exitReason || undefined,
      };

      await createEmployeeExit(data);

      toast({
        title: 'Succès',
        description: 'Le processus de sortie a été créé avec succès',
      });

      // Reset form
      setEmployeeId('');
      setExitType('demission');
      setExitRequestDate(new Date().toISOString().split('T')[0]);
      setLastWorkingDay('');
      setNoticePeriodDays(0);
      setIsGrossMisconduct(false);
      setNoticeIndemnityType('paid');
      setExitReason('');

      onOpenChange(false);
      onSuccess?.();
    } catch (error: any) {
      console.error('Erreur lors de la création de la sortie:', error);
      toast({
        title: 'Erreur',
        description: error.response?.data?.detail || 'Impossible de créer le processus de sortie',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle sortie de collaborateur</DialogTitle>
          <DialogDescription>
            Créer un nouveau processus de sortie (démission, rupture conventionnelle ou licenciement)
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Sélection de l'employé */}
          <div className="space-y-2">
            <Label htmlFor="employee">Employé *</Label>
            <Select value={employeeId} onValueChange={setEmployeeId} disabled={loadingEmployees}>
              <SelectTrigger id="employee">
                <SelectValue placeholder={loadingEmployees ? "Chargement..." : "Sélectionner un employé"} />
              </SelectTrigger>
              <SelectContent>
                {employees.map((emp) => (
                  <SelectItem key={emp.id} value={emp.id}>
                    {emp.first_name} {emp.last_name} {emp.job_title ? `- ${emp.job_title}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Type de sortie */}
          <div className="space-y-2">
            <Label htmlFor="exit_type">Type de sortie *</Label>
            <Select value={exitType} onValueChange={(value) => setExitType(value as ExitType)}>
              <SelectTrigger id="exit_type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="demission">Démission</SelectItem>
                <SelectItem value="rupture_conventionnelle">Rupture conventionnelle</SelectItem>
                <SelectItem value="licenciement">Licenciement</SelectItem>
                <SelectItem value="depart_retraite">Départ à la retraite</SelectItem>
                <SelectItem value="fin_periode_essai">Fin de période d'essai</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Date de demande */}
          <div className="space-y-2">
            <Label htmlFor="exit_request_date">Date de demande/notification *</Label>
            <Input
              id="exit_request_date"
              type="date"
              value={exitRequestDate}
              onChange={(e) => setExitRequestDate(e.target.value)}
              required
            />
          </div>

          {/* Dernier jour travaillé */}
          <div className="space-y-2">
            <Label htmlFor="last_working_day">Dernier jour travaillé *</Label>
            <Input
              id="last_working_day"
              type="date"
              value={lastWorkingDay}
              onChange={(e) => setLastWorkingDay(e.target.value)}
              required
            />
          </div>

          {/* Période de préavis */}
          <div className="space-y-2">
            <Label htmlFor="notice_period_days">Durée du préavis (jours)</Label>
            <Input
              id="notice_period_days"
              type="number"
              min="0"
              value={noticePeriodDays}
              onChange={(e) => setNoticePeriodDays(parseInt(e.target.value) || 0)}
            />
            <p className="text-sm text-muted-foreground">
              Période de préavis légale ou conventionnelle (0 si dispensé)
            </p>
          </div>

          {/* Type d'indemnité de préavis */}
          <div className="space-y-2">
            <Label htmlFor="notice_indemnity_type">Indemnité de préavis</Label>
            <Select value={noticeIndemnityType} onValueChange={(value: any) => setNoticeIndemnityType(value)}>
              <SelectTrigger id="notice_indemnity_type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="paid">Payée (préavis effectué)</SelectItem>
                <SelectItem value="waived">Dispensée (préavis non effectué, payé)</SelectItem>
                <SelectItem value="not_applicable">Non applicable</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Faute grave (uniquement pour licenciement) */}
          {exitType === 'licenciement' && (
            <div className="flex items-center space-x-2">
              <Checkbox
                id="is_gross_misconduct"
                checked={isGrossMisconduct}
                onCheckedChange={(checked) => setIsGrossMisconduct(checked as boolean)}
              />
              <Label htmlFor="is_gross_misconduct" className="cursor-pointer">
                Faute grave ou lourde (pas d'indemnité)
              </Label>
            </div>
          )}

          {/* Motif de sortie */}
          <div className="space-y-2">
            <Label htmlFor="exit_reason">Motif de sortie</Label>
            <Textarea
              id="exit_reason"
              placeholder="Raison de la sortie (optionnel)"
              value={exitReason}
              onChange={(e) => setExitReason(e.target.value)}
              rows={3}
            />
          </div>

          {/* Boutons d'action */}
          <div className="flex justify-end gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Annuler
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Créer la sortie
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
