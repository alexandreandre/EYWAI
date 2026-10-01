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
import { BlocPeriodeVariables } from '@/features/payroll/components/BlocPeriodeVariables';
import { JoursASaisirListe } from '@/features/payroll/components/JoursASaisirListe';
import {
  ChoixHeuresSurArret,
  HeuresSurArretSansJours,
} from '@/features/payroll/components/ChoixHeuresSurArret';
import {
  etatDialogueHeuresSurArret,
  type JourEnConflit,
  type RefusApresCorrection,
  type SuiteEffacement,
} from '@/features/payroll/utils/heuresSurArret';
import {
  estForcable,
  extractGenerationRefusal,
  splitGenerationWarnings,
  REFUSAL_DIALOG_LABELS,
  type GenerationRefusal,
} from '@/features/payroll/utils/generationGuards';
import {
  messageRegenereNonRecharge,
  regenererPuisRecharger,
} from '@/features/payroll/utils/regenerationBulletin';

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
  /** Des corrections sont en cours sur l'écran : la régénération les abandonne. */
  modificationsNonEnregistrees?: boolean;
  /** Nom complet du salarié, s'il est connu (prénom des boutons de correction). */
  employeeName?: string | null;
  /**
   * Refus d'heures sur un arrêt déjà connu (venu d'une correction de bulletin) :
   * le dialogue du choix s'ouvre tout de suite, sans relancer une génération.
   */
  refusInitial?: RefusApresCorrection | null;
  /** Appelé quand le dialogue de ce refus initial se ferme, sans autre effet. */
  onRefusInitialFerme?: () => void;
  disabled?: boolean;
  /** Recharge le bulletin depuis le serveur après une régénération réussie. */
  onRegenerated: () => Promise<void> | void;
}

export default function RegeneratePayslipButton({
  employeeId,
  year,
  month,
  manuallyEdited,
  modificationsNonEnregistrees = false,
  employeeName,
  refusInitial,
  onRefusInitialFerme,
  disabled,
  onRegenerated,
}: RegeneratePayslipButtonProps) {
  const { toast } = useToast();
  const [confirmationOuverte, setConfirmationOuverte] = useState(false);
  const [refusLocal, setRefus] = useState<GenerationRefusal | null>(null);
  const refus: GenerationRefusal | null =
    refusLocal ??
    (refusInitial
      ? {
          code: 'heures_sur_jour_d_arret',
          message: refusInitial.message,
          jours: refusInitial.jours,
        }
      : null);
  // Heures effacées mais régénération en échec : le dialogue le dit et propose de relancer.
  const [suiteEffacement, setSuiteEffacement] = useState<SuiteEffacement | null>(null);
  const etatHeures =
    refus?.code === 'heures_sur_jour_d_arret'
      ? etatDialogueHeuresSurArret(refus.jours, suiteEffacement)
      : null;
  const fermerRefus = () => {
    setRefus(null);
    setSuiteEffacement(null);
    onRefusInitialFerme?.();
  };
  const [enCours, setEnCours] = useState(false);

  /** `effaces` : relance après un effacement ; un échec reste alors dans le dialogue. */
  const lancer = async (forcage: ForcageGeneration = {}, effaces: JourEnConflit[] = []) => {
    setEnCours(true);
    try {
      const issue = await regenererPuisRecharger(
        () => generatePayslip({ employee_id: employeeId, year, month, ...forcage }),
        onRegenerated
      );
      if (issue.kind === 'echec') {
        signalerEchec(issue.erreur, effaces);
        return;
      }

      setConfirmationOuverte(false);
      fermerRefus();

      const { messages, infos } = splitGenerationWarnings(issue.reponse.warnings);
      const details = [...messages, ...infos];
      toast({
        title: 'Bulletin régénéré',
        description:
          details.length > 0 ? details.join(' · ') : 'Brut, cotisations et net ont été recalculés.',
      });
      if (issue.kind === 'regenere_non_recharge') {
        toast({ ...messageRegenereNonRecharge(), variant: 'destructive' });
      }
    } finally {
      setEnCours(false);
    }
  };

  const signalerEchec = (error: unknown, effaces: JourEnConflit[]) => {
    const refusStructure = extractGenerationRefusal(error);
    if (refusStructure) {
      // Le backend refuse et dit pourquoi : on demande confirmation avant de forcer.
      setConfirmationOuverte(false);
      setSuiteEffacement(null);
      setRefus(refusStructure);
      return;
    }
    if (effaces.length > 0) {
      setSuiteEffacement({
        effaces,
        echecGeneration: getPayrollGenerationErrorMessage(error),
      });
      return;
    }
    toast({
      title: 'Régénération impossible',
      description: getPayrollGenerationErrorMessage(error),
      variant: 'destructive',
    });
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
              {modificationsNonEnregistrees
                ? ' Vos corrections non enregistrées seront abandonnées.'
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {/* La fenêtre des variables se voit ici aussi : c'est elle que le
              moteur lit pour les heures sup, pas le mois civil. */}
          <BlocPeriodeVariables year={year} month={month} lectureSeule />
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

      <AlertDialog open={refus !== null} onOpenChange={(ouvert) => !ouvert && fermerRefus()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {etatHeures?.kind === 'generation_en_echec'
                ? etatHeures.titre
                : refus
                  ? REFUSAL_DIALOG_LABELS[refus.code].title
                  : ''}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {etatHeures?.kind === 'generation_en_echec'
                ? etatHeures.confirmation
                : refus?.message}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {refus?.code === 'calendrier_incomplet' && refus.details && (
            <JoursASaisirListe
              details={refus.details}
              lienPlanning={`/schedules?employee=${encodeURIComponent(employeeId)}`}
            />
          )}
          {etatHeures?.kind === 'choix' && (
            <ChoixHeuresSurArret
              employeeId={employeeId}
              employeeName={employeeName}
              jours={etatHeures.jours}
              onEffacees={async (effaces) => {
                // Les heures sont effacées : on relance la génération de CE bulletin.
                await lancer({}, effaces);
              }}
              onModifier={fermerRefus}
            />
          )}
          {etatHeures?.kind === 'sans_jours' && (
            <HeuresSurArretSansJours employeeId={employeeId} onOuvrir={fermerRefus} />
          )}
          {etatHeures?.kind === 'generation_en_echec' && (
            <p role="alert" className="text-sm text-destructive" data-testid="echec-regeneration">
              {etatHeures.echec}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={enCours}>
              {refus?.code === 'heures_sur_jour_d_arret' ? 'Fermer' : 'Annuler'}
            </AlertDialogCancel>
            {etatHeures?.kind === 'generation_en_echec' && suiteEffacement && (
              <AlertDialogAction
                disabled={enCours}
                onClick={(e) => {
                  e.preventDefault();
                  void lancer({}, suiteEffacement.effaces);
                }}
              >
                {enCours ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                {etatHeures.actionRelancer}
              </AlertDialogAction>
            )}
            {refus && refus.code !== 'heures_sur_jour_d_arret' && (
              <AlertDialogAction
                disabled={enCours}
                onClick={(e) => {
                  e.preventDefault();
                  // Forçable : on reposte avec le forçage. Arrêts illisibles : simple nouvel essai.
                  void lancer(estForcable(refus.code) ? forcageDuRefus() : {});
                }}
              >
                {REFUSAL_DIALOG_LABELS[refus.code].actionLabel}
              </AlertDialogAction>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
