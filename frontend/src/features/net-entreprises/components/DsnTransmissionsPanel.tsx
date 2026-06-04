import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getNetEntreprisesTransmissions,
  markTransmissionTransmitted,
  TRANSMISSION_MODE_LABELS,
  type DSNTransmission,
} from '@/api/netEntreprises';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { History, Send } from 'lucide-react';
import TransmissionStatusBadge from './TransmissionStatusBadge';

function formatDate(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

export function DsnTransmissionsPanel() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [markTarget, setMarkTarget] = useState<DSNTransmission | null>(null);
  const [ref, setRef] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['net-entreprises-transmissions'],
    queryFn: () => getNetEntreprisesTransmissions(),
  });

  const markMutation = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) =>
      markTransmissionTransmitted(id, value || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['net-entreprises-transmissions'] });
      setMarkTarget(null);
      setRef('');
      toast({ title: 'Transmission mise à jour', description: 'Dépôt confirmé.' });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Mise à jour impossible.',
        variant: 'destructive',
      });
    },
  });

  const transmissions = data?.transmissions ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <History className="h-5 w-5 text-muted-foreground" />
          Suivi des télétransmissions DSN
        </CardTitle>
        <CardDescription>
          Statut de chaque DSN générée. En mode manuel, confirmez le dépôt pour
          enregistrer le numéro d'accusé Net-entreprises.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : isError ? (
          <p className="text-sm text-destructive">Chargement du suivi impossible.</p>
        ) : transmissions.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Aucune DSN générée pour le moment.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Période</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Accusé</TableHead>
                  <TableHead>Générée le</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transmissions.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium">{t.period}</TableCell>
                    <TableCell>
                      <TransmissionStatusBadge status={t.status} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {TRANSMISSION_MODE_LABELS[t.mode] ?? t.mode}
                    </TableCell>
                    <TableCell className="text-sm">
                      {t.net_entreprises_ref || '—'}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(t.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {(t.status === 'manual' || t.status === 'generated') && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setMarkTarget(t);
                            setRef(t.net_entreprises_ref ?? '');
                          }}
                        >
                          <Send className="mr-1 h-3.5 w-3.5" />
                          Marquer déposée
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>

      <Dialog open={!!markTarget} onOpenChange={(open) => !open && setMarkTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmer le dépôt manuel</DialogTitle>
            <DialogDescription>
              Indiquez le numéro de dépôt / accusé reçu sur net-entreprises.fr pour la
              période {markTarget?.period}.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Input
              value={ref}
              onChange={(e) => setRef(e.target.value)}
              placeholder="Numéro d'accusé (optionnel)"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMarkTarget(null)}>
              Annuler
            </Button>
            <Button
              onClick={() =>
                markTarget && markMutation.mutate({ id: markTarget.id, value: ref.trim() })
              }
              disabled={markMutation.isPending}
            >
              {markMutation.isPending ? 'Enregistrement…' : 'Confirmer le dépôt'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export default DsnTransmissionsPanel;
