import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CASE_STATUS_LABELS,
  confirmWorkMedalCase,
  listEmployeeWorkMedalCases,
  MEDAL_LEVEL_LABELS,
} from '@/api/workMedals';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { Award } from 'lucide-react';

interface WorkMedalEmployeeActionProps {
  employeeId: string;
}

export function WorkMedalEmployeeAction({ employeeId }: WorkMedalEmployeeActionProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: cases = [] } = useQuery({
    queryKey: ['work-medals', 'employee', employeeId],
    queryFn: () => listEmployeeWorkMedalCases(employeeId),
    enabled: Boolean(employeeId),
  });

  const confirmMutation = useMutation({
    mutationFn: confirmWorkMedalCase,
    onSuccess: () => {
      toast({
        title: 'Confirmation enregistrée',
        description: 'Votre RH sera notifié pour valider la prime.',
      });
      queryClient.invalidateQueries({ queryKey: ['work-medals', 'employee', employeeId] });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Confirmation impossible.',
        variant: 'destructive',
      });
    },
  });

  const pending = cases.filter((c) => c.status === 'awaiting_employee');
  const history = cases.filter((c) => !['awaiting_employee', 'upcoming'].includes(c.status));

  if (cases.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Award className="mr-2 h-5 w-5 text-amber-600" />
          Médailles du travail
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {pending.map((c) => (
          <div key={c.id} className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
            <p className="font-medium">{MEDAL_LEVEL_LABELS[c.medal_level]}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Vous avez atteint {c.milestone_years} ans de carrière (éligible le{' '}
              {new Date(c.eligible_date).toLocaleDateString('fr-FR')}). Confirmez pour déclencher
              la prime prévue par votre entreprise.
            </p>
            <Button
              className="mt-3"
              size="sm"
              onClick={() => confirmMutation.mutate(c.id)}
              disabled={confirmMutation.isPending}
            >
              Je confirme mon éligibilité
            </Button>
          </div>
        ))}

        {history.length > 0 ? (
          <ul className="space-y-2">
            {history.map((c) => (
              <li key={c.id} className="flex items-center justify-between text-sm">
                <span>{MEDAL_LEVEL_LABELS[c.medal_level]}</span>
                <Badge variant="outline">{CASE_STATUS_LABELS[c.status]}</Badge>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
