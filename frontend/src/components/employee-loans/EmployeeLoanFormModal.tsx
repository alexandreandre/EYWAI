import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import { Loader2, AlertTriangle } from 'lucide-react';
import apiClient from '@/api/apiClient';
import {
  createEmployeeLoan,
  previewAmortization,
  type AmortizationPreview,
  type EmployeeLoanCreate,
} from '@/api/employeeLoans';
import { useToast } from '@/hooks/use-toast';

interface EmployeeOption {
  id: string;
  first_name: string;
  last_name: string;
}

interface EmployeeLoanFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeId?: string;
  employeeName?: string;
  onSuccess: () => void;
}

const formatEuro = (value: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value);

export function EmployeeLoanFormModal({
  open,
  onOpenChange,
  employeeId: fixedEmployeeId,
  employeeName,
  onSuccess,
}: EmployeeLoanFormModalProps) {
  const { toast } = useToast();
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState(fixedEmployeeId ?? '');
  const [principal, setPrincipal] = useState('5000');
  const [rate, setRate] = useState('0');
  const [duration, setDuration] = useState('12');
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [repaymentDay, setRepaymentDay] = useState('1');
  const [saveAsDraft, setSaveAsDraft] = useState(false);
  const [reason, setReason] = useState('');
  const [preview, setPreview] = useState<AmortizationPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (fixedEmployeeId) setEmployeeId(fixedEmployeeId);
  }, [fixedEmployeeId]);

  useEffect(() => {
    if (!fixedEmployeeId && open) {
      void apiClient.get<EmployeeOption[]>('/api/employees').then((res) => {
        setEmployees(res.data ?? []);
      });
    }
  }, [fixedEmployeeId, open]);

  const createMutation = useMutation({
    mutationFn: (payload: EmployeeLoanCreate) => createEmployeeLoan(payload),
    onSuccess: () => {
      toast({ title: 'Prêt créé', description: 'Le prêt employeur a été enregistré.' });
      onSuccess();
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Impossible de créer le prêt.';
      toast({ title: 'Erreur', description: detail, variant: 'destructive' });
    },
  });

  const handlePreview = async () => {
    setPreviewLoading(true);
    try {
      const result = await previewAmortization({
        principal_amount: Number(principal),
        annual_interest_rate: Number(rate) / 100,
        start_date: startDate,
        duration_months: Number(duration),
      });
      setPreview(result);
    } catch {
      toast({
        title: 'Erreur',
        description: "Impossible de calculer l'échéancier.",
        variant: 'destructive',
      });
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSubmit = () => {
    if (!employeeId) {
      toast({ title: 'Erreur', description: 'Sélectionnez un salarié.', variant: 'destructive' });
      return;
    }
    createMutation.mutate({
      employee_id: employeeId,
      principal_amount: Number(principal),
      annual_interest_rate: Number(rate) / 100,
      start_date: startDate,
      duration_months: Number(duration),
      repayment_day: Number(repaymentDay),
      reason: reason || undefined,
      activate: !saveAsDraft,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouveau prêt employeur</DialogTitle>
          <DialogDescription>
            {employeeName
              ? `Prêt pour ${employeeName}`
              : "Créer un prêt d'argent de l'entreprise au salarié."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          {!fixedEmployeeId && (
            <div className="sm:col-span-2">
              <Label>Salarié *</Label>
              <Select value={employeeId} onValueChange={setEmployeeId}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner un salarié" />
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
          <div>
            <Label htmlFor="principal">Montant (€)</Label>
            <Input
              id="principal"
              type="number"
              min={1}
              value={principal}
              onChange={(e) => setPrincipal(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="rate">Taux annuel (%)</Label>
            <Input
              id="rate"
              type="number"
              min={0}
              step={0.01}
              value={rate}
              onChange={(e) => setRate(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="duration">Durée (mois)</Label>
            <Input
              id="duration"
              type="number"
              min={1}
              max={360}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="start_date">Date de début</Label>
            <Input
              id="start_date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              La première échéance correspond au mois de cette date.
            </p>
          </div>
          <div>
            <Label htmlFor="repayment_day">Jour de prélèvement</Label>
            <Input
              id="repayment_day"
              type="number"
              min={1}
              max={28}
              value={repaymentDay}
              onChange={(e) => setRepaymentDay(e.target.value)}
            />
          </div>
          <div className="sm:col-span-2 flex items-center gap-2">
            <Checkbox
              id="save_draft"
              checked={saveAsDraft}
              onCheckedChange={(checked) => setSaveAsDraft(checked === true)}
            />
            <Label htmlFor="save_draft" className="font-normal">
              Enregistrer en brouillon (activation manuelle ultérieure)
            </Label>
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="reason">Motif</Label>
            <Textarea
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
            />
          </div>
        </div>

        {Number(principal) >= 5000 && (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Montant ≥ 5 000 € : déclaration fiscale formulaire 2062 requise pour le salarié.
            </AlertDescription>
          </Alert>
        )}

        <Button type="button" variant="outline" onClick={handlePreview} disabled={previewLoading}>
          {previewLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Aperçu échéancier
        </Button>

        {preview && (
          <div className="space-y-2">
            <p className="text-sm font-medium">
              Mensualité : {formatEuro(preview.monthly_payment)}
              {preview.requires_2062_declaration && (
                <Badge variant="outline" className="ml-2">
                  2062
                </Badge>
              )}
            </p>
            <div className="max-h-48 overflow-auto rounded border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>N°</TableHead>
                    <TableHead>Période</TableHead>
                    <TableHead>Capital</TableHead>
                    <TableHead>Intérêts</TableHead>
                    <TableHead>Échéance</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.schedule.slice(0, 12).map((row) => (
                    <TableRow key={row.installment_number}>
                      <TableCell>{row.installment_number}</TableCell>
                      <TableCell>
                        {String(row.month).padStart(2, '0')}/{row.year}
                      </TableCell>
                      <TableCell>{formatEuro(row.capital_part)}</TableCell>
                      <TableCell>{formatEuro(row.interest_part)}</TableCell>
                      <TableCell>{formatEuro(row.total_due)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Créer le prêt
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
