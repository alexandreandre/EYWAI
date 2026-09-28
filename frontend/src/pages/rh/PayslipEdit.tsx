// frontend/src/pages/rh/PayslipEdit.tsx

/**
 * Corriger un bulletin par ses variables du mois (audit du 28/09).
 *
 * L'écran ne retouche plus les lignes du bulletin : un montant retouché laissait
 * cotisations, net et cumuls de l'ancien calcul. On y corrige les heures sup et
 * les primes du mois, et les notes ; à l'enregistrement, le serveur écrit ces
 * variables puis recalcule tout le bulletin. Le reste se corrige à sa source
 * (planning, fiche, saisies), puis « Régénérer ».
 */

import { pageTitleClassName } from '@/components/layout';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Eye, History, Loader2, Save, Undo2 } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
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
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { SharkFinLoader } from '@/components/SharkFinLoader';

import {
  editPayslip,
  getPayslipDetails,
  isPayslipBlocMaintienPresent,
  validatePayslip,
  type PayslipDetail,
} from '@/api/payslips';
import { hasRhAccess, useAuth } from '@/contexts/AuthContext';
import { isPlatformAdmin } from '@/lib/platformAdmin';
import { queryKeys } from '@/lib/queryKeys';
import { cn } from '@/lib/utils';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

import CorrectionsBulletinPanel from '@/components/payslip-edit/CorrectionsBulletinPanel';
import HistoryPanel from '@/components/payslip-edit/HistoryPanel';
import NotesSection from '@/components/payslip-edit/NotesSection';
import PayslipPreviewFrame from '@/components/payslip-edit/PayslipPreviewFrame';
import RegeneratePayslipButton from '@/components/payslip-edit/RegeneratePayslipButton';
import { MaintenanceDetailModal } from '@/components/payslip/MaintenanceDetailModal';
import { PayslipAlertsBanner } from '@/components/payslip/PayslipAlertsBanner';
import { PayslipComparisonTab } from '@/components/payslip/PayslipComparisonTab';
import { PayslipTrendTab } from '@/components/payslip/PayslipTrendTab';
import { PayslipValidateBlockedModal } from '@/components/payslip/PayslipValidateBlockedModal';
import {
  aDesModifications,
  etatInitial,
  recalculAttendu,
  requeteDeCorrection,
  type EtatCorrections,
} from '@/features/payroll/utils/correctionsBulletin';
import { lienVariablesDuMois } from '@/features/payroll/utils/payslipDerivedLines';

const QUESTION_ABANDON = 'Vos corrections ne sont pas enregistrées. Les abandonner ?';

function isCriticalValidationBlock(err: unknown): boolean {
  const ax = err as { response?: { status?: number; data?: { detail?: unknown } } };
  if (ax.response?.status !== 400) return false;
  const detail = ax.response.data?.detail;
  return (
    typeof detail === 'object' &&
    detail !== null &&
    'critical_alerts' in detail &&
    Array.isArray((detail as { critical_alerts: unknown }).critical_alerts)
  );
}

function messageDErreur(error: unknown, parDefaut: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return 'Correction refusée : une valeur saisie est invalide.';
  return parDefaut;
}

function statutHttp(error: unknown): number | undefined {
  return (error as { response?: { status?: number } }).response?.status;
}

function dateCourte(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString('fr-FR');
}

