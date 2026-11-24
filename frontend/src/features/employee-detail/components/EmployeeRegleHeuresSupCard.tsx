import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clock } from 'lucide-react';

import { getRegleHeuresSup, setRegleHeuresSup } from '@/api/modulation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { useCompany } from '@/contexts/CompanyContext';
import { useToast } from '@/hooks/use-toast';
import { getUserErrorMessage } from '@/lib/errorMessages';
import { queryKeys } from '@/lib/queryKeys';
import {
  type ChoixRegleHeuresSup,
  choixDeLaRegle,
  phraseDuChoix,
  regleDuChoix,
} from './regleHeuresSup';

interface Props {
  employeeId: string;
  canEdit?: boolean;
}

const CHOIX: { valeur: ChoixRegleHeuresSup; libelle: string }[] = [
  { valeur: 'societe', libelle: 'Règle de la société' },
  { valeur: 'pay_all', libelle: 'Toujours payées' },
  { valeur: 'account_all', libelle: 'Toujours au compteur' },
];

/**
 * Heures sup du salarié : la règle de la société, ou la sienne (retour d'Elsa,
 * Cartol : les alternants ne vont pas au compteur). Visible seulement quand la
 * société tient un compteur de récupération : sans compteur, toutes les heures
 * sup sont payées et le choix n'aurait aucun effet.
 */
export function EmployeeRegleHeuresSupCard({ employeeId, canEdit = true }: Props) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const cle = queryKeys.regleHeuresSup(companyId, employeeId);
  const { data } = useQuery({
    queryKey: cle,
    queryFn: () => getRegleHeuresSup(employeeId),
    enabled: Boolean(companyId && employeeId),
  });
  const actuel = choixDeLaRegle(data?.regle ?? null);
  const [choix, setChoix] = useState<ChoixRegleHeuresSup>(actuel);
  useEffect(() => setChoix(actuel), [actuel]);

  const enregistrer = useMutation({
    mutationFn: () => setRegleHeuresSup(employeeId, regleDuChoix(choix)),
    onSuccess: (saved) => {
      queryClient.setQueryData(cle, saved);
      void queryClient.invalidateQueries({ queryKey: queryKeys.modulationSettings(companyId) });
      toast({
        title: 'Enregistré',
        description:
          'Vaut dès le prochain calcul de son bulletin ; un bulletin déjà calculé change en le recalculant.',
      });
    },
    onError: (err) =>
      toast({ title: 'Rien n’a été changé', description: getUserErrorMessage(err), variant: 'destructive' }),
  });

  if (!data || !data.compteur_ouvert) return null;

  return (
    <Card data-testid="regle-heures-sup-salarie">
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Clock className="mr-2 h-5 w-5 text-primary" />
          Heures supplémentaires
        </CardTitle>
        <CardDescription>
          Payées sur le bulletin ou mises au compteur de récupération, pour ce salarié.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <RadioGroup
          value={choix}
          onValueChange={(v) => setChoix(v as ChoixRegleHeuresSup)}
          disabled={!canEdit || enregistrer.isPending}
        >
          {CHOIX.map(({ valeur, libelle }) => (
            <div key={valeur} className="flex items-center gap-2">
              <RadioGroupItem value={valeur} id={`regle-hs-${valeur}`} />
              <Label htmlFor={`regle-hs-${valeur}`}>{libelle}</Label>
            </div>
          ))}
        </RadioGroup>
        <p data-testid="regle-heures-sup-phrase">{phraseDuChoix(choix, data.regle_societe)}</p>
        <p className="text-xs text-muted-foreground">
          Pour un seul mois, le choix reste possible depuis son bulletin.
        </p>
        {canEdit && (
          <Button
            type="button"
            size="sm"
            onClick={() => enregistrer.mutate()}
            disabled={enregistrer.isPending || choix === actuel}
          >
            Enregistrer
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
