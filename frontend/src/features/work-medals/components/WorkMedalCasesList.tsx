import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  approveWorkMedalCase,
  CASE_STATUS_LABELS,
  dismissWorkMedalCase,
  listWorkMedalCases,
  MEDAL_LEVEL_LABELS,
  type WorkMedalCase,
} from '@/api/workMedals';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { Award } from 'lucide-react';
import { useState } from 'react';

function employeeName(c: WorkMedalCase): string {
  const fn = c.employee_first_name ?? '';
  const ln = c.employee_last_name ?? '';
  return `${fn} ${ln}`.trim() || 'Collaborateur';
}

function statusVariant(
  status: WorkMedalCase['status'],
): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'awaiting_rh' || status === 'awaiting_employee') return 'default';
  if (status === 'dismissed') return 'destructive';
  return 'outline';
}

interface ApproveRowProps {
  caseItem: WorkMedalCase;
  onDone: () => void;
}

function ApproveRow({ caseItem, onDone }: ApproveRowProps) {
  const { toast } = useToast();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [amountOverride, setAmountOverride] = useState<string>('');

  const approveMutation = useMutation({
    mutationFn: () =>
      approveWorkMedalCase(caseItem.id, {
        payroll_year: year,
        payroll_month: month,
        amount_override: amountOverride ? Number(amountOverride) : undefined,
      }),
    onSuccess: () => {
      toast({ title: 'Prime validée', description: 'La saisie paie a été créée.' });
      onDone();
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Validation impossible.',
        variant: 'destructive',
      });
    },
  });

  const dismissMutation = useMutation({
    mutationFn: () => dismissWorkMedalCase(caseItem.id, 'Non applicable'),
    onSuccess: () => {
      toast({ title: 'Dossier ignoré' });
      onDone();
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Action impossible.',
        variant: 'destructive',
      });
    },
  });

  return (
    <div className="flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">{employeeName(caseItem)}</p>
          <p className="text-sm text-muted-foreground">
            {MEDAL_LEVEL_LABELS[caseItem.medal_level]} — palier {caseItem.milestone_years} ans
            (éligible le {new Date(caseItem.eligible_date).toLocaleDateString('fr-FR')})
          </p>
        </div>
        <Badge variant={statusVariant(caseItem.status)}>
          {CASE_STATUS_LABELS[caseItem.status]}
        </Badge>
      </div>

      {(caseItem.status === 'awaiting_rh' || caseItem.status === 'awaiting_employee') ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <Label className="text-xs">Mois de paie</Label>
            <Input
              type="number"
              min={1}
              max={12}
              value={month}
              onChange={(e) => setMonth(Number(e.target.value) || 1)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Année</Label>
            <Input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value) || year)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Montant (optionnel)</Label>
            <Input
              type="number"
              min={0}
              placeholder="Barème entreprise"
              value={amountOverride}
              onChange={(e) => setAmountOverride(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap gap-2 sm:col-span-3">
            <Button
              size="sm"
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
            >
              Valider et créer la saisie paie
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => dismissMutation.mutate()}
              disabled={dismissMutation.isPending}
            >
              Ignorer
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function WorkMedalCasesList({ statusFilter }: { statusFilter?: string }) {
  const queryClient = useQueryClient();
  const rhPendingOnly = statusFilter === 'awaiting_rh';
  const { data, isLoading } = useQuery({
    queryKey: ['work-medals', statusFilter ?? 'all'],
    queryFn: () => listWorkMedalCases(statusFilter ? { status: statusFilter } : undefined),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['work-medals'] });
    queryClient.invalidateQueries({ queryKey: ['work-medal-summary'] });
  };

  if (isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }

  const cases = (data ?? []).filter((c) =>
    rhPendingOnly
      ? c.status === 'awaiting_rh' || c.status === 'awaiting_employee'
      : true,
  );
  const actionable = cases.filter((c) =>
    ['awaiting_rh', 'awaiting_employee', 'upcoming'].includes(c.status),
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Award className="mr-2 h-5 w-5" />
          Dossiers médailles
        </CardTitle>
        <CardDescription>
          {actionable.length > 0
            ? `${actionable.length} dossier(s) à suivre`
            : 'Aucun dossier en attente'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {cases.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucun dossier. Activez le module et lancez un scan depuis les paramètres paie.
          </p>
        ) : (
          cases.map((c) => <ApproveRow key={c.id} caseItem={c} onDone={invalidate} />)
        )}
      </CardContent>
    </Card>
  );
}