export default function PayslipEdit() {
  const { payslipId } = useParams<{ payslipId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const companyId = useActiveCompanyId();

  const [payslip, setPayslip] = useState<PayslipDetail | null>(null);
  const [initial, setInitial] = useState<EtatCorrections | null>(null);
  const [etat, setEtat] = useState<EtatCorrections | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('corriger');
  const [confirmationValide, setConfirmationValide] = useState(false);
  const [validateModalOpen, setValidateModalOpen] = useState(false);
  const [validateBusy, setValidateBusy] = useState(false);
  const [showMaintienModal, setShowMaintienModal] = useState(false);

  const appliquer = useCallback((data: PayslipDetail) => {
    const depart = etatInitial(data.payslip_data, data.pdf_notes);
    setPayslip(data);
    setInitial(depart);
    setEtat(depart);
  }, []);

  const recharger = useCallback(async () => {
    if (!payslipId) return;
    appliquer(await getPayslipDetails(payslipId));
  }, [payslipId, appliquer]);

  // Les listes de bulletins (paie, fiche salarié) sont en cache : sans cela,
  // elles montraient l'ancien net après une correction.
  const invaliderListes = useCallback(() => {
    if (!payslip) return;
    void queryClient.invalidateQueries({
      queryKey: queryKeys.employeePayslips(companyId, payslip.employee_id),
    });
  }, [queryClient, companyId, payslip]);

  const apresChangement = useCallback(async () => {
    await recharger();
    invaliderListes();
  }, [recharger, invaliderListes]);

  useEffect(() => {
    if (!payslipId) {
      navigate('/');
      return;
    }
    const charger = async () => {
      setIsLoading(true);
      try {
        appliquer(await getPayslipDetails(payslipId));
      } catch (error) {
        toast({
          title: 'Erreur',
          description: messageDErreur(error, 'Impossible de charger le bulletin'),
          variant: 'destructive',
        });
        navigate('/payroll');
      } finally {
        setIsLoading(false);
      }
    };
    void charger();
  }, [payslipId, navigate, toast, appliquer]);

  const modifie = initial && etat ? aDesModifications(initial, etat) : false;
  const recalculPrevu = initial && etat ? recalculAttendu(initial, etat) : false;

  useEffect(() => {
    const avantDeQuitter = (e: BeforeUnloadEvent) => {
      if (modifie) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', avantDeQuitter);
    return () => window.removeEventListener('beforeunload', avantDeQuitter);
  }, [modifie]);

  /** Faux si la RH préfère garder ses corrections en cours. */
  const abandonnerSiBesoin = useCallback(
    () => !modifie || window.confirm(QUESTION_ABANDON),
    [modifie]
  );

  const aller = (lien: string) => {
    if (abandonnerSiBesoin()) navigate(lien);
  };

  const enregistrer = async () => {
    if (!payslipId || !payslip || !initial || !etat) return;
    setConfirmationValide(false);
    setIsSaving(true);
    try {
      const reponse = await editPayslip(
        payslipId,
        requeteDeCorrection(initial, etat, payslip.updated_at)
      );
      if (reponse.recalcul_erreur) {
        toast({
          title: 'Corrections enregistrées, bulletin non recalculé',
          description: `${reponse.recalcul_erreur} — utilisez « Régénérer ».`,
          variant: 'destructive',
        });
      } else if (reponse.recalcule) {
        toast({
          title: 'Bulletin corrigé et recalculé',
          description: 'Brut, cotisations, net et cumuls ont suivi la correction.',
        });
      } else {
        toast({ title: 'Notes enregistrées' });
      }
      await apresChangement();
    } catch (error) {
      if (statutHttp(error) === 409) {
        toast({
          title: 'Le bulletin a changé depuis son ouverture',
          description: 'Il a été rechargé : refaites vos corrections sur la version à jour.',
          variant: 'destructive',
        });
        await recharger();
      } else {
        toast({
          title: 'Correction impossible',
          description: messageDErreur(error, 'Impossible d’enregistrer les corrections'),
          variant: 'destructive',
        });
      }
    } finally {
      setIsSaving(false);
    }
  };

  const demanderEnregistrement = () => {
    if (payslip?.status === 'valide') setConfirmationValide(true);
    else void enregistrer();
  };

  const valider = async () => {
    if (!payslipId || !abandonnerSiBesoin()) return;
    setValidateBusy(true);
    try {
      appliquer(await validatePayslip(payslipId));
      invaliderListes();
      toast({ title: 'Bulletin validé', description: 'Le statut du bulletin a été mis à jour.' });
    } catch (error) {
      if (isCriticalValidationBlock(error)) {
        setValidateModalOpen(true);
      } else {
        toast({
          title: 'Validation impossible',
          description: messageDErreur(error, 'Impossible de valider le bulletin'),
          variant: 'destructive',
        });
      }
    } finally {
      setValidateBusy(false);
    }
  };

  if (isLoading) {
    return <SharkFinLoader variant="fullPage" label="Chargement du bulletin…" />;
  }
  if (!payslip || !initial || !etat) {
    return null;
  }

  const isRH = hasRhAccess(user, payslip.company_id);
  const isEditLocked = Boolean(payslip.manual_edit_locked);
  const showAdminOverride =
    Boolean(payslip.period_edit_locked) && isPlatformAdmin(user) && !isEditLocked;
  const statut = payslip.status ?? 'brouillon';
  const recalculEnAttente = payslip.payslip_data?.recalcul_en_attente ?? null;
  const exportsDuMois = payslip.exports_du_mois ?? [];
  const validationBloquee = Boolean(recalculEnAttente || payslip.a_regenerer);
  const lienSaisies = lienVariablesDuMois({
    employeeId: payslip.employee_id,
    year: payslip.year,
    month: payslip.month,
  });

  return (
    <div className="container mx-auto space-y-6">
      <PayslipAlertsBanner data={payslip.payslip_data} />

      {recalculEnAttente ? (
        <Alert variant="destructive" data-testid="recalcul-en-attente">
          <AlertTitle>Bulletin non recalculé</AlertTitle>
          <AlertDescription>
            Les dernières corrections sont enregistrées, mais le recalcul a échoué (
            {recalculEnAttente.erreur}). Régénérez le bulletin avant de le valider.
          </AlertDescription>
        </Alert>
      ) : null}

      {payslip.a_regenerer ? (
        <Alert data-testid="a-regenerer">
          <AlertTitle>À régénérer</AlertTitle>
          <AlertDescription>{payslip.a_regenerer}</AlertDescription>
        </Alert>
      ) : null}

      {exportsDuMois.length > 0 ? (
        <Alert data-testid="exports-du-mois">
          <AlertTitle>Déjà exporté pour ce mois</AlertTitle>
          <AlertDescription>
            {exportsDuMois.map((e) => `${e.libelle} (${dateCourte(e.date)})`).join(' · ')}. Après une
            correction, refaites ces exports.
          </AlertDescription>
        </Alert>
      ) : null}

      {isEditLocked && payslip.manual_edit_lock_reason ? (
        <Alert variant="destructive">
          <AlertTitle>Correction verrouillée</AlertTitle>
          <AlertDescription>{payslip.manual_edit_lock_reason}</AlertDescription>
        </Alert>
      ) : null}

      {showAdminOverride ? (
        <Alert>
          <AlertTitle>Override administrateur</AlertTitle>
          <AlertDescription>
            La période est normalement verrouillée pour les RH, mais vous pouvez encore corriger ce
            bulletin en tant qu&apos;administrateur plateforme.
          </AlertDescription>
        </Alert>
      ) : null}

      {!isEditLocked && payslip.manual_edit_lock_until ? (
        <Alert>
          <AlertDescription>
            Correction autorisée jusqu&apos;au{' '}
            {new Date(payslip.manual_edit_lock_until).toLocaleDateString('fr-FR')}.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            onClick={() => {
              if (abandonnerSiBesoin()) navigate(-1);
            }}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
          <div>
            <h1 className={pageTitleClassName}>Corriger le bulletin - {payslip.name}</h1>
            <p className="text-muted-foreground">
              Les corrections deviennent des variables du mois ; le bulletin est recalculé en entier.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {statut === 'valide' ? (
            <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">
              Bulletin validé
              {payslip.validated_at
                ? ` · ${new Date(payslip.validated_at).toLocaleString('fr-FR')}`
                : ''}
            </Badge>
          ) : isRH ? (
            <Button
              type="button"
              className="bg-sky-600 text-white hover:bg-sky-700"
              onClick={() => void valider()}
              disabled={validateBusy || validationBloquee}
              title={validationBloquee ? 'Régénérez le bulletin avant de le valider' : undefined}
            >
              {validateBusy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Valider le bulletin
            </Button>
          ) : null}
          <RegeneratePayslipButton
            employeeId={payslip.employee_id}
            year={payslip.year}
            month={payslip.month}
            manuallyEdited={payslip.manually_edited}
            modificationsNonEnregistrees={modifie}
            disabled={isEditLocked}
            onRegenerated={apresChangement}
          />
          <Button variant="outline" onClick={() => setActiveTab('bulletin')}>
            <Eye className="h-4 w-4 mr-2" />
            Bulletin
          </Button>
          <Button variant="outline" onClick={() => setActiveTab('historique')}>
            <History className="h-4 w-4 mr-2" />
            Historique
          </Button>
          <Button
            onClick={demanderEnregistrement}
            disabled={isSaving || !modifie || isEditLocked}
            data-testid="enregistrer-entete"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            {recalculPrevu || !modifie ? 'Enregistrer et recalculer' : 'Enregistrer les notes'}
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className={cn('grid h-auto w-full gap-1 p-1', 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5')}>
          <TabsTrigger value="corriger">Corriger</TabsTrigger>
          <TabsTrigger value="bulletin">Bulletin</TabsTrigger>
          <TabsTrigger value="historique">Historique</TabsTrigger>
          <TabsTrigger value="comparaison">Comparaison N-1</TabsTrigger>
          <TabsTrigger value="tendance">Tendance</TabsTrigger>
        </TabsList>

        <TabsContent value="corriger" className="space-y-6 mt-6">
          <fieldset disabled={isEditLocked} className="space-y-6 border-0 p-0 m-0 min-w-0">
            <CorrectionsBulletinPanel
              payslipData={payslip.payslip_data}
              etat={etat}
              onChange={setEtat}
              disabled={isEditLocked}
              employeeId={payslip.employee_id}
              year={payslip.year}
              month={payslip.month}
              lienPlanning={`/schedules?employee=${encodeURIComponent(payslip.employee_id)}`}
              lienFiche={`/employees/${encodeURIComponent(payslip.employee_id)}`}
              lienSaisies={lienSaisies}
              onAller={aller}
            />
            <NotesSection
              pdfNotes={etat.pdfNotes}
              internalNote={etat.noteInterne}
              internalNotes={payslip.internal_notes ?? []}
              changesSummary={etat.resume}
              onPdfNotesChange={(pdfNotes) => setEtat({ ...etat, pdfNotes })}
              onInternalNoteChange={(noteInterne) => setEtat({ ...etat, noteInterne })}
              onChangesSummaryChange={(resume) => setEtat({ ...etat, resume })}
            />
          </fieldset>
        </TabsContent>

        <TabsContent value="bulletin" className="mt-6 space-y-4">
          {isPayslipBlocMaintienPresent(payslip.payslip_data?.bloc_maintien) ? (
            <Button variant="outline" size="sm" onClick={() => setShowMaintienModal(true)}>
              Détail du maintien de salaire
            </Button>
          ) : null}
          {/* Clé : l'aperçu se refait après chaque rechargement du bulletin. */}
          <PayslipPreviewFrame
            key={payslip.updated_at ?? payslip.id}
            payslipId={payslip.id}
            pdfNotes={etat.pdfNotes}
          />
        </TabsContent>

        <TabsContent value="historique" className="mt-6">
          <HistoryPanel
            key={payslip.updated_at ?? payslip.id}
            payslipId={payslip.id}
            canRestore={!isEditLocked}
            avantRestauration={abandonnerSiBesoin}
            onRestore={() => {
              void apresChangement();
              setActiveTab('corriger');
            }}
          />
        </TabsContent>

        <TabsContent value="comparaison" className="mt-0">
          <PayslipComparisonTab
            payslipId={payslip.id}
            isRH={isRH}
            onShowTrend={() => setActiveTab('tendance')}
            onPayslipRefresh={apresChangement}
          />
        </TabsContent>

        <TabsContent value="tendance" className="mt-0">
          <PayslipTrendTab
            payslipId={payslip.id}
            referenceYear={payslip.year}
            referenceMonth={payslip.month}
          />
        </TabsContent>
      </Tabs>

      <AlertDialog open={confirmationValide} onOpenChange={setConfirmationValide}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Corriger un bulletin validé ?</AlertDialogTitle>
            <AlertDialogDescription>
              Il repassera en brouillon : le salarié ne le verra plus tant qu’il n’aura pas été
              revalidé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSaving}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              disabled={isSaving}
              onClick={(e) => {
                e.preventDefault();
                void enregistrer();
              }}
            >
              Corriger et repasser en brouillon
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <PayslipValidateBlockedModal
        open={validateModalOpen}
        onOpenChange={setValidateModalOpen}
        payslipId={payslip.id}
        isRH={isRH}
        onValidated={apresChangement}
      />

      {isPayslipBlocMaintienPresent(payslip.payslip_data?.bloc_maintien) ? (
        <MaintenanceDetailModal
          open={showMaintienModal}
          onClose={() => setShowMaintienModal(false)}
          maintien={payslip.payslip_data.bloc_maintien}
        />
      ) : null}

      {/* Barre fixe : où qu'elle soit dans la page, la RH voit qu'il reste à
          enregistrer (le 12/09, des heures corrigées n'avaient jamais été
          enregistrées, le bouton du haut étant hors de vue). */}
      {modifie && !isEditLocked ? (
        <>
          <div className="h-24" aria-hidden="true" />
          <div
            data-testid="barre-enregistrement"
            className="fixed inset-x-0 bottom-0 z-40 border-t border-orange-300 bg-orange-50 shadow-[0_-4px_16px_rgba(0,0,0,0.08)]"
          >
            <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-orange-900">
                <p className="font-semibold">Corrections non enregistrées</p>
                <p className="text-orange-800">
                  {recalculPrevu
                    ? 'À l’enregistrement, le bulletin est recalculé en entier : brut, cotisations, net et cumuls.'
                    : 'Seules les notes changent : le bulletin n’est pas recalculé.'}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setEtat(initial)} disabled={isSaving}>
                  <Undo2 className="h-4 w-4 mr-2" />
                  Annuler les corrections
                </Button>
                <Button onClick={demanderEnregistrement} disabled={isSaving} data-testid="enregistrer-barre">
                  {isSaving ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  {recalculPrevu ? 'Enregistrer et recalculer' : 'Enregistrer les notes'}
                </Button>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
