import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { getTeams } from '@/api/teams';
import {
  justifyAnomaly,
  removeAnomalyJustification,
  type PreflightAnomaly,
  type PreflightAnomalyType,
  type PreflightResolutionMotif,
} from '@/api/payrollPreflight';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';
import { invalidateRhSidebarBadges } from '@/lib/invalidateRhSidebarBadges';
import { usePreflightAnomalies } from '@/features/payroll/hooks/usePreflightAnomaliesCount';
import { AnomalyTable } from '@/features/payroll/components/review/AnomalyTable';
import { JustifyAnomalyDialog } from '@/features/payroll/components/review/JustifyAnomalyDialog';
import { PayrollReviewSummaryBanner } from '@/features/payroll/components/review/PayrollReviewSummaryBanner';
import {
  countOpenByType,
  PREFLIGHT_ANOMALY_TYPE_LABELS,
  PREFLIGHT_ANOMALY_TYPE_ORDER,
} from '@/features/payroll/components/review/preflightLabels';
import { useQuery } from '@tanstack/react-query';

function generateMonthOptions() {
  const options: { value: string; label: string; year: number; month: number }[] = [];
  const now = new Date();
  for (let i = -12; i <= 2; i++) {
    const date = new Date(now.getFullYear(), now.getMonth() + i, 1);
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const value = `${year}-${String(month).padStart(2, '0')}`;
    const label = date.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
    options.push({
      value,
      label: label.charAt(0).toUpperCase() + label.slice(1),
      year,
      month,
    });
  }
  return options;
}

