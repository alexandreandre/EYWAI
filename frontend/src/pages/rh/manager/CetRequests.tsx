import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getPendingManagerCetApproval,
  managerApproveCetMovement,
  type CetPendingManagerItem,
} from '@/api/cet';
import { RhPageHeader } from '@/components/layout';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { useCompany } from '@/contexts/CompanyContext';
import { queryKeys } from '@/lib/queryKeys';

const MOVEMENT_LABELS: Record<string, string> = {
  deposit_hs: 'Épargne HS',
  deposit_cp: 'Transfert CP',
  withdraw_rest: 'Congé CET',
};

function movementAmount(m: CetPendingManagerItem): string {
  if (m.movement_type === 'deposit_cp') return `${m.days} j CP`;
  return `${m.hours} h`;
}

export default function CetRequests() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';

  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<CetPendingManagerItem | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const { data = [], isLoading, isError } = useQuery({
    queryKey: queryKeys.cetPendingManager(companyId),
    queryFn: () => getPendingManagerCetApproval(companyId),
    enabled: Boolean(companyId),
  });

  const mutation = useMutation({
    mutationFn: async ({
      id,
      approved,
      reason,
    }: {
      id: string;
      approved: boolean;
      reason?: string | null;
    }) =>
      managerApproveCetMovement(id, approved, companyId, reason ?? undefined),
    onSuccess: (_, variables) => {
      toast({
        title: variables.approved ? 'Demande approuvée' : 'Demande refusée',
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.cetPendingManager(companyId),
      });
      void queryClient.invalidateQueries({ queryKey: ['company', companyId, 'cet'] });
    },
    onError: (err: unknown) => {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? String((err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail ?? '')
          : '';
      toast({
        title: 'Erreur',
        description: msg || 'Action impossible.',
        variant: 'destructive',
      });
    },
  });

  const confirmReject = () => {
    if (!rejectTarget) return;
    const r = rejectReason.trim();
    if (!r) {
      toast({ title: 'Motif requis', variant: 'destructive' });
      return;
    }
    mutation.mutate({ id: rejectTarget.id, approved: false, reason: r });
    setRejectOpen(false);
  };

  return (
    <div className="container max-w-4xl py-6 space-y-4">
      <RhPageHeader
        title="CET à valider"
        description="Demandes de compte épargne-temps en attente de votre validation."
      />

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : isError ? (
        <p className="text-destructive text-sm">Impossible de charger les demandes.</p>
      ) : data.length === 0 ? (
        <p className="text-muted-foreground text-sm">Aucune demande CET en attente.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Salarié</TableHead>
              <TableHead>Demande</TableHead>
              <TableHead>Date</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  {row.employee?.first_name} {row.employee?.last_name}
                </TableCell>
                <TableCell>
                  {MOVEMENT_LABELS[row.movement_type] ?? row.movement_type} —{' '}
                  {movementAmount(row)}
                </TableCell>
                <TableCell>
                  {row.created_at
                    ? new Date(row.created_at).toLocaleDateString('fr-FR')
                    : '—'}
                </TableCell>
                <TableCell className="space-x-2 text-right">
                  <Button
                    size="sm"
                    disabled={mutation.isPending}
                    onClick={() => mutation.mutate({ id: row.id, approved: true })}
                  >
                    Approuver
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={mutation.isPending}
                    onClick={() => {
                      setRejectTarget(row);
                      setRejectReason('');
                      setRejectOpen(true);
                    }}
                  >
                    Refuser
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Motif de refus</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="cet-reject-reason">Motif</Label>
            <Textarea
              id="cet-reject-reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="destructive" onClick={confirmReject}>
              Confirmer le refus
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
