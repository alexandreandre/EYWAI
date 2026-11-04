import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { CheckCheck, Loader2 } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { getCompanySettings } from '@/api/company';
import { validerBulletinsPrets } from '@/api/payslips';
import { queryKeys } from '@/lib/queryKeys';
import { toast } from '@/hooks/use-toast';
import { accord, pluriel } from '@/lib/pluriel';
import { showErrorToast } from '@/lib/errorMessages';
import {
  libelleBoutonValider,
  resumeValidationGroupee,
  type RefusNomme,
} from '@/features/payroll/utils/validationGroupee';
import {
  dateDuJourAParis,
  jourDeMiseADisposition,
  textesRemiseDuLot,
} from '@/features/payroll/utils/remiseALaValidation';
import { deDevant } from '@/features/payroll/utils/elision';

type Props = {
  /** Bulletins prêts du mois : générés, à jour, sans alerte ni écart fort, non validés. */
  idsPrets: string[];
  /** Nom du salarié de chaque bulletin du mois, pour nommer les refus. */
  nomParBulletin: Readonly<Record<string, string>>;
  companyId: string | null | undefined;
  titreMois: string;
  /** Mois de paie du lot : la remise se compte depuis le mois suivant. */
  annee: number;
  mois: number;
  /** Bulletins de sortie parmi les prêts : remis dès leur validation. */
  idsSortie?: readonly string[];
  /** Mois précédent à recalculer pour certains salariés : dit sans bloquer. */
  avertissement?: string | null;
  disabled?: boolean;
  /** Pourquoi le bouton est grisé quand `disabled` (ex. calcul en cours). */
  raisonDesactive?: string | null;
  /** Pourquoi rien n'est prêt (« 2 à revoir, 1 à générer ») : le bouton reste visible, grisé. */
  raisonRienAValider?: string | null;
  /** Recharge les bulletins du mois, réussite ou échec. */
  onTermine: () => Promise<void> | void;
};

