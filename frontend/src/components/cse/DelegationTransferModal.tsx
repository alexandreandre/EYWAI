import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/components/ui/use-toast';
import {
  createDelegationTransfer,
  getElectedMembers,
  type DelegationTransferCreate,
} from '@/api/cse';
import { Loader2 } from 'lucide-react';

interface DelegationTransferModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultYear: number;
  defaultMonth: number;
}

export function DelegationTransferModal({
  open,
  onOpenChange,
  defaultYear,
  defaultMonth,
}: DelegationTransferModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: members = [] } = useQuery({
    queryKey: ['cse', 'elected-members'],
    queryFn: () => getElectedMembers(true),
    enabled: open,
  });

  const [fromId, setFromId] = useState('');
  const [toId, setToId] = useState('');
  const [hours, setHours] = useState('');
  const [notifiedAt, setNotifiedAt] = useState('');

  const mutation = useMutation({
    mutationFn: (data: DelegationTransferCreate) => createDelegationTransfer(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['cse'] });
      if (result.warnings?.length) {
        toast({
          title: 'Mutualisation enregistrée avec avertissements',
          description: result.warnings.join(' '),
        });
      } else {
        toast({ title: 'Mutualisation enregistrée' });
      }
      onOpenChange(false);
    },
    onError: (error: Error) => {
      toast({
        title: 'Erreur',
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  const titulaires = members.filter((m) =>
    ['titulaire', 'secretaire', 'tresorier'].includes(m.role)
  );

  const handleSubmit = () => {
    const h = parseFloat(hours);
    if (!fromId || !toId || !h || h <= 0) {
      toast({
        title: 'Champs requis',
        description: 'Cédant, bénéficiaire et heures sont obligatoires',
        variant: 'destructive',
      });
      return;
    }
    mutation.mutate({
      from_employee_id: fromId,
      to_employee_id: toId,
      period_year: defaultYear,
      period_month: defaultMonth + 1,
      hours: h,
      employer_notified_at: notifiedAt || null,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mutualiser des heures de délégation</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Cédant (titulaire)</Label>
            <Select value={fromId} onValueChange={setFromId}>
              <SelectTrigger>
                <SelectValue placeholder="Sélectionner" />
              </SelectTrigger>
              <SelectContent>
                {titulaires.map((m) => (
                  <SelectItem key={m.employee_id} value={m.employee_id}>
                    {m.first_name} {m.last_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Bénéficiaire</Label>
            <Select value={toId} onValueChange={setToId}>
              <SelectTrigger>
                <SelectValue placeholder="Sélectionner" />
              </SelectTrigger>
              <SelectContent>
                {members.map((m) => (
                  <SelectItem key={m.employee_id} value={m.employee_id}>
                    {m.first_name} {m.last_name} ({m.role})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Heures cédées</Label>
            <Input
              type="number"
              step="0.5"
              min="0.5"
              value={hours}
              onChange={(e) => setHours(e.target.value)}
            />
          </div>
          <div>
            <Label>Date information employeur (≥ 8 j avant utilisation)</Label>
            <Input type="date" value={notifiedAt} onChange={(e) => setNotifiedAt(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
