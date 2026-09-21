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
import { monthYearLabel } from '@/features/payroll/utils/payrollMonth';

interface Props {
  year: number;
  month: number;
  /** Bornes et semaines seulement ; « Modifier la fenêtre » déplie le réglage. */
  lectureSeule?: boolean;
}

/**
 * Fenêtre des heures sup et des paniers pour le mois lancé.
 *
 * Le début n'est pas modifiable : il est la suite du mois précédent, et c'est
 * ce qui garantit qu'aucune semaine n'est ni perdue ni payée deux fois. Seule
 * la date d'arrêt se choisit, et la semaine entamée est comptée en entier.
 *
 * La fenêtre est un réglage société-mois : depuis la fiche d'un salarié, on la
 * voit en lecture, et la modifier est annoncé comme valant pour toute la société.
 */
export function BlocPeriodeVariables({ year, month, lectureSeule = false }: Props) {
  const { data: fenetre, isLoading } = usePeriodeVariables(year, month);
  const enregistrer = useEnregistrerPeriodeVariables(year, month);
  const [finSaisie, setFinSaisie] = useState<string>('');
  const [modification, setModification] = useState(false);

  if (isLoading || !fenetre) return null;

  const aRegenerer = fenetre.bulletins_a_regenerer ?? 0;
  const mentionBulletins =
    aRegenerer > 0 ? (
      <p className="text-xs text-amber-700 dark:text-amber-500">
        {aRegenerer} bulletin{aRegenerer > 1 ? 's' : ''} déjà généré{aRegenerer > 1 ? 's' : ''}{' '}
        pour ce mois garde{aRegenerer > 1 ? 'nt' : ''} l'ancienne fenêtre : à régénérer.
      </p>
    ) : null;

  if (estSurLeMoisCivil(fenetre)) {
    return (
      <div className="rounded-md border p-3 space-y-1">
        <Label className="text-sm font-medium">Variables (heures sup et paniers)</Label>
        <p className="text-sm text-muted-foreground">
          Mois civil — du {formatFr(fenetre.mois_civil[0])} au{' '}
          {formatFr(fenetre.mois_civil[1])}.
        </p>
        {mentionBulletins}
      </div>
    );
  }

  if (lectureSeule && !modification) {
    return (
      <div className="rounded-md border p-3 space-y-2">
        <Label className="text-sm font-medium">Variables (heures sup et paniers)</Label>
        <p className="text-sm">
          Du <strong>{formatFr(fenetre.debut)}</strong> au{' '}
          <strong>{formatFr(fenetre.fin)}</strong> — {libelleSemaines(fenetre.semaines)}.
        </p>
        {mentionBulletins}
        <Button
          type="button"
          variant="link"
          className="h-auto p-0 text-xs"
          onClick={() => setModification(true)}
        >
          Modifier la fenêtre de {monthYearLabel(month, year)} (pour toute la société)
        </Button>
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
            max={fenetre.mois_civil[1]}
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

      {/* Changer la période ne recalcule rien : les bulletins déjà générés
          gardent celle qui était en vigueur au moment de leur génération.
          Le dire est plus sûr que de régénérer d'office — un bulletin validé
          ne doit pas se recalculer dans le dos de la gestionnaire de paie.
          Quand le serveur en compte, on donne le nombre. */}
      {mentionBulletins ?? (
        <p className="text-xs text-amber-700 dark:text-amber-500">
          Les bulletins déjà générés pour ce mois gardent l'ancienne période :
          régénérez-les pour appliquer celle-ci.
        </p>
      )}
    </div>
  );
}
