// frontend/src/components/payslip-edit/RegeneratePayslipButton.tsx

/**
 * Régénère le bulletin affiché en repassant par le moteur de paie.
 *
 * Raison d'être : l'écran d'édition corrige le brut ligne à ligne sans toucher
 * aux cotisations ni au net. Après avoir corrigé une variable du mois (heures
 * supplémentaires, panier), il faut refaire calculer le bulletin — sinon le
 * brut et le net ne collent plus. Ce bouton évite de ressortir vers la page de
 * génération pour un seul salarié.
 *
 * Les deux gardes du backend sont respectées : on ne force jamais sans une
 * confirmation explicite (422 calendrier incomplet, 409 bulletin validé).
 */

import { useState } from 'react';
import { RefreshCw, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
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
import { useToast } from '@/components/ui/use-toast';
import { generatePayslip } from '@/api/payslips';
import { getPayrollGenerationErrorMessage } from '@/lib/errorMessages';
import {
  extractGenerationRefusal,
  splitGenerationWarnings,
  REFUSAL_DIALOG_LABELS,
  type GenerationRefusal,
} from '@/features/payroll/utils/generationGuards';

type ForcageGeneration = {
  force_calendrier_incomplet?: boolean;
  regenerer_bulletin_valide?: boolean;
};

interface RegeneratePayslipButtonProps {
  employeeId: string;
  year: number;
  month: number;
  /** Le bulletin porte des retouches manuelles : la régénération les écrase. */
  manuallyEdited: boolean;
  disabled?: boolean;
  /** Recharge le bulletin depuis le serveur après une régénération réussie. */
  onRegenerated: () => Promise<void> | void;
}

export default function RegeneratePayslipButton({
  employeeId,
  year,
  month,
  manuallyEdited,
  disabled,
  onRegenerated,
}: RegeneratePayslipButtonProps) {
  const { toast } = useToast();
  const [confirmationOuverte, setConfirmationOuverte] = useState(false);
  const [refus, setRefus] = useState<GenerationRefusal | null>(null);
  const [enCours, setEnCours] = useState(false);

  const lancer = async (forcage: ForcageGeneration = {}) => {
    setEnCours(true);
    try {
      const reponse = await generatePayslip({
        employee_id: employeeId,
        year,
        month,
        ...forcage,
      });

      setConfirmationOuverte(false);
      setRefus(null);

      const { messages } = splitGenerationWarnings(reponse.warnings);
      toast({
        title: 'Bulletin régénéré',
        description:
          messages.length > 0
            ? messages.join(' · ')
            : 'Brut, cotisations et net ont été recalculés.',
      });

      await onRegenerated();
    } catch (error) {
      const refusStructure = extractGenerationRefusal(error);
      if (refusStructure) {
        // Le backend refuse et dit pourquoi : on demande confirmation avant de forcer.
        setConfirmationOuverte(false);
        setRefus(refusStructure);
        return;
      }
      toast({
        title: 'Régénération impossible',
        description: getPayrollGenerationErrorMessage(error),
        variant: 'destructive',
      });
    } finally {
      setEnCours(false);
    }
  };

  const forcageDuRefus = (): ForcageGeneration =>
    refus?.code === 'calendrier_incomplet'
      ? { force_calendrier_incomplet: true }
      : { regenerer_bulletin_valide: true };

  return (
    <>
      <Button
        type="button"
        variant="outline"
        data-testid="regenerer-bulletin"
        disabled={disabled || enCours}
        onClick={() => setConfirmationOuverte(true)}
      >
        {enCours ? (
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        ) : (
          <RefreshCw className="h-4 w-4 mr-2" />
        )}
        Régénérer
      </Button>

      <AlertDialog open={confirmationOuverte} onOpenChange={setConfirmationOuverte}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Régénérer ce bulletin ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le moteur recalcule le bulletin depuis les variables du mois, le
              calendrier et le contrat : brut, cotisations et net redeviennent
              cohérents.
              {manuallyEdited
                ? ' Ce bulletin porte des modifications manuelles : elles seront remplacées par le calcul.'
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={enCours}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              disabled={enCours}
              onClick={(e) => {
                e.preventDefault();
                void lancer();
              }}
            >
              Régénérer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={refus !== null} onOpenChange={(ouvert) => !ouvert && setRefus(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {refus ? REFUSAL_DIALOG_LABELS[refus.code].title : ''}
            </AlertDialogTitle>
            <AlertDialogDescription>{refus?.message}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={enCours}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              disabled={enCours}
              onClick={(e) => {
                e.preventDefault();
                void lancer(forcageDuRefus());
              }}
            >
              {refus ? REFUSAL_DIALOG_LABELS[refus.code].actionLabel : ''}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