/** Bouton « Valider les bulletins prêts (n) », sa confirmation et le récapitulatif des refus. */
export function ValiderBulletinsPrets({
  idsPrets,
  nomParBulletin,
  companyId,
  titreMois,
  annee,
  mois,
  idsSortie = [],
  avertissement = null,
  disabled = false,
  raisonDesactive = null,
  raisonRienAValider = null,
  onTermine,
}: Props) {
  const [confirmation, setConfirmation] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [recap, setRecap] = useState<{
    titre: string;
    refus: RefusNomme[];
    valides: string[];
    /** Quand les validés seront visibles, dit au moment de la validation. */
    remise: string[];
  } | null>(null);

  // Le jour de remise réglé par la société (onglet « Paramètres paie ») ; illisible,
  // la fenêtre ne promet aucune date.
  const reglages = useQuery({
    queryKey: queryKeys.companySettings(companyId ?? undefined),
    queryFn: getCompanySettings,
    enabled: Boolean(companyId),
  });
  const jour = reglages.data ? jourDeMiseADisposition(reglages.data.settings) : null;
  const nomsSortie = (ids: readonly string[]) =>
    ids.filter((id) => idsSortie.includes(id)).map((id) => nomParBulletin[id] ?? 'un salarié');
  // Validés aujourd'hui (jour de Paris) : la même date que celle du serveur.
  const textesDuLot = (ids: readonly string[]) =>
    textesRemiseDuLot({
      annee,
      mois,
      jour,
      aujourdhui: dateDuJourAParis(),
      nombre: ids.length,
      sorties: nomsSortie(ids),
    });
  const lignesDuLot = (ids: readonly string[]) => {
    const textes = textesDuLot(ids);
    return [textes.phrase, textes.ligneSortie].filter((t): t is string => Boolean(t));
  };
  const textesConfirmation = textesDuLot(idsPrets);

  const rienAValider = idsPrets.length === 0 && !enCours;
  // Le bouton ne disparaît plus : grisé, il dit pourquoi (jamais d'état silencieux).
  const raison = enCours
    ? null
    : rienAValider
      ? (raisonRienAValider ?? 'Aucun bulletin prêt à valider.')
      : disabled
        ? raisonDesactive
        : null;

  const valider = async () => {
    setConfirmation(false);
    setEnCours(true);
    try {
      const resultat = await validerBulletinsPrets(idsPrets, companyId);
      const resume = resumeValidationGroupee(resultat, nomParBulletin);
      const remise = lignesDuLot(resultat.valides);
      if (resume.refus.length > 0) {
        setRecap({ ...resume, remise });
      } else {
        toast({
          title: resume.titre,
          description: remise.length > 0 ? [`${titreMois} :`, ...remise].join(' ') : undefined,
        });
      }
    } catch (error) {
      showErrorToast(error, {
        title: 'Validation interrompue',
        fallback:
          'La validation n’a pas abouti. La liste est rechargée : les bulletins qui portent « Validé » le sont, relancez pour les autres.',
      });
    } finally {
      await onTermine();
      setEnCours(false);
    }
  };

  return (
    <>
      <Button
        size="sm"
        className="gap-1.5 bg-sky-600 text-white hover:bg-sky-700"
        disabled={disabled || enCours || rienAValider}
        aria-describedby={raison ? 'valider-bulletins-prets-raison' : undefined}
        onClick={() => {
          setConfirmation(true);
          void reglages.refetch();
        }}
        data-testid="valider-bulletins-prets"
      >
        {enCours ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <CheckCheck className="h-3.5 w-3.5" aria-hidden />
        )}
        {enCours ? 'Validation en cours…' : libelleBoutonValider(idsPrets.length)}
      </Button>
      {raison ? (
        <p
          id="valider-bulletins-prets-raison"
          className="text-xs text-muted-foreground"
          data-testid="valider-bulletins-prets-raison"
        >
          {raison}
        </p>
      ) : null}

      <AlertDialog open={confirmation} onOpenChange={setConfirmation}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Valider {pluriel(idsPrets.length, 'bulletin')}{' '}
              {deDevant(titreMois.charAt(0).toLowerCase() + titreMois.slice(1))} ?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Ce sont les bulletins générés, à jour, sans alerte ni écart fort avec le mois
              précédent. Les bulletins à revoir ne sont pas validés : ouvrez-les un par un.
            </AlertDialogDescription>
            {textesConfirmation.phrase ? (
              <p className="text-sm font-medium" data-testid="validation-remise">
                {textesConfirmation.phrase}
              </p>
            ) : null}
            {textesConfirmation.ligneSortie ? (
              <p className="text-sm" data-testid="validation-remise-sortie">
                {textesConfirmation.ligneSortie}
              </p>
            ) : null}
            {avertissement ? (
              <p className="text-sm text-amber-700" data-testid="validation-mois-precedent">
                {avertissement}
              </p>
            ) : null}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={() => void valider()}>Valider</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={recap !== null} onOpenChange={(open) => !open && setRecap(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{recap?.titre}</DialogTitle>
            <DialogDescription>
              Ces bulletins ne sont pas validés. Ouvrez chacun, réglez ce qui est dit, puis
              validez-le depuis son écran.
            </DialogDescription>
          </DialogHeader>
          <ul className="max-h-[50vh] space-y-2 overflow-y-auto text-sm" data-testid="refus-validation">
            {recap?.refus.map((r) => (
              <li key={r.payslipId} className="rounded-md border px-3 py-2">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium">{r.nom}</span>
                  <Link
                    to={`/payslips/${r.payslipId}/edit`}
                    className="shrink-0 text-xs font-medium text-primary hover:underline"
                  >
                    Ouvrir le bulletin
                  </Link>
                </div>
                <p className="text-xs text-muted-foreground">{r.raison}</p>
              </li>
            ))}
          </ul>
          {recap && recap.valides.length > 0 ? (
            <div className="space-y-1 text-sm" data-testid="valides-validation">
              <p className="font-medium">
                {pluriel(recap.valides.length, 'bulletin')} {accord(recap.valides.length, 'validé')}
              </p>
              <p className="text-xs text-muted-foreground">{recap.valides.join(', ')}</p>
              {recap.remise.map((t) => (
                <p key={t} className="text-xs" data-testid="valides-remise">
                  {t}
                </p>
              ))}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setRecap(null)}>
              Fermer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
