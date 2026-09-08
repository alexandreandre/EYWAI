import { useState } from 'react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  estSurLeMoisCivil,
  formatFr,
  libelleSemaines,
} from '@/features/payroll/lib/fenetreVariables';
import {
  useEnregistrerPeriodeVariables,
  usePeriodeVariables,
} from '@/features/payroll/hooks/usePeriodeVariables';

interface Props {
  year: number;
  month: number;
}

/**
 * Fenêtre des heures sup et des paniers pour le mois lancé.
 *
 * Le début n'est pas modifiable : il est la suite du mois précédent, et c'est
 * ce qui garantit qu'aucune semaine n'est ni perdue ni payée deux fois. Seule
 * la date d'arrêt se choisit, et la semaine entamée est comptée en entier.
 */
export function BlocPeriodeVariables({ year, month }: Props) {
  const { data: fenetre, isLoading } = usePeriodeVariables(year, month);
  const enregistrer = useEnregistrerPeriodeVariables(year, month);
  const [finSaisie, setFinSaisie] = useState<string>('');

  if (isLoading || !fenetre) return null;

  if (estSurLeMoisCivil(fenetre)) {
    return (
      <div className="rounded-md border p-3 space-y-1">
        <Label className="text-sm font-medium">Variables (heures sup et paniers)</Label>
        <p className="text-sm text-muted-foreground">
          Mois civil — du {formatFr(fenetre.mois_civil[0])} au{' '}
          {formatFr(fenetre.mois_civil[1])}.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border p-3 space-y-2">
      <Label className="text-sm font-medium">Variables (heures sup et paniers)</Label>

      <p className="text-sm">
        Du <strong>{formatFr(fenetre.debut)}</strong> au{' '}
        <strong>{formatFr(fenetre.fin)}</strong> — {libelleSemaines(fenetre.semaines)}.
      </p>
      <p className="text-xs text-muted-foreground">
        Le début est la suite du mois précédent et n'est pas modifiable.
      </p>

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Label htmlFor="fin-variables" className="text-xs">
            J'arrête les variables le
          </Label>
          <Input
            id="fin-variables"
            type="date"
            value={finSaisie || fenetre.fin}
            min={fenetre.debut}
            onChange={(e) => setFinSaisie(e.target.value)}
          />
        </div>
        <Button
          type="button"
          variant="secondary"
          disabled={enregistrer.isPending || !finSaisie || finSaisie === fenetre.fin}
          onClick={() => enregistrer.mutate(finSaisie)}
        >
          Appliquer
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        La semaine entamée est comptée en entier. Ce qui suit le{' '}
        {formatFr(fenetre.fin)} partira sur le mois suivant, à partir du{' '}
        {formatFr(fenetre.report_debut)}.
      </p>
    </div>
  );
}
