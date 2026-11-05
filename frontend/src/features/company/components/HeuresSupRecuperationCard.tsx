import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getModulationSettings, updateModulationSettings } from '@/api/modulation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { useCompany } from '@/contexts/CompanyContext';
import { useToast } from '@/hooks/use-toast';
import { getUserErrorMessage } from '@/lib/errorMessages';
import { queryKeys } from '@/lib/queryKeys';

type Choix = 'payees' | 'compteur';

/**
 * Le seul réglage des heures de récupération (spec 2026-11-05 § 3.1) :
 * heures sup payées au bulletin, ou mises au compteur (plafond facultatif).
 * Les conditions de L3121-37 sont dites au moment du choix : activer vaut
 * confirmation, la question n'est pas reposée.
 */
export default function HeuresSupRecuperationCard() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.modulationSettings(companyId),
    queryFn: getModulationSettings,
    enabled: Boolean(companyId),
  });

  const actuel: Choix =
    data?.hour_account_enabled && data.hs_routing_policy !== 'pay_all' ? 'compteur' : 'payees';
  const [choix, setChoix] = useState<Choix>(actuel);
  const [plafond, setPlafond] = useState('');
  useEffect(() => {
    setChoix(actuel);
    setPlafond(
      data?.max_account_balance_hours != null ? String(data.max_account_balance_hours) : '',
    );
  }, [actuel, data?.max_account_balance_hours]);

  const enregistrer = useMutation({
    mutationFn: () => {
      if (choix === 'payees') {
        return updateModulationSettings({ hour_account_enabled: false, hs_routing_policy: 'pay_all' });
      }
      const n = Number.parseFloat(plafond.replace(',', '.'));
      return updateModulationSettings({
        hour_account_enabled: true,
        hs_routing_policy: 'account_all',
        max_account_balance_hours: Number.isFinite(n) && n > 0 ? n : null,
        recovery_absence_enabled: true,
        recovery_debit_timing: 'on_validation',
      });
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.modulationSettings(companyId), saved);
      toast({
        title: 'Enregistré',
        description:
          choix === 'compteur'
            ? 'Les heures sup iront au compteur de récupération dès le prochain calcul.'
            : 'Les heures sup sont payées au bulletin.',
      });
    },
    onError: (err) =>
      toast({ title: 'Rien n’a été changé', description: getUserErrorMessage(err), variant: 'destructive' }),
  });

  if (isLoading || !data) return null;

  return (
    <Card data-testid="reglage-heures-sup">
      <CardHeader>
        <CardTitle className="text-base">Heures supplémentaires</CardTitle>
        <CardDescription>
          Payées au bulletin, ou mises au compteur de récupération et prises en repos.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <RadioGroup value={choix} onValueChange={(v) => setChoix(v as Choix)}>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="payees" id="hs-payees" />
            <Label htmlFor="hs-payees">Payées au bulletin</Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="compteur" id="hs-compteur" />
            <Label htmlFor="hs-compteur">Mises au compteur de récupération</Label>
          </div>
        </RadioGroup>
        {choix === 'compteur' ? (
          <div className="space-y-3 rounded-md border p-3">
            <p>
              Une heure sup à 25 % donne 1 h 15 de repos, à 50 % 1 h 30. Le bulletin affiche les
              heures acquises, les heures prises et le solde. Pour un salarié et un mois, vous
              pourrez toujours payer au lieu de mettre au compteur, depuis son bulletin.
            </p>
            <div className="flex items-center gap-2">
              <Label htmlFor="hs-plafond">Plafond du compteur (facultatif)</Label>
              <Input
                id="hs-plafond"
                inputMode="decimal"
                className="h-8 w-24 text-right"
                placeholder="aucun"
                value={plafond}
                onChange={(e) => setPlafond(e.target.value)}
              />
              <span>h de repos ; au-delà, les heures sont payées.</span>
            </div>
            {actuel !== 'compteur' ? (
              <p className="text-xs text-muted-foreground">
                Sans accord collectif, la loi permet ce choix si l’entreprise n’a pas de délégué
                syndical, et si le CSE, quand il existe, ne s’y oppose pas (Code du travail,
                L3121-37). En enregistrant, vous confirmez que c’est le cas.
              </p>
            ) : null}
          </div>
        ) : null}
        <Button size="sm" disabled={enregistrer.isPending} onClick={() => enregistrer.mutate()}>
          Enregistrer
        </Button>
      </CardContent>
    </Card>
  );
}
