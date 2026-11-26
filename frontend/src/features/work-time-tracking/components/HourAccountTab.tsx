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
import {
  detailMouvement,
  libelleStatutMouvement,
} from '@/features/work-time-tracking/lib/hourAccountLabels';
import { workTimeHubPath } from '@/features/work-time-tracking/lib/workTimeTabRouting';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { ArrowRight } from 'lucide-react';

const MOVEMENT_LABELS: Record<string, string> = {
  credit_hs: 'Heures sup au compteur',
  debit_recovery: 'Récupération',
  debit_payout: 'Paiement du solde',
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

  const {
    data: movements = [],
    isLoading: chargementMouvements,
    refetch: refetchMovements,
  } = useQuery({
    queryKey: queryKeys.modulationMovements(companyId, selectedEmployeeId ?? '', year),
    queryFn: () => getEmployeeModulationMovements(selectedEmployeeId!, year),
    enabled: Boolean(companyId && selectedEmployeeId),
  });

  // Sans annualisation, Théorique, Réalisé et Écart restent à 0 : des colonnes
  // vides qui faisaient croire à un compteur faux (retour d'Elsa du 16/11).
  const avecAnnualisation = useMemo(
    () =>
      overview.some(
        (r) =>
          !r.estimated &&
          (Math.abs(r.theoretical_hours) > 0.004 ||
            Math.abs(r.actual_hours) > 0.004 ||
            Math.abs(r.balance_hours) > 0.004),
      ),
    [overview],
  );

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
        Le compteur de récupération de chaque salarié en {year} : les heures sup mises au compteur,
        moins les récupérations prises. Le repos compensateur obligatoire (au-delà du contingent) est
        dans l&apos;onglet « Plafond annuel ».
      </p>
      <p className="text-sm text-muted-foreground">
        Une heure sup à 25 % donne 1 h 15 au compteur, à 50 % 1 h 30 : quand le salarié récupère,
        son salaire est maintenu sur ces heures. Il reçoit donc exactement ce que l&apos;heure sup
        payée lui aurait rapporté (1 h à 25 % payée = 1 h 15 de salaire). Pour poser une
        récupération : calendrier du salarié, « Poser une récupération ».
      </p>
      <p className="text-sm text-muted-foreground" data-testid="compteur-quand">
        Le compteur se remplit au calcul du bulletin : les heures sup de la période de paie y
        passent quand le bulletin du mois est calculé, pas au pointage. Les heures sup payées avant
        Martine (ancien logiciel) n&apos;y sont pas ; un reste d&apos;avant se saisit en « Solde
        initial ».
      </p>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Vue d&apos;ensemble</TabsTrigger>
          <TabsTrigger value="history" disabled={!selectedEmployeeId}>
            Détail du compteur
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
                      {avecAnnualisation && (
                        <>
                          <TableHead>Théorique (h)</TableHead>
                          <TableHead>Réalisé (h)</TableHead>
                          <TableHead>Écart annuel (h)</TableHead>
                        </>
                      )}
                      <TableHead>Solde du compteur (h)</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {overview.map((row) => (
                      <TableRow key={row.employee_id}>
                        <TableCell>
                          {row.first_name} {row.last_name}
                        </TableCell>
                        {avecAnnualisation && (
                        <>
                        <TableCell>
                          {row.estimated ? (
                            <span title="Estimation (durée hebdomadaire × 52) : aucun compteur n'existe encore pour ce salarié.">
                              ≈ {row.theoretical_hours.toFixed(2)} (estimé)
                            </span>
                          ) : (
                            row.theoretical_hours.toFixed(2)
                          )}
                        </TableCell>
                        <TableCell>{row.estimated ? '—' : row.actual_hours.toFixed(2)}</TableCell>
                        <TableCell
                          className={
                            row.balance_hours < 0
                              ? 'text-destructive font-medium'
                              : row.balance_hours > 0
                                ? 'text-amber-700 font-medium'
                                : ''
                          }
                        >
                          {row.estimated ? (
                            '—'
                          ) : (
                            <>
                              {row.balance_hours > 0 ? '+' : ''}
                              {row.balance_hours.toFixed(2)}
                            </>
                          )}
                        </TableCell>
                        </>
                        )}
                        <TableCell className="font-medium">
                          {row.estimated ? (
                            <span
                              className="font-normal text-muted-foreground"
                              title="Aucun mouvement cette année : rien n'est encore passé au compteur par un bulletin calculé."
                            >
                              0.00 (aucun mouvement)
                            </span>
                          ) : (
                            row.account_balance_hours.toFixed(2)
                          )}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => selectEmployee(row.employee_id)}
                          >
                            Détail du compteur
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
                  : 'Détail du compteur'}
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
                        <TableHead>Mois</TableHead>
                        <TableHead>Mouvement</TableHead>
                        <TableHead>Heures de repos</TableHead>
                        <TableHead>Détail</TableHead>
                        <TableHead>Statut</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {!chargementMouvements && movements.length === 0 && (
                        <TableRow>
                          <TableCell
                            colSpan={5}
                            className="text-sm text-muted-foreground"
                            data-testid="compteur-vide"
                          >
                            Aucun mouvement en {year}. Les heures sup de ce salarié passeront au
                            compteur au calcul de son prochain bulletin.
                          </TableCell>
                        </TableRow>
                      )}
                      {movements.map((m) => (
                        <TableRow key={m.id}>
                          <TableCell>
                            {m.month
                              ? `${String(m.month).padStart(2, '0')}/${m.year}`
                              : m.created_at
                                ? new Date(m.created_at).toLocaleDateString('fr-FR')
                                : '—'}
                          </TableCell>
                          <TableCell>
                            {MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}
                          </TableCell>
                          <TableCell>{m.hours.toFixed(2)}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {detailMouvement(m)}
                          </TableCell>
                          <TableCell>{libelleStatutMouvement(m.status)}</TableCell>
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
          <p className="text-sm text-muted-foreground">
            Les heures de repos que le salarié avait déjà au compteur avant Martine (relevé de
            l&apos;ancien logiciel ou du tableau de suivi).
          </p>
          <div className="space-y-2">
            <Label>Heures de repos</Label>
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
