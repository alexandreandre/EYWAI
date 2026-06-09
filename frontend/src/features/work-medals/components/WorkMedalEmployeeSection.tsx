import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  approveWorkMedalCase,
  CASE_STATUS_LABELS,
  dismissWorkMedalCase,
  listEmployeeWorkMedalCases,
  MEDAL_LEVEL_LABELS,
  type WorkMedalCase,
} from '@/api/workMedals';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { Award } from 'lucide-react';
import { useState } from 'react';

interface WorkMedalEmployeeSectionProps {
  employeeId: string;
  priorServiceMonths?: number | null;
  canEdit: boolean;
  onPriorServiceChange?: (months: number) => void;
}

function RhActions({ caseItem, onDone }: { caseItem: WorkMedalCase; onDone: () => void }) {
  const { toast } = useToast();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const approveMutation = useMutation({
    mutationFn: () =>
      approveWorkMedalCase(caseItem.id, { payroll_year: year, payroll_month: month }),
    onSuccess: () => {
      toast({ title: 'Prime validée' });
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
    mutationFn: () => dismissWorkMedalCase(caseItem.id),
    onSuccess: () => onDone(),
  });

  if (caseItem.status !== 'awaiting_rh') return null;

  return (
    <div className="mt-2 flex flex-wrap items-end gap-2">
      <div>
        <Label className="text-xs">Mois</Label>
        <Input
          className="w-20"
          type="number"
          min={1}
          max={12}
          value={month}
          onChange={(e) => setMonth(Number(e.target.value) || 1)}
        />
      </div>
      <div>
        <Label className="text-xs">Année</Label>
        <Input
          className="w-24"
          type="number"
          value={year}
          onChange={(e) => setYear(Number(e.target.value) || year)}
        />
      </div>
      <Button size="sm" onClick={() => approveMutation.mutate()} disabled={approveMutation.isPending}>
        Valider la prime
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => dismissMutation.mutate()}
        disabled={dismissMutation.isPending}
      >
        Ignorer
      </Button>
    </div>
  );
}

export function WorkMedalEmployeeSection({
  employeeId,
  priorServiceMonths,
  canEdit,
  onPriorServiceChange,
}: WorkMedalEmployeeSectionProps) {
  const queryClient = useQueryClient();
  const [priorMonths, setPriorMonths] = useState(priorServiceMonths ?? 0);

  const { data, isLoading } = useQuery({
    queryKey: ['work-medals', 'employee', employeeId],
    queryFn: () => listEmployeeWorkMedalCases(employeeId),
    enabled: Boolean(employeeId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['work-medals', 'employee', employeeId] });
    queryClient.invalidateQueries({ queryKey: ['work-medals'] });
  };

  if (isLoading) return <Skeleton className="h-24 w-full" />;

  const cases = data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Award className="mr-2 h-5 w-5" />
          Médailles du travail
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {canEdit ? (
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1">
              <Label className="text-xs">Ancienneté antérieure (mois)</Label>
              <Input
                type="number"
                min={0}
                className="w-32"
                value={priorMonths}
                onChange={(e) => setPriorMonths(Number(e.target.value) || 0)}
              />
            </div>
            {onPriorServiceChange ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => onPriorServiceChange(priorMonths)}
              >
                Enregistrer l&apos;ancienneté
              </Button>
            ) : null}
          </div>
        ) : null}

        {cases.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun palier détecté pour ce collaborateur.</p>
        ) : (
          <ul className="space-y-3">
            {cases.map((c) => (
              <li key={c.id} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{MEDAL_LEVEL_LABELS[c.medal_level]}</span>
                  <Badge variant="outline">{CASE_STATUS_LABELS[c.status]}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  Palier {c.milestone_years} ans — éligible le{' '}
                  {new Date(c.eligible_date).toLocaleDateString('fr-FR')}
                  {c.amount_computed != null ? ` — ${c.amount_computed.toFixed(2)} €` : ''}
                </p>
                {canEdit ? <RhActions caseItem={c} onDone={invalidate} /> : null}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
