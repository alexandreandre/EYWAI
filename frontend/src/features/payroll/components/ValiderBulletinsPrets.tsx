import { useState } from 'react';
import { Link } from 'react-router-dom';
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
import { validerBulletinsPrets } from '@/api/payslips';
import { toast } from '@/hooks/use-toast';
import { showErrorToast } from '@/lib/errorMessages';
import {
  libelleBoutonValider,
  resumeValidationGroupee,
  type RefusNomme,
} from '@/features/payroll/utils/validationGroupee';

type Props = {
  /** Bulletins prêts du mois : générés, à jour, sans alerte ni écart fort, non validés. */
  idsPrets: string[];
  /** Nom du salarié de chaque bulletin du mois, pour nommer les refus. */
  nomParBulletin: Readonly<Record<string, string>>;
  companyId: string | null | undefined;
  titreMois: string;
  disabled?: boolean;
  /** Recharge les bulletins du mois, réussite ou échec. */
  onTermine: () => Promise<void> | void;
};

/** Bouton « Valider les bulletins prêts (n) », sa confirmation et le récapitulatif des refus. */
export function ValiderBulletinsPrets({
  idsPrets,
  nomParBulletin,
  companyId,
  titreMois,
  disabled = false,
  onTermine,
}: Props) {
  const [confirmation, setConfirmation] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [recap, setRecap] = useState<{ titre: string; refus: RefusNomme[] } | null>(null);

  if (idsPrets.length === 0 && !enCours && !recap) return null;

  const valider = async () => {
    setConfirmation(false);
    setEnCours(true);
    try {
      const resultat = await validerBulletinsPrets(idsPrets, companyId);
      const resume = resumeValidationGroupee(resultat, nomParBulletin);
      if (resume.refus.length > 0) {
        setRecap(resume);
      } else {
        toast({ title: resume.titre, description: `${titreMois} : les salariés voient leur bulletin.` });
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
      {idsPrets.length > 0 || enCours ? (
        <Button
          size="sm"
          className="gap-1.5 bg-sky-600 text-white hover:bg-sky-700"
          disabled={disabled || enCours}
          onClick={() => setConfirmation(true)}
          data-testid="valider-bulletins-prets"
        >
          {enCours ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <CheckCheck className="h-3.5 w-3.5" aria-hidden />
          )}
          {enCours ? 'Validation en cours…' : libelleBoutonValider(idsPrets.length)}
        </Button>
      ) : null}

      <AlertDialog open={confirmation} onOpenChange={setConfirmation}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Valider {idsPrets.length} bulletin{idsPrets.length > 1 ? 's' : ''} de {titreMois} ?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Ce sont les bulletins générés, à jour, sans alerte ni écart fort avec le mois
              précédent. Chaque salarié verra son bulletin dans son espace et en sera prévenu. Les
              bulletins à revoir ne sont pas validés : ouvrez-les un par un.
            </AlertDialogDescription>
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
