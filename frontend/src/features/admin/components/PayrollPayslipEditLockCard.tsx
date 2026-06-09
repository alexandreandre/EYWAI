import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lock } from 'lucide-react';

import {
  getPayslipEditLockSettings,
  updatePayslipEditLockSettings,
} from '@/api/rates';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';

export function PayrollPayslipEditLockCard() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [cutoffDay, setCutoffDay] = useState('15');

  const { data, isLoading } = useQuery({
    queryKey: ['payslip-edit-lock'],
    queryFn: getPayslipEditLockSettings,
  });

  useEffect(() => {
    if (data?.cutoff_day_of_next_month != null) {
      setCutoffDay(String(data.cutoff_day_of_next_month));
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const parsed = Number.parseInt(cutoffDay, 10);
      if (Number.isNaN(parsed) || parsed < 1 || parsed > 28) {
        throw new Error('Le jour doit être un entier entre 1 et 28.');
      }
      return updatePayslipEditLockSettings({ cutoff_day_of_next_month: parsed });
    },
    onSuccess: (result) => {
      queryClient.setQueryData(['payslip-edit-lock'], {
        cutoff_day_of_next_month: result.cutoff_day_of_next_month,
      });
      toast({ title: 'Règle de verrouillage enregistrée' });
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Impossible d’enregistrer la règle.';
      toast({ title: 'Erreur', description: message, variant: 'destructive' });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Lock className="h-4 w-4 text-primary" />
          Verrouillage édition manuelle des bulletins
        </CardTitle>
        <CardDescription>
          Les bulletins du mois M ne sont plus éditables manuellement par les RH à
          partir du jour configuré du mois M+1.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2 max-w-xs">
          <Label htmlFor="payslip-edit-lock-day">Jour du mois suivant</Label>
          <Input
            id="payslip-edit-lock-day"
            type="number"
            min={1}
            max={28}
            value={cutoffDay}
            disabled={isLoading || saveMutation.isPending}
            onChange={(e) => setCutoffDay(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Exemple avec 15 : un bulletin de juin reste éditable jusqu’au 14 juillet
            inclus.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={isLoading || saveMutation.isPending}
        >
          Enregistrer la règle
        </Button>
      </CardContent>
    </Card>
  );
}
