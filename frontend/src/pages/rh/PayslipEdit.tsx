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

import { dateEnClair, dateHeureEnClair } from '@/components/payslip/comparaisonAffichage';
import { pageTitleClassName } from '@/components/layout';
import { useCallback, useEffect, useMemo, useState } from 'react';
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
import { getEmployeeMonthlyInputs } from '@/api/saisies';
import { hasRhAccess, useAuth } from '@/contexts/AuthContext';
import { isPlatformAdmin } from '@/lib/platformAdmin';
import { cn } from '@/lib/utils';
import { useEmployeeQuery } from '@/hooks/queries/useEmployeeQuery';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

import CorrectionsBulletinPanel from '@/components/payslip-edit/CorrectionsBulletinPanel';
import {
  choixApresCorrection,
  lienCalendrierDuSalarie,
  prenomDuBulletin,
  type RefusApresCorrection,
} from '@/features/payroll/utils/heuresSurArret';
import {
  estBulletinIntrouvable,
  lienListeDesBulletins,
  messageBulletinNonCharge,
  messageBulletinRemplace,
  type MessageEcran,
} from '@/features/payroll/utils/bulletinRemplace';
import { invaliderApresBulletin } from '@/features/payroll/utils/invalidationsBulletin';
import { rechargementsDuBulletin } from '@/features/payroll/utils/rechargementBulletin';
import HistoryPanel from '@/components/payslip-edit/HistoryPanel';
import NotesSection from '@/components/payslip-edit/NotesSection';
import PayslipPreviewFrame from '@/components/payslip-edit/PayslipPreviewFrame';
import RegeneratePayslipButton from '@/components/payslip-edit/RegeneratePayslipButton';
import { MaintenanceDetailModal } from '@/components/payslip/MaintenanceDetailModal';
import { PayslipAlertsBanner } from '@/components/payslip/PayslipAlertsBanner';
import { ReportNetNegatif } from '@/features/payroll/components/ReportNetNegatif';
import { LignesExpliquees } from '@/features/payroll/components/LignesExpliquees';
import { ComparaisonMoisDernier } from '@/features/payroll/components/ComparaisonMoisDernier';
import { PayslipComparisonTab } from '@/components/payslip/PayslipComparisonTab';
import { PayslipTrendTab } from '@/components/payslip/PayslipTrendTab';
import { PayslipValidateBlockedModal } from '@/components/payslip/PayslipValidateBlockedModal';
import {
  aDesModifications,
  avecSaisiesSurLeNet,
  etatInitial,
  recalculAttendu,
  requeteDeCorrection,
  titreDuBulletin,
  type EtatCorrections,
  type SaisieDuMois,
} from '@/features/payroll/utils/correctionsBulletin';
import { lienVariablesDuMois } from '@/features/payroll/utils/payslipDerivedLines';
import { bandeauExportsDuMois } from '@/lib/exportsARefaire';
import { estPerime, messageARecalculer } from '@/features/payroll/utils/bulletinARecalculer';

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
  return dateEnClair(iso) || iso;
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
  const { data: salarieBulletin } = useEmployeeQuery(payslip?.employee_id);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('corriger');
  const [confirmationValide, setConfirmationValide] = useState(false);
  const [validateModalOpen, setValidateModalOpen] = useState(false);
  const [validateBusy, setValidateBusy] = useState(false);
  // Refus « heures sur un jour d'arrêt » du recalcul d'après une correction :
  // le dialogue du choix s'ouvre au lieu de proposer « Régénérer » (refusé de nouveau).
  const [refusApresCorrection, setRefusApresCorrection] =
    useState<RefusApresCorrection | null>(null);
  const [showMaintienModal, setShowMaintienModal] = useState(false);
  const [echecChargement, setEchecChargement] = useState<MessageEcran | null>(null);

  const appliquer = useCallback((data: PayslipDetail) => {
    const depart = etatInitial(data.payslip_data, data.pdf_notes);
    setPayslip(data);
    setInitial(depart);
    setEtat(depart);
  }, []);

  /** 404 : supprimé, ou supprimé puis généré à nouveau (autre identifiant). */
  const bulletinRemplace = useCallback(
    async (connu: PayslipDetail | null) => {
      toast(messageBulletinRemplace());
      await invaliderApresBulletin(queryClient, companyId, connu?.employee_id);
      navigate(lienListeDesBulletins(connu), { replace: true });
    },
    [toast, queryClient, companyId, navigate]
  );

  // Société du bulletin, envoyée à chaque appel : un autre onglet a pu changer
  // celle du localStorage, et le bulletin y serait « introuvable ».
  const societeDuBulletin = payslip?.company_id ?? companyId;

  // Les listes de bulletins (paie, fiche salarié) et les onglets du bulletin
  // sont en cache : sans cela, ils montraient l'ancien net après une correction.
  const invaliderListes = useCallback(() => {
    if (!payslip) return;
    void invaliderApresBulletin(queryClient, companyId, payslip.employee_id);
  }, [queryClient, companyId, payslip]);

  const rechargements = useMemo(
    () =>
      rechargementsDuBulletin({
        lire: payslipId ? () => getPayslipDetails(payslipId, societeDuBulletin) : null,
        appliquer,
        remplace: () => bulletinRemplace(payslip),
        signalerEchec: (error) =>
          toast({ ...messageBulletinNonCharge(error), variant: 'destructive' }),
        invaliderListes,
      }),
    [payslipId, societeDuBulletin, appliquer, bulletinRemplace, payslip, toast, invaliderListes]
  );
  const { recharger, apresChangement } = rechargements;

  const charger = useCallback(async () => {
    if (!payslipId) return;
    setIsLoading(true);
    setEchecChargement(null);
    try {
      appliquer(await getPayslipDetails(payslipId, companyId));
    } catch (error) {
      if (estBulletinIntrouvable(error)) await bulletinRemplace(null);
      else setEchecChargement(messageBulletinNonCharge(error));
    } finally {
      setIsLoading(false);
    }
  }, [payslipId, companyId, appliquer, bulletinRemplace]);

  useEffect(() => {
    if (!payslipId) {
      navigate('/');
      return;
    }
    void charger();
  }, [payslipId, navigate, charger]);

  // Les retenues et versements sur le net ne sont pas des lignes du bulletin :
  // on les lit dans les saisies du mois pour les montrer avec les primes.
  useEffect(() => {
    if (!payslip) return;
    let annule = false;
    getEmployeeMonthlyInputs(payslip.employee_id, payslip.year, payslip.month)
      .then((reponse) => {
        if (annule) return;
        const saisies = Array.isArray(reponse.data) ? (reponse.data as SaisieDuMois[]) : [];
        setInitial((i) => (i ? avecSaisiesSurLeNet(i, saisies) : i));
        setEtat((e) => (e ? avecSaisiesSurLeNet(e, saisies) : e));
      })
      .catch(() => {
        if (annule) return;
        toast({
          title: 'Retenues et versements sur le net non chargés',
          description:
            'Les primes du mois s’affichent sans eux. Rechargez la page pour les voir et les corriger.',
          variant: 'destructive',
        });
      });
    return () => {
      annule = true;
    };
  }, [payslip, toast]);

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
        requeteDeCorrection(initial, etat, payslip.updated_at),
        payslip.company_id
      );
      const suite = choixApresCorrection(reponse);
      if (suite.kind === 'choix') {
        toast({
          title: 'Corrections enregistrées, bulletin non recalculé',
          description: `${suite.refus.message} Choisissez quoi faire de ces heures.`,
          variant: 'destructive',
        });
        setRefusApresCorrection(suite.refus);
      } else if (suite.kind === 'regenerer') {
        toast({
          title: 'Corrections enregistrées, bulletin non recalculé',
          description: `${suite.message} — utilisez « Régénérer ».`,
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
      } else if (estBulletinIntrouvable(error)) {
        await bulletinRemplace(payslip);
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
      appliquer(await validatePayslip(payslipId, societeDuBulletin));
      invaliderListes();
      toast({ title: 'Bulletin validé', description: 'Le statut du bulletin a été mis à jour.' });
    } catch (error) {
      if (isCriticalValidationBlock(error)) {
        setValidateModalOpen(true);
      } else if (estBulletinIntrouvable(error)) {
        await bulletinRemplace(payslip);
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
  if (echecChargement) {
    return (
      <div className="container mx-auto max-w-2xl space-y-4">
        <Alert variant="destructive" data-testid="bulletin-non-charge">
          <AlertTitle>{echecChargement.title}</AlertTitle>
          <AlertDescription>{echecChargement.description}</AlertDescription>
        </Alert>
        <div className="flex gap-2">
          <Button type="button" onClick={() => void charger()}>
            Réessayer
          </Button>
          <Button type="button" variant="outline" onClick={() => navigate('/payroll')}>
            Retour à la paie
          </Button>
        </div>
      </div>
    );
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
  const bandeauExports = bandeauExportsDuMois(payslip.exports_du_mois ?? [], dateCourte);
  const validationBloquee = Boolean(
    recalculEnAttente || payslip.a_regenerer || estPerime(payslip)
  );
  // Ce qui a changé depuis le calcul, dit simplement (« La mutuelle a changé… »).
  const aRecalculer = messageARecalculer(payslip);
  const lienSaisies = lienVariablesDuMois({
    employeeId: payslip.employee_id,
    year: payslip.year,
    month: payslip.month,
  });

  return (
    <div className="container mx-auto space-y-6">
      <PayslipAlertsBanner data={payslip.payslip_data} />
      <ReportNetNegatif
        payslipId={payslip.id}
        companyId={payslip.company_id}
        variante="editeur"
      />

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

      {aRecalculer ? (
        <Alert data-testid="a-recalculer">
          <AlertTitle>À recalculer</AlertTitle>
          <AlertDescription>{aRecalculer}</AlertDescription>
        </Alert>
      ) : null}

      {bandeauExports ? (
        <Alert
          data-testid="exports-du-mois"
          variant={bandeauExports.aRefaire ? 'destructive' : 'default'}
        >
          <AlertTitle>{bandeauExports.titre}</AlertTitle>
          <AlertDescription>{bandeauExports.texte}</AlertDescription>
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
            {dateEnClair(payslip.manual_edit_lock_until)}.
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
            <h1 className={pageTitleClassName}>{titreDuBulletin(payslip.payslip_data, payslip.month, payslip.year)}</h1>
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
                ? ` · ${dateHeureEnClair(payslip.validated_at)}`
                : ''}
            </Badge>
          ) : isRH ? (
            <Button
              type="button"
              className="bg-sky-600 text-white hover:bg-sky-700"
              onClick={() => void valider()}
              disabled={validateBusy || validationBloquee}
              title={
                validationBloquee
                  ? (aRecalculer ?? 'Régénérez le bulletin avant de le valider')
                  : undefined
              }
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
            employeeName={prenomDuBulletin(payslip.payslip_data)}
            refusInitial={refusApresCorrection}
            onRefusInitialFerme={() => setRefusApresCorrection(null)}
            disabled={isEditLocked}
            companyId={payslip.company_id}
            onRegenerated={rechargements.apresRegeneration}
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
              lienPlanning={lienCalendrierDuSalarie(payslip.employee_id, { year: payslip.year, month: payslip.month })}
              lienFiche={`/employees/${encodeURIComponent(payslip.employee_id)}`}
              lienSaisies={lienSaisies}
              forfaitJours={salarieBulletin?.is_forfait_jour === true}
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
          <ComparaisonMoisDernier comparaison={payslip.comparaison_mois_dernier} />
          <LignesExpliquees payslipData={payslip.payslip_data} />
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
            companyId={payslip.company_id}
            canRestore={!isEditLocked}
            onRecalculRefuse={setRefusApresCorrection}
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
        companyId={payslip.company_id}
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
