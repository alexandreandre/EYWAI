import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/components/ui/use-toast';
import {
  getDelegationConfig,
  updateDelegationConfig,
  type DelegationConfigUpdate,
} from '@/api/cse';
import { Loader2, Settings2 } from 'lucide-react';
import { useState } from 'react';

export function DelegationConfigCard() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: config, isLoading } = useQuery({
    queryKey: ['cse', 'delegation-config'],
    queryFn: getDelegationConfig,
  });

  const [headcount, setHeadcount] = useState<string>('');
  const [refDate, setRefDate] = useState<string>('');

  const saveMutation = useMutation({
    mutationFn: (payload: DelegationConfigUpdate) => updateDelegationConfig(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cse'] });
      toast({ title: 'Configuration enregistrée' });
    },
    onError: (error: Error) => {
      toast({
        title: 'Erreur',
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  if (isLoading || !config) {
    return (
      <Card>
        <CardContent className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  const effectiveHeadcount = headcount || String(config.reference_headcount);
  const effectiveDate =
    refDate || config.reference_date?.split('T')[0] || new Date().toISOString().split('T')[0];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Settings2 className="h-5 w-5" />
          Configuration délégation (effectif figé)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Effectif actuel : {config.current_headcount} salariés — barème art. R. 2314-1 appliqué
          sur l&apos;effectif de référence à la date des élections.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="ref-headcount">Effectif de référence</Label>
            <Input
              id="ref-headcount"
              type="number"
              min={0}
              value={effectiveHeadcount}
              onChange={(e) => setHeadcount(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="ref-date">Date de référence (élections)</Label>
            <Input
              id="ref-date"
              type="date"
              value={effectiveDate}
              onChange={(e) => setRefDate(e.target.value)}
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2">
            <Switch
              id="report-enabled"
              checked={config.report_enabled}
              onCheckedChange={(checked) =>
                saveMutation.mutate({ report_enabled: checked })
              }
            />
            <Label htmlFor="report-enabled">Report 12 mois</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="mutua-enabled"
              checked={config.mutualisation_enabled}
              onCheckedChange={(checked) =>
                saveMutation.mutate({ mutualisation_enabled: checked })
              }
            />
            <Label htmlFor="mutua-enabled">Mutualisation</Label>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() =>
              saveMutation.mutate({ initialize_from_current_headcount: true })
            }
            disabled={saveMutation.isPending}
          >
            Reprendre l&apos;effectif actuel
          </Button>
          <Button
            onClick={() =>
              saveMutation.mutate({
                reference_headcount: Number(effectiveHeadcount),
                reference_date: effectiveDate,
              })
            }
            disabled={saveMutation.isPending}
          >
            Enregistrer
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