export function PayrollReviewContent() {
  const monthOptions = useMemo(() => generateMonthOptions(), []);
  const now = new Date();
  const defaultValue = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const [selectedMonth, setSelectedMonth] = useState(defaultValue);
  const [activeTab, setActiveTab] = useState<PreflightAnomalyType | 'all'>('all');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [justifyTargets, setJustifyTargets] = useState<PreflightAnomaly[]>([]);
  const [justifyOpen, setJustifyOpen] = useState(false);

  const { toast } = useToast();
  const queryClient = useQueryClient();
  const companyId = useActiveCompanyId();

  const parsed = useMemo(() => {
    const [yearStr, monthStr] = selectedMonth.split('-');
    return { year: parseInt(yearStr, 10), month: parseInt(monthStr, 10) };
  }, [selectedMonth]);

  const { data, isLoading, isError, refetch } = usePreflightAnomalies(
    parsed.year,
    parsed.month,
  );

  const teamsQuery = useQuery({
    queryKey: queryKeys.planning(companyId),
    queryFn: getTeams,
    staleTime: 60_000,
  });

  const teamNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const team of teamsQuery.data?.teams ?? []) {
      map[team.id] = team.name;
    }
    return map;
  }, [teamsQuery.data]);

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: queryKeys.payrollPreflight(companyId, parsed.year, parsed.month),
    });
    void queryClient.invalidateQueries({
      queryKey: ['payroll', 'preflight-anomalies', 'sidebar-badges'],
    });
    void invalidateRhSidebarBadges(queryClient);
  };

  const justifyMutation = useMutation({
    mutationFn: async ({
      targets,
      motif,
      commentaire,
    }: {
      targets: PreflightAnomaly[];
      motif: PreflightResolutionMotif;
      commentaire: string;
    }) => {
      for (const anomaly of targets) {
        await justifyAnomaly({
          employee_id: anomaly.employee_id,
          anomaly_type: anomaly.type,
          year: parsed.year,
          month: parsed.month,
          motif,
          commentaire: commentaire || undefined,
        });
      }
    },
    onSuccess: (_data, variables) => {
      invalidate();
      setSelectedIds(new Set());
      setJustifyOpen(false);
      setJustifyTargets([]);
      toast({
        title: 'Anomalie(s) justifiée(s)',
        description: `${variables.targets.length} anomalie(s) enregistrée(s).`,
      });
    },
    onError: () => {
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: 'Impossible d\'enregistrer la justification.',
      });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (anomaly: PreflightAnomaly) =>
      removeAnomalyJustification({
        employee_id: anomaly.employee_id,
        anomaly_type: anomaly.type,
        year: parsed.year,
        month: parsed.month,
      }),
    onSuccess: () => {
      invalidate();
      toast({ title: 'Justification annulée' });
    },
    onError: () => {
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: 'Impossible d\'annuler la justification.',
      });
    },
  });

  const selectedAnomalies = useMemo(() => {
    if (!data) return [];
    return data.anomalies.filter((a) => selectedIds.has(a.id) && a.status === 'a_traiter');
  }, [data, selectedIds]);

  const handleBulkJustify = () => {
    if (selectedAnomalies.length === 0) return;
    setJustifyTargets(selectedAnomalies);
    setJustifyOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Revue des anomalies</h1>
          <p className="text-sm text-muted-foreground">
            Contrôle qualité des heures et du pointage avant le lancement de la paie.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[220px]">
            <Label htmlFor="review-month" className="mb-2 block text-sm">
              Mois de paie
            </Label>
            <Select value={selectedMonth} onValueChange={setSelectedMonth}>
              <SelectTrigger id="review-month">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {monthOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" asChild className="mt-6">
            <Link to="/payroll/generate">Lancer la paie</Link>
          </Button>
        </div>
      </div>

      <PayrollReviewSummaryBanner data={data} isLoading={isLoading} />

      {isError && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
          Impossible de charger les anomalies.{' '}
          <button type="button" className="font-medium underline" onClick={() => refetch()}>
            Réessayer
          </button>
        </div>
      )}

      {!isLoading && data && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              {data.total_open} ouverte{data.total_open > 1 ? 's' : ''} · {data.total_treated}{' '}
              traitée{data.total_treated > 1 ? 's' : ''}
            </p>
            {selectedAnomalies.length > 0 && (
              <Button size="sm" onClick={handleBulkJustify}>
                Justifier la sélection ({selectedAnomalies.length})
              </Button>
            )}
          </div>

          <Tabs
            value={activeTab}
            onValueChange={(value) => setActiveTab(value as PreflightAnomalyType | 'all')}
          >
            <TabsList className="flex h-auto flex-wrap justify-start gap-1">
              <TabsTrigger value="all">
                Toutes ({countOpenByType(data.anomalies, 'ecart_heures') +
                  countOpenByType(data.anomalies, 'heures_non_saisies') +
                  countOpenByType(data.anomalies, 'pointage') +
                  countOpenByType(data.anomalies, 'conflit_absence')})
              </TabsTrigger>
              {PREFLIGHT_ANOMALY_TYPE_ORDER.map((type) => {
                const open = countOpenByType(data.anomalies, type);
                const total = data.anomalies.filter((a) => a.type === type).length;
                if (total === 0) return null;
                return (
                  <TabsTrigger key={type} value={type}>
                    {PREFLIGHT_ANOMALY_TYPE_LABELS[type]} ({open > 0 ? open : total})
                  </TabsTrigger>
                );
              })}
            </TabsList>

            <TabsContent value={activeTab} className="mt-4">
              <AnomalyTable
                anomalies={data.anomalies}
                teamNames={teamNames}
                activeType={activeTab}
                selectedIds={selectedIds}
                onSelectedIdsChange={setSelectedIds}
                onJustify={(items) => {
                  setJustifyTargets(items);
                  setJustifyOpen(true);
                }}
                onRemoveJustification={(anomaly) => removeMutation.mutate(anomaly)}
              />
            </TabsContent>
          </Tabs>
        </>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" aria-hidden />
          Chargement…
        </div>
      )}

      <JustifyAnomalyDialog
        open={justifyOpen}
        onOpenChange={setJustifyOpen}
        anomalies={justifyTargets}
        isSubmitting={justifyMutation.isPending}
        onConfirm={async (motif, commentaire) => {
          await justifyMutation.mutateAsync({
            targets: justifyTargets,
            motif,
            commentaire,
          });
        }}
      />
    </div>
  );
}
