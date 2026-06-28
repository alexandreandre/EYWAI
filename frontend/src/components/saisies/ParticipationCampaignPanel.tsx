import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Download, FileText, Megaphone, RefreshCw, Send } from 'lucide-react';

import {
  bulletinStatusLabel,
  choiceLabel,
  closeCampaignDefaults,
  createCampaign,
  generateCampaignPayrollLines,
  generateRegularisationPayslip,
  listCampaignBulletins,
  listCampaigns,
  publishCampaign,
  remindCampaign,
  type CampaignAdvanceInput,
  type ParticipationBulletin,
  type ParticipationCampaign,
} from '@/api/participation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { useToast } from '@/hooks/use-toast';
import { downloadBlob } from '@/lib/downloadBlob';

const MONTH_OPTIONS = [
  { value: 1, label: 'Janvier' },
  { value: 2, label: 'Février' },
  { value: 3, label: 'Mars' },
  { value: 4, label: 'Avril' },
  { value: 5, label: 'Mai' },
  { value: 6, label: 'Juin' },
  { value: 7, label: 'Juillet' },
  { value: 8, label: 'Août' },
  { value: 9, label: 'Septembre' },
  { value: 10, label: 'Octobre' },
  { value: 11, label: 'Novembre' },
  { value: 12, label: 'Décembre' },
];

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
  }).format(amount);
}

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('fr-FR');
}

export interface ParticipationCampaignPanelProps {
  year: number;
  results: Array<{
    employeeId: string;
    employeeName: string;
    participationAmount: number;
    interessementAmount: number;
  }>;
  simulationId?: string;
  defaultPayrollYear?: number;
  defaultPayrollMonth?: number;
}

