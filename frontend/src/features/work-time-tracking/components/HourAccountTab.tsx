import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createModulationAdjustment,
  createOpeningBalance,
  getEmployeeModulationMovements,
  getModulationOverview,
} from '@/api/modulation';
import { useCompany } from '@/contexts/CompanyContext';
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
import { workTimeHubPath } from '@/features/work-time-tracking/lib/workTimeTabRouting';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { ArrowRight } from 'lucide-react';

const MOVEMENT_LABELS: Record<string, string> = {
  credit_hs: 'Crédit HS (paie)',
  debit_recovery: 'Récupération',
  debit_payout: 'Liquidation',
  adjustment: 'Ajustement RH',
  opening_balance: 'Solde initial',
};

export interface HourAccountTabProps {
  initialEmployeeId?: string | null;
  onEmployeeSelect?: (employeeId: string | null) => void;
}

export function HourAccountTab({
  initialEmployeeId = null,
  onEmployeeSelect,
}: HourAccountTabProps) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const year = new Date().getFullYear();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState(
    initialEmployeeId ? 'history' : 'overview',
  );
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(
    initialEmployeeId,
  );
  const [openingHours, setOpeningHours] = useState('');
  const [openingDialogOpen, setOpeningDialogOpen] = useState(false);
  const [adjustmentHours, setAdjustmentHours] = useState('');
  const [adjustmentNote, setAdjustmentNote] = useState('');
  const [adjustmentDialogOpen, setAdjustmentDialogOpen] = useState(false);

  useEffect(() => {
    setSelectedEmployeeId(initialEmployeeId);
    if (initialEmployeeId) {
      setActiveTab('history');
    }
  }, [initialEmployeeId]);

  const { data: overview = [], isLoading } = useQuery({
    queryKey: queryKeys.modulationOverview(companyId, year),
    queryFn: () => getModulationOverview(year),
    enabled: Boolean(companyId),
  });

  const { data: movements = [], refetch: refetchMovements } = useQuery({
    queryKey: queryKeys.modulationMovements(companyId, selectedEmployeeId ?? '', year),
    queryFn: () => getEmployeeModulationMovements(selectedEmployeeId!, year),
    enabled: Boolean(companyId && selectedEmployeeId),
  });

  const selectedRow = useMemo(
    () => overview.find((r) => r.employee_id === selectedEmployeeId),
    [overview, selectedEmployeeId],
  );

  const selectEmployee = (employeeId: string) => {
    setSelectedEmployeeId(employeeId);
    onEmployeeSelect?.(employeeId);
    setActiveTab('history');
  };

  const handleOpeningBalance = async () => {
    if (!selectedEmployeeId || !openingHours) return;
    try {
      await createOpeningBalance(selectedEmployeeId, Number(openingHours));
      toast({ title: 'Solde initial enregistré' });
      setOpeningDialogOpen(false);
      setOpeningHours('');
      await queryClient.invalidateQueries({
        queryKey: queryKeys.modulationOverview(companyId, year),
      });
      refetchMovements();
    } catch {
      toast({
        title: 'Erreur',
        description: 'Impossible d\'enregistrer le solde initial.',
        variant: 'destructive',
      });
    }
  };

  const handleAdjustment = async () => {
    if (!selectedEmployeeId || adjustmentHours === '') return;
    try {
      await createModulationAdjustment(
        selectedEmployeeId,
        Number(adjustmentHours),
        adjustmentNote || undefined,
      );
      toast({ title: 'Ajustement enregistré' });
      setAdjustmentDialogOpen(false);
      setAdjustmentHours('');
      setAdjustmentNote('');
      await queryClient.invalidateQueries({
        queryKey: queryKeys.modulationOverview(companyId, year),
      });
      refetchMovements();
    } catch {
      toast({
        title: 'Erreur',
        description: 'Impossible d\'enregistrer l\'ajustement.',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Annualisation et compte d&apos;heures par salarié pour l&apos;année {year}.
      </p>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Vue d&apos;ensemble</TabsTrigger>
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
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Salarié</TableHead>
                      <TableHead>Théorique (h)</TableHead>
                      <TableHead>Réalisé (h)</TableHead>
                      <TableHead>Écart annuel (h)</TableHead>
                      <TableHead>Solde compte (h)</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {overview.map((row) => (
                      <TableRow key={row.employee_id}>
                        <TableCell>
                          {row.first_name} {row.last_name}
                        </TableCell>
                        <TableCell>{row.theoretical_hours.toFixed(2)}</TableCell>
                        <TableCell>{row.actual_hours.toFixed(2)}</TableCell>
                        <TableCell
                          className={
                            row.balance_hours < 0
                              ? 'text-destructive font-medium'
                              : row.balance_hours > 0
                                ? 'text-amber-700 font-medium'
                                : ''
                          }
                        >
                          {row.balance_hours > 0 ? '+' : ''}
                          {row.balance_hours.toFixed(2)}
                        </TableCell>
                        <TableCell className="font-medium">
                          {row.account_balance_hours.toFixed(2)}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => selectEmployee(row.employee_id)}
                          >
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

        <TabsContent value="history">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">
                {selectedRow
                  ? `${selectedRow.first_name} ${selectedRow.last_name}`
                  : 'Historique'}
              </CardTitle>
              {selectedEmployeeId && (
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => setOpeningDialogOpen(true)}>
                    Solde initial
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setAdjustmentDialogOpen(true)}>
                    Ajustement RH
                  </Button>
                </div>
              )}
            </CardHeader>
            <CardContent>
              {!selectedEmployeeId ? (
                <p className="text-sm text-muted-foreground">
                  Sélectionnez un salarié dans la vue d&apos;ensemble.
                </p>
              ) : (
                <>
                  <Button variant="outline" size="sm" className="mb-4" asChild>
                    <Link
                      to={workTimeHubPath({
                        tab: 'contingent',
                        employee: selectedEmployeeId,
                      })}
                    >
                      Voir le plafond annuel
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Heures</TableHead>
                        <TableHead>Statut</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {movements.map((m) => (
                        <TableRow key={m.id}>
                          <TableCell>
                            {m.created_at
                              ? new Date(m.created_at).toLocaleDateString('fr-FR')
                              : '—'}
                          </TableCell>
                          <TableCell>
                            {MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}
                          </TableCell>
                          <TableCell>{m.hours.toFixed(2)}</TableCell>
                          <TableCell>{m.status}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={openingDialogOpen} onOpenChange={setOpeningDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Solde initial (reprise)</DialogTitle>
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
            <Button onClick={handleOpeningBalance}>Enregistrer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={adjustmentDialogOpen} onOpenChange={setAdjustmentDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ajustement manuel du compte</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Valeur positive = crédit, négative = débit (correction RH).
          </p>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Heures (+ / −)</Label>
              <Input
                type="number"
                step={0.5}
                value={adjustmentHours}
                onChange={(e) => setAdjustmentHours(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Note (optionnel)</Label>
              <Input
                value={adjustmentNote}
                onChange={(e) => setAdjustmentNote(e.target.value)}
                placeholder="Motif de l'ajustement"
              />
            </div>
          </div>
          <DialogFooter>
            <Button onClick={handleAdjustment}>Enregistrer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
