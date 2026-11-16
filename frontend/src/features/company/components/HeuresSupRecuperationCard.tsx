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

type Choix = 'payees' | 'premieres' | 'compteur';

const HEURES_PAR_DEFAUT = '14';

function nombre(texte: string): number | null {
  const t = texte.trim();
  return t === '' ? null : Number.parseFloat(t.replace(',', '.'));
}

/**
 * Le seul réglage des heures de récupération (spec 2026-11-05 § 3.1) :
 * heures sup payées au bulletin, les N premières du mois au compteur et le
 * reste payé (modulation de Cartol, retour d'Elsa du 16/11), ou toutes au
 * compteur (plafond facultatif).
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

  const actuel: Choix = !data?.hour_account_enabled || data.hs_routing_policy === 'pay_all'
    ? 'payees'
    : data.hs_routing_policy === 'franchise'
      ? 'premieres'
      : 'compteur';
  const [choix, setChoix] = useState<Choix>(actuel);
  const [plafond, setPlafond] = useState('');
  const [premieres, setPremieres] = useState(HEURES_PAR_DEFAUT);
  useEffect(() => {
    setChoix(actuel);
    setPlafond(
      data?.max_account_balance_hours != null ? String(data.max_account_balance_hours) : '',
    );
    setPremieres(
      data?.hs_franchise_hours_per_period != null && data.hs_franchise_hours_per_period > 0
        ? String(data.hs_franchise_hours_per_period)
        : HEURES_PAR_DEFAUT,
    );
  }, [actuel, data?.max_account_balance_hours, data?.hs_franchise_hours_per_period]);

  const avecCompteur = choix !== 'payees';
  const plafondSaisi = nombre(plafond);
  const plafondInvalide =
    avecCompteur && plafondSaisi !== null && !(Number.isFinite(plafondSaisi) && plafondSaisi > 0);
  const premieresSaisies = nombre(premieres);
  const premieresInvalides =
    choix === 'premieres' &&
    !(premieresSaisies !== null && Number.isFinite(premieresSaisies) && premieresSaisies > 0 && premieresSaisies <= 500);

  const enregistrer = useMutation({
    mutationFn: () => {
      if (choix === 'payees') {
        // Le compte reste ouvert : un solde déjà acquis reste dû, visible, et
        // se prend ou se paie toujours.
        return updateModulationSettings({ hs_routing_policy: 'pay_all' });
      }
      return updateModulationSettings({
        hour_account_enabled: true,
        hs_routing_policy: choix === 'premieres' ? 'franchise' : 'account_all',
        ...(choix === 'premieres'
          ? { hs_franchise_hours_per_period: premieresSaisies, hs_franchise_period: 'month' as const }
          : {}),
        max_account_balance_hours: plafondSaisi,
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
            : choix === 'premieres'
              ? `Dès le prochain calcul, les ${premieres.trim()} premières heures sup du mois iront au compteur ; au-delà, elles sont payées.`
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
          Payées au bulletin, ou mises au compteur de récupération et prises en repos (en tout ou
          pour les premières heures du mois seulement).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <RadioGroup value={choix} onValueChange={(v) => setChoix(v as Choix)}>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="payees" id="hs-payees" />
            <Label htmlFor="hs-payees">Payées au bulletin</Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="premieres" id="hs-premieres" />
            <Label htmlFor="hs-premieres">Les premières heures du mois au compteur, le reste payé</Label>
          </div>
          <div className="flex items-center gap-2">
            <RadioGroupItem value="compteur" id="hs-compteur" />
            <Label htmlFor="hs-compteur">Toutes au compteur de récupération</Label>
          </div>
        </RadioGroup>
        {avecCompteur ? (
          <div className="space-y-3 rounded-md border p-3">
            {choix === 'premieres' ? (
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Label htmlFor="hs-premieres-heures">Chaque mois, les</Label>
                  <Input
                    id="hs-premieres-heures"
                    data-testid="hs-premieres-heures"
                    inputMode="decimal"
                    className="h-8 w-20 text-right"
                    value={premieres}
                    onChange={(e) => setPremieres(e.target.value)}
                  />
                  <span>premières heures sup vont au compteur ; au-delà, elles sont payées.</span>
                </div>
                {premieresInvalides ? (
                  <p className="text-xs text-destructive">Indiquez un nombre d’heures, par exemple 14.</p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  Les heures se comptent mois par mois (le solde du compteur, lui, reste acquis) : avec 14, un salarié qui fait 20 h sup en
                  met 14 au compteur et 6 sont payées sur son bulletin.
                </p>
              </div>
            ) : null}
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
            {plafondInvalide ? (
              <p className="text-xs text-destructive">
                Indiquez un nombre d’heures, ou laissez vide pour ne pas mettre de plafond.
              </p>
            ) : null}
            {actuel === 'payees' ? (
              <p className="text-xs text-muted-foreground">
                Sans accord collectif, la loi permet ce choix si l’entreprise n’a pas de délégué
                syndical, et si le CSE, quand il existe, ne s’y oppose pas (Code du travail,
                L3121-37). En enregistrant, vous confirmez que c’est le cas.
              </p>
            ) : null}
          </div>
        ) : null}
        <Button size="sm" disabled={enregistrer.isPending || plafondInvalide || premieresInvalides} onClick={() => enregistrer.mutate()}>
          Enregistrer
        </Button>
      </CardContent>
    </Card>
  );
}