export function ParticipationCampaignPanel({
  year,
  results,
  simulationId,
  defaultPayrollYear,
  defaultPayrollMonth,
}: ParticipationCampaignPanelProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [activeCampaignId, setActiveCampaignId] = useState<string | null>(null);
  const [payrollYear, setPayrollYear] = useState(
    defaultPayrollYear ?? year + 1,
  );
  const [payrollMonth, setPayrollMonth] = useState(defaultPayrollMonth ?? 5);
  const [advances, setAdvances] = useState<Record<string, { amount: string; label: string }>>(
    () => {
      const init: Record<string, { amount: string; label: string }> = {};
      for (const r of results) {
        init[r.employeeId] = { amount: '0', label: `décembre ${year}` };
      }
      return init;
    },
  );

  const { data: campaigns = [], refetch: refetchCampaigns } = useQuery({
    queryKey: ['participation-campaigns', year],
    queryFn: () => listCampaigns(year),
  });

  const selectedCampaign: ParticipationCampaign | undefined = useMemo(() => {
    if (activeCampaignId) {
      return campaigns.find((c) => c.id === activeCampaignId);
    }
    return campaigns[0];
  }, [campaigns, activeCampaignId]);

  const campaignId = selectedCampaign?.id;

  const { data: bulletins = [], refetch: refetchBulletins } = useQuery({
    queryKey: ['participation-campaign-bulletins', campaignId],
    queryFn: () => listCampaignBulletins(campaignId!),
    enabled: Boolean(campaignId),
  });

  const createMut = useMutation({
    mutationFn: () => {
      const advanceList: CampaignAdvanceInput[] = results
        .map((r) => ({
          employee_id: r.employeeId,
          amount: parseFloat(advances[r.employeeId]?.amount || '0') || 0,
          label: advances[r.employeeId]?.label || '',
        }))
        .filter((a) => a.amount > 0 || a.label.trim());

      return createCampaign({
        simulation_id: simulationId,
        year,
        exercise_label: `PARTICIPATION ${year}`,
        payroll_year: payrollYear,
        payroll_month: payrollMonth,
        advances: advanceList,
        amounts: results.map((r) => ({
          employee_id: r.employeeId,
          participation_amount: r.participationAmount,
          interessement_amount: r.interessementAmount,
        })),
      });
    },
    onSuccess: (data) => {
      setActiveCampaignId(data.campaign.id);
      void queryClient.invalidateQueries({ queryKey: ['participation-campaigns', year] });
      toast({
        title: 'Campagne créée',
        description: `${data.bulletins_created} bulletin(s) préparé(s).`,
      });
    },
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Création impossible.';
      toast({ title: 'Erreur', description: String(detail), variant: 'destructive' });
    },
  });

  const publishMut = useMutation({
    mutationFn: () => publishCampaign(campaignId!),
    onSuccess: () => {
      void refetchCampaigns();
      void refetchBulletins();
      toast({ title: 'Bulletins envoyés aux salariés' });
    },
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Publication impossible.';
      toast({ title: 'Erreur', description: String(detail), variant: 'destructive' });
    },
  });

  const remindMut = useMutation({
    mutationFn: () => remindCampaign(campaignId!),
    onSuccess: () => toast({ title: 'Rappels envoyés' }),
  });

  const closeMut = useMutation({
    mutationFn: () => closeCampaignDefaults(campaignId!),
    onSuccess: () => {
      void refetchCampaigns();
      void refetchBulletins();
      toast({ title: 'Défauts PEE appliqués' });
    },
  });

  const payrollMut = useMutation({
    mutationFn: () =>
      generateCampaignPayrollLines(campaignId!, payrollYear, payrollMonth),
    onSuccess: () => {
      void refetchCampaigns();
      toast({
        title: 'Saisies créées',
        description: "Retrouvez-les dans l'onglet Primes.",
      });
    },
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Génération impossible.';
      toast({ title: 'Erreur', description: String(detail), variant: 'destructive' });
    },
  });

  const [regulPendingId, setRegulPendingId] = useState<string | null>(null);
  const regulMut = useMutation({
    mutationFn: (bulletinId: string) => generateRegularisationPayslip(bulletinId),
    onMutate: (bulletinId: string) => setRegulPendingId(bulletinId),
    onSuccess: (data) => {
      if (data.download_url) {
        window.open(data.download_url, '_blank', 'noopener');
      }
      toast({
        title: 'Bulletin de régularisation généré',
        description: `Participation versée sur la paie ${String(data.month).padStart(2, '0')}/${data.year}.`,
      });
    },
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Génération impossible.';
      toast({ title: 'Erreur', description: String(detail), variant: 'destructive' });
    },
    onSettled: () => setRegulPendingId(null),
  });

  const exportNatixisCsv = () => {
    const header = [
      'Nom',
      'Prénom',
      'Dispositif',
      'Net',
      'Choix',
      'Montant PEE',
      'Montant numéraire',
      'Statut',
    ];
    const lines = bulletins.map((b: ParticipationBulletin) => [
      b.employee_last_name ?? '',
      b.employee_first_name ?? '',
      b.dispositif_type,
      b.net_amount.toFixed(2),
      choiceLabel(b.choice_type ?? undefined),
      (b.pee_amount ?? 0).toFixed(2),
      (b.cash_amount ?? 0).toFixed(2),
      bulletinStatusLabel(b.status),
    ]);
    const csv = [header, ...lines].map((row) => row.join(';')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    downloadBlob(blob, `participation_natixis_${year}.csv`);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Megaphone className="h-5 w-5" />
          Campagne bulletin d&apos;option
        </CardTitle>
        <CardDescription>
          Préparez les acomptes, lancez la campagne, publiez les bulletins et suivez les réponses
          salariés (délai 15 jours, défaut PEE).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label>Mois de paie (solde)</Label>
            <Select
              value={String(payrollMonth)}
              onValueChange={(v) => setPayrollMonth(parseInt(v, 10))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MONTH_OPTIONS.map((m) => (
                  <SelectItem key={m.value} value={String(m.value)}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Année de paie</Label>
            <Input
              type="number"
              value={payrollYear}
              onChange={(e) => setPayrollYear(parseInt(e.target.value, 10) || payrollYear)}
            />
          </div>
          <div className="flex items-end">
            <Button
              className="w-full"
              onClick={() => createMut.mutate()}
              disabled={createMut.isPending || results.length === 0}
            >
              Lancer la campagne bulletin
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Salarié</TableHead>
                <TableHead className="text-right">Acompte (€)</TableHead>
                <TableHead>Libellé acompte</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((r) => (
                <TableRow key={r.employeeId}>
                  <TableCell>{r.employeeName}</TableCell>
                  <TableCell className="text-right">
                    <Input
                      className="ml-auto max-w-[120px] text-right"
                      type="number"
                      min={0}
                      step="0.01"
                      value={advances[r.employeeId]?.amount ?? '0'}
                      onChange={(e) =>
                        setAdvances((prev) => ({
                          ...prev,
                          [r.employeeId]: {
                            amount: e.target.value,
                            label: prev[r.employeeId]?.label ?? '',
                          },
                        }))
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={advances[r.employeeId]?.label ?? ''}
                      onChange={(e) =>
                        setAdvances((prev) => ({
                          ...prev,
                          [r.employeeId]: {
                            amount: prev[r.employeeId]?.amount ?? '0',
                            label: e.target.value,
                          },
                        }))
                      }
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {campaigns.length > 0 && (
          <div className="space-y-2">
            <Label>Campagne active</Label>
            <Select
              value={campaignId ?? ''}
              onValueChange={(v) => setActiveCampaignId(v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Choisir une campagne" />
              </SelectTrigger>
              <SelectContent>
                {campaigns.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.exercise_label} — {c.status} ({c.stats.responded + c.stats.default_pee}/
                    {c.stats.total} réponses)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {selectedCampaign && (
          <div className="rounded-lg border bg-muted/30 p-4 text-sm space-y-1">
            <div>
              Statut : <strong>{selectedCampaign.status}</strong>
            </div>
            <div>Envoi : {formatDate(selectedCampaign.sent_at)}</div>
            <div>Échéance : {formatDate(selectedCampaign.deadline_at)}</div>
            <div>
              Réponses : {selectedCampaign.stats.responded + selectedCampaign.stats.default_pee} /{' '}
              {selectedCampaign.stats.total} — En attente : {selectedCampaign.stats.sent}
            </div>
          </div>
        )}

        {campaignId && (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="default"
              disabled={publishMut.isPending || selectedCampaign?.status === 'closed'}
              onClick={() => publishMut.mutate()}
            >
              <Send className="mr-2 h-4 w-4" />
              Publier les bulletins
            </Button>
            <Button
              variant="outline"
              disabled={remindMut.isPending}
              onClick={() => remindMut.mutate()}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Relancer les retardataires
            </Button>
            <Button variant="outline" disabled={closeMut.isPending} onClick={() => closeMut.mutate()}>
              Clôturer (défaut PEE)
            </Button>
            <Button
              variant="secondary"
              disabled={payrollMut.isPending}
              onClick={() => payrollMut.mutate()}
            >
              Générer les saisies paie
            </Button>
            <Button variant="outline" onClick={exportNatixisCsv} disabled={bulletins.length === 0}>
              <Download className="mr-2 h-4 w-4" />
              Export Natixis (CSV)
            </Button>
          </div>
        )}

        {bulletins.length > 0 && (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Dispositif</TableHead>
                  <TableHead className="text-right">Net</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Choix</TableHead>
                  <TableHead className="text-right">PEE</TableHead>
                  <TableHead className="text-right">Numéraire</TableHead>
                  <TableHead className="text-right">Bulletin</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bulletins.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell>
                      {b.employee_first_name} {b.employee_last_name}
                    </TableCell>
                    <TableCell className="capitalize">{b.dispositif_type}</TableCell>
                    <TableCell className="text-right">{formatCurrency(b.net_amount)}</TableCell>
                    <TableCell>{bulletinStatusLabel(b.status)}</TableCell>
                    <TableCell>{choiceLabel(b.choice_type ?? undefined)}</TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(b.pee_amount ?? 0)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(b.cash_amount ?? 0)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        title="Générer un bulletin de paie de régularisation (y compris salarié parti)"
                        disabled={regulMut.isPending && regulPendingId === b.id}
                        onClick={() => regulMut.mutate(b.id)}
                      >
                        <FileText className="mr-1 h-4 w-4" />
                        Régularisation
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
