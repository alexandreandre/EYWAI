import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createCetAdjustment,
  createCetOpeningBalance,
  exportCetOverviewCsv,
  getCetOverview,
  getCetPending,
  getEmployeeCetMovements,
  validateCetMovement,
  type CetMovementDetail,
  type CetOverviewRow,
} from '@/api/cet';
import { useCompany } from '@/contexts/CompanyContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';

const MOVEMENT_LABELS: Record<string, string> = {
  deposit_hs: 'Épargne HS',
  deposit_cp: 'Transfert CP',
  withdraw_rest: 'Congé CET',
  adjustment: 'Ajustement',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'En attente',
  validated: 'Validé',
  rejected: 'Refusé',
  applied_payroll: 'Appliqué paie',
};

const WORKFLOW_LABELS: Record<string, string> = {
  pending: 'RH',
  pending_manager: 'Manager',
  approved_manager: 'OK manager',
  rejected_manager: 'Refus manager',
  approved_rh: 'Validé',
  rejected_rh: 'Refus RH',
};

function movementAmount(m: CetMovementDetail): string {
  if (m.movement_type === 'deposit_cp') return `${m.days} j`;
  if (m.hours) return `${m.hours} h`;
  return '—';
}

export default function SuiviCetPage() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const year = new Date().getFullYear();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('overview');
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const [openingHours, setOpeningHours] = useState('');
  const [openingDialogOpen, setOpeningDialogOpen] = useState(false);
  const [adjustmentHours, setAdjustmentHours] = useState('');
  const [adjustmentDays, setAdjustmentDays] = useState('');
  const [adjustmentNote, setAdjustmentNote] = useState('');
  const [adjustmentDialogOpen, setAdjustmentDialogOpen] = useState(false);

  const invalidateAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ['company', companyId, 'cet'] });
  };

  const { data: overview = [], isLoading } = useQuery({
    queryKey: queryKeys.cetOverview(companyId, year),
    queryFn: () => getCetOverview(year),
    enabled: Boolean(companyId),
  });

  const { data: pending = [] } = useQuery({
    queryKey: queryKeys.cetPendingQueue(companyId),
    queryFn: getCetPending,
    enabled: Boolean(companyId),
  });

  const { data: movements = [], refetch: refetchMovements } = useQuery({
    queryKey: queryKeys.cetMovements(companyId, selectedEmployeeId ?? '', year),
    queryFn: () => getEmployeeCetMovements(selectedEmployeeId!, { year, companyId }),
    enabled: Boolean(companyId && selectedEmployeeId),
  });

  const selectedRow = useMemo(
    () => overview.find((r) => r.employee_id === selectedEmployeeId),
    [overview, selectedEmployeeId],
  );

  const totalPending = useMemo(
    () => overview.reduce((acc, r) => acc + r.pending_count, 0),
    [overview],
  );

  const handleExport = async () => {
    const blob = await exportCetOverviewCsv(year);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `suivi-cet-${year}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleOpeningBalance = async () => {
    if (!selectedEmployeeId || !openingHours) return;
    try {
      await createCetOpeningBalance({
        employee_id: selectedEmployeeId,
        hours: Number(openingHours),
      });
      toast({ title: 'Solde initial enregistré' });
      setOpeningDialogOpen(false);
      setOpeningHours('');
      await invalidateAll();
      refetchMovements();
    } catch {
      toast({
        title: 'Erreur',
        description: 'Impossible d’enregistrer le solde initial.',
        variant: 'destructive',
      });
    }
  };

  const handleAdjustment = async () => {
    if (!selectedEmployeeId || !adjustmentNote.trim()) return;
    try {
      await createCetAdjustment({
        employee_id: selectedEmployeeId,
        hours: adjustmentHours ? Number(adjustmentHours) : undefined,
        days: adjustmentDays ? Number(adjustmentDays) : undefined,
        note: adjustmentNote.trim(),
      });
      toast({ title: 'Ajustement enregistré' });
      setAdjustmentDialogOpen(false);
      setAdjustmentHours('');
      setAdjustmentDays('');
      setAdjustmentNote('');
      await invalidateAll();
      refetchMovements();
    } catch {
      toast({
        title: 'Erreur',
        description: 'Impossible d’enregistrer l’ajustement.',
        variant: 'destructive',
      });
    }
  };

  const handleValidate = async (movementId: string, approved: boolean) => {
    try {
      await validateCetMovement(movementId, approved, companyId);
      toast({ title: approved ? 'Validé' : 'Refusé' });
      await invalidateAll();
    } catch {
      toast({ title: 'Erreur', variant: 'destructive' });
    }
  };

  const openHistory = (row: CetOverviewRow) => {
    setSelectedEmployeeId(row.employee_id);
    setActiveTab('history');
  };

  return (
    <div className="container max-w-6xl py-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Suivi CET</h1>
          <p className="text-sm text-muted-foreground">
            Compte épargne-temps — année {year}
            {totalPending > 0 ? (
              <Badge variant="secondary" className="ml-2">
                {totalPending} en attente
              </Badge>
            ) : null}
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void handleExport()}>
          Export CSV
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Vue d&apos;ensemble</TabsTrigger>
          <TabsTrigger value="pending">File validation ({pending.length})</TabsTrigger>
          <TabsTrigger value="history" disabled={!selectedEmployeeId}>
            Historique
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Effectif</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <p className="text-sm text-muted-foreground">Chargement…</p>
              ) : overview.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  CET non activé ou aucun salarié éligible.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Salarié</TableHead>
                      <TableHead>Solde (j)</TableHead>
                      <TableHead>CP transférés</TableHead>
                      <TableHead>Quota restant</TableHead>
                      <TableHead>En attente</TableHead>
                      <TableHead>Manager</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {overview.map((row) => (
                      <TableRow key={row.employee_id}>
                        <TableCell>
                          {row.last_name} {row.first_name}
                        </TableCell>
                        <TableCell className="font-medium">
                          {row.balance_days.toFixed(1)}
                        </TableCell>
                        <TableCell>{row.cp_transfer_used_days.toFixed(1)}</TableCell>
                        <TableCell>
                          {row.cp_transfer_remaining_days != null
                            ? row.cp_transfer_remaining_days.toFixed(1)
                            : '—'}
                        </TableCell>
                        <TableCell>
                          {row.pending_count > 0 ? (
                            <Badge variant="outline">{row.pending_count}</Badge>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell>
                          {!row.has_manager ? (
                            <span className="text-amber-700 text-xs">Sans manager</span>
                          ) : (
                            'OK'
                          )}
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" size="sm" onClick={() => openHistory(row)}>
                            Historique
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pending">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Demandes en attente RH</CardTitle>
            </CardHeader>
            <CardContent>
              {pending.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune demande en attente.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Montant</TableHead>
                      <TableHead>Workflow</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pending.map((m) => (
                      <TableRow key={m.id}>
                        <TableCell>{MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}</TableCell>
                        <TableCell>{movementAmount(m)}</TableCell>
                        <TableCell>{WORKFLOW_LABELS[m.workflow_step] ?? m.workflow_step}</TableCell>
                        <TableCell>
                          {m.created_at
                            ? new Date(m.created_at).toLocaleDateString('fr-FR')
                            : '—'}
                        </TableCell>
                        <TableCell className="space-x-2">
                          <Button size="sm" onClick={() => void handleValidate(m.id, true)}>
                            Valider
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => void handleValidate(m.id, false)}
                          >
                            Refuser
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">
                {selectedRow
                  ? `${selectedRow.first_name} ${selectedRow.last_name}`
                  : 'Historique'}
              </CardTitle>
              {selectedEmployeeId ? (
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => setOpeningDialogOpen(true)}>
                    Solde initial
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setAdjustmentDialogOpen(true)}>
                    Ajustement RH
                  </Button>
                </div>
              ) : null}
            </CardHeader>
            <CardContent>
              {!selectedEmployeeId ? (
                <p className="text-sm text-muted-foreground">
                  Sélectionnez un salarié dans la vue d&apos;ensemble.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Montant</TableHead>
                      <TableHead>Solde (j)</TableHead>
                      <TableHead>Statut</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {[...movements].reverse().map((m) => (
                      <TableRow key={m.id}>
                        <TableCell>
                          {m.created_at
                            ? new Date(m.created_at).toLocaleDateString('fr-FR')
                            : '—'}
                        </TableCell>
                        <TableCell>{MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}</TableCell>
                        <TableCell>{movementAmount(m)}</TableCell>
                        <TableCell>
                          {m.balance_after_days != null
                            ? m.balance_after_days.toFixed(1)
                            : '—'}
                        </TableCell>
                        <TableCell>{STATUS_LABELS[m.status] ?? m.status}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={openingDialogOpen} onOpenChange={setOpeningDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Solde initial CET (reprise)</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label>Heures</Label>
            <Input
              type="number"
              step={0.5}
              min={0}
              value={openingHours}
              onChange={(e) => setOpeningHours(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button onClick={() => void handleOpeningBalance()}>Enregistrer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={adjustmentDialogOpen} onOpenChange={setAdjustmentDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ajustement manuel CET</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Heures (optionnel)</Label>
              <Input
                type="number"
                step={0.5}
                value={adjustmentHours}
                onChange={(e) => setAdjustmentHours(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Jours (optionnel)</Label>
              <Input
                type="number"
                step={0.5}
                value={adjustmentDays}
                onChange={(e) => setAdjustmentDays(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Motif</Label>
              <Input
                value={adjustmentNote}
                onChange={(e) => setAdjustmentNote(e.target.value)}
                placeholder="Motif de l'ajustement"
              />
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => void handleAdjustment()}>Enregistrer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
