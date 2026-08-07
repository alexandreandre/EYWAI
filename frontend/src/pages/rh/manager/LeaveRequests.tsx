import { RhPageHeader } from '@/components/layout';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getPendingManagerApproval,
  managerApproveAbsence,
  type AbsencePendingManagerItem,
} from '@/api/absences';
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
import { useToast } from '@/components/ui/use-toast';
import { useCompany } from '@/contexts/CompanyContext';

const TYPE_LABELS: Record<AbsencePendingManagerItem['type'], string> = {
  conge_paye: 'Congé payé',
  rtt: 'RTT',
  jtc: 'JTC',
  sans_solde: 'Sans solde',
  repos_compensateur: 'Repos compensateur',
  evenement_familial: 'Événement familial',
  arret_maladie: 'Arrêt maladie',
  arret_at: 'Accident du travail',
  arret_paternite: 'Congé paternité',
  arret_maternite: 'Congé maternité',
  arret_maladie_pro: 'Maladie professionnelle',
};

function formatDates(days: string[]): string {
  if (!days?.length) return '—';
  const sorted = [...days].sort();
  if (sorted.length === 1) return sorted[0];
  return `${sorted[0]} → ${sorted[sorted.length - 1]} (${sorted.length} j.)`;
}

export default function LeaveRequests() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';

  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<AbsencePendingManagerItem | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['absences', 'pending-manager-approval', companyId],
    queryFn: async () => {
      const res = await getPendingManagerApproval(companyId);
      return res.data;
    },
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
    }) => {
      const res = await managerApproveAbsence(id, companyId, {
        approved,
        rejection_reason: reason ?? null,
      });
      return res.data;
    },
    onSuccess: (_, variables) => {
      toast({
        title: variables.approved ? 'Demande approuvée' : 'Demande refusée',
        description: variables.approved
          ? 'La demande est transmise à la RH pour validation finale.'
          : 'Le collaborateur verra le refus dans l’historique de ses demandes.',
      });
      void queryClient.invalidateQueries({
        queryKey: ['absences', 'pending-manager-approval', companyId],
      });
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

  const openReject = (row: AbsencePendingManagerItem) => {
    setRejectTarget(row);
    setRejectReason('');
    setRejectOpen(true);
  };

  const confirmReject = () => {
    if (!rejectTarget) return;
    const r = rejectReason.trim();
    if (!r) {
      toast({ title: 'Motif requis', description: 'Indiquez un motif de refus.', variant: 'destructive' });
      return;
    }
    mutation.mutate(
      { id: rejectTarget.id, approved: false, reason: r },
      {
        onSettled: () => {
          setRejectOpen(false);
          setRejectTarget(null);
        },
      },
    );
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <RhPageHeader
        title="Demandes d'absence à valider"
        description="En attente de ma validation (manager), avant transmission à la RH."
      />

      <section className="rounded-lg border bg-card p-4 shadow-sm">
        <h2 className="text-lg font-medium mb-4">En attente de ma validation</h2>

        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}

        {isError && (
          <p className="text-sm text-destructive">Impossible de charger les demandes.</p>
        )}

        {!isLoading && !isError && (!data || data.length === 0) && (
          <p className="text-sm text-muted-foreground py-8 text-center">Aucune demande en attente</p>
        )}

        {!isLoading && data && data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Salarié</TableHead>
                <TableHead>Type d&apos;absence</TableHead>
                <TableHead>Dates</TableHead>
                <TableHead>Durée</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-medium">
                    {row.employee?.first_name} {row.employee?.last_name}
                  </TableCell>
                  <TableCell>{TYPE_LABELS[row.type] ?? row.type}</TableCell>
                  <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                    {formatDates(row.selected_days)}
                  </TableCell>
                  <TableCell>{row.selected_days?.length ?? 0} j.</TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      disabled={mutation.isPending}
                      onClick={() => mutation.mutate({ id: row.id, approved: true })}
                    >
                      Approuver
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={mutation.isPending}
                      onClick={() => openReject(row)}
                    >
                      Refuser
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Motif du refus</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="reject-reason">Motif (obligatoire)</Label>
            <Textarea
              id="reject-reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Expliquez la raison du refus…"
              rows={4}
            />
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setRejectOpen(false)}>
              Annuler
            </Button>
            <Button type="button" variant="destructive" onClick={confirmReject} disabled={mutation.isPending}>
              Confirmer le refus
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
