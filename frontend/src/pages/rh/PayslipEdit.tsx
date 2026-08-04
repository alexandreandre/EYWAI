// frontend/src/pages/PayslipEdit.tsx

import { pageTitleClassName } from '@/components/layout';
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import { ArrowLeft, Save, Eye, History, Loader2 } from 'lucide-react';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

import {
  getPayslipDetails,
  editPayslip,
  validatePayslip,
  PayslipDetail,
  PayslipEditRequest,
  isPayslipBlocMaintienPresent,
  type PayslipBulletinData,
} from '@/api/payslips';
import { useAuth, hasRhAccess } from '@/contexts/AuthContext';
import { isPlatformAdmin } from '@/lib/platformAdmin';

// Import des composants d'édition (à créer)
import PayslipHeaderSection from '@/components/payslip-edit/PayslipHeaderSection';
import CongesAbsencesSection from '@/components/payslip-edit/CongesAbsencesSection';
import CalculBrutSection from '@/components/payslip-edit/CalculBrutSection';
import CotisationsSection from '@/components/payslip-edit/CotisationsSection';
import SyntheseNetSection from '@/components/payslip-edit/SyntheseNetSection';
import PrimesNonSoumisesSection from '@/components/payslip-edit/PrimesNonSoumisesSection';
import NotesDeFraisSection from '@/components/payslip-edit/NotesDeFraisSection';
import NotesSection from '@/components/payslip-edit/NotesSection';
import HistoryPanel from '@/components/payslip-edit/HistoryPanel';
import PayslipPreviewFrame from '@/components/payslip-edit/PayslipPreviewFrame';
import { MaintenanceDetailModal } from '@/components/payslip/MaintenanceDetailModal';
import { PayslipComparisonTab } from '@/components/payslip/PayslipComparisonTab';
import { PayslipTrendTab } from '@/components/payslip/PayslipTrendTab';
import { PayslipValidateBlockedModal } from '@/components/payslip/PayslipValidateBlockedModal';
import { PayslipAlertsBanner } from '@/components/payslip/PayslipAlertsBanner';
import { cn } from '@/lib/utils';

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

export default function PayslipEdit() {
  const { payslipId } = useParams<{ payslipId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();

  const [payslip, setPayslip] = useState<PayslipDetail | null>(null);
  const [editedData, setEditedData] = useState<PayslipBulletinData | null>(null);
  const [showMaintienModal, setShowMaintienModal] = useState(false);
  const [cumuls, setCumuls] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [changesSummary, setChangesSummary] = useState('');
  const [pdfNotes, setPdfNotes] = useState('');
  const [internalNote, setInternalNote] = useState('');
  const [activeTab, setActiveTab] = useState('edit');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [validateModalOpen, setValidateModalOpen] = useState(false);
  const [validateBusy, setValidateBusy] = useState(false);

  const isRH = payslip ? hasRhAccess(user, payslip.company_id) : false;
  const isAdminPlatform = isPlatformAdmin(user);
  const isEditLocked = Boolean(payslip?.manual_edit_locked);
  const showAdminOverride =
    Boolean(payslip?.period_edit_locked) && isAdminPlatform && !isEditLocked;
  const payslipStatus = payslip?.status ?? 'brouillon';

  const refreshPayslipFromServer = useCallback(async () => {
    if (!payslipId) return;
    const data = await getPayslipDetails(payslipId);
    setPayslip(data);
    setEditedData(JSON.parse(JSON.stringify(data.payslip_data)) as PayslipBulletinData);
    setPdfNotes(data.pdf_notes || '');
    setCumuls(data.cumuls || null);
    setHasUnsavedChanges(false);
    setChangesSummary('');
    setInternalNote('');
  }, [payslipId]);

  // Charger les détails du bulletin
  useEffect(() => {
    if (!payslipId) {
      navigate('/');
      return;
    }

    const fetchPayslip = async () => {
      setIsLoading(true);
      try {
        const data = await getPayslipDetails(payslipId);
        setPayslip(data);
        setEditedData(
          JSON.parse(JSON.stringify(data.payslip_data)) as PayslipBulletinData
        ); // Deep clone
        setPdfNotes(data.pdf_notes || '');
        setCumuls(data.cumuls || null);
      } catch (error: any) {
        toast({
          title: 'Erreur',
          description: error.response?.data?.detail || 'Impossible de charger le bulletin',
          variant: 'destructive',
        });
        navigate('/payroll');
      } finally {
        setIsLoading(false);
      }
    };

    fetchPayslip();
  }, [payslipId, navigate, toast]);

  const handleValidatePayslip = async () => {
    if (!payslipId) return;
    setValidateBusy(true);
    try {
      const updated = await validatePayslip(payslipId);
      setPayslip(updated);
      setEditedData(JSON.parse(JSON.stringify(updated.payslip_data)) as PayslipBulletinData);
      setHasUnsavedChanges(false);
      toast({ title: 'Bulletin validé', description: 'Le statut du bulletin a été mis à jour.' });
    } catch (error: unknown) {
      if (isCriticalValidationBlock(error)) {
        setValidateModalOpen(true);
      } else {
        const ax = error as { response?: { data?: { detail?: string } } };
        toast({
          title: 'Erreur',
          description:
            typeof ax.response?.data?.detail === 'string'
              ? ax.response.data.detail
              : 'Impossible de valider le bulletin',
          variant: 'destructive',
        });
      }
    } finally {
      setValidateBusy(false);
    }
  };

  // Fonction pour mettre à jour les données éditées
  const updateEditedData = (path: string[], value: any) => {
    if (isEditLocked) return;
    const newData = JSON.parse(JSON.stringify(editedData));
    let current = newData;

    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]];
    }

    current[path[path.length - 1]] = value;
    setEditedData(newData);
    setHasUnsavedChanges(true);
  };

  // Fonction de sauvegarde
  const handleSave = async () => {
    if (!changesSummary.trim()) {
      toast({
        title: 'Résumé requis',
        description: 'Veuillez fournir un résumé des modifications effectuées',
        variant: 'destructive',
      });
      return;
    }

    setIsSaving(true);
    try {
      const request: PayslipEditRequest = {
        payslip_data: editedData,
        changes_summary: changesSummary,
        pdf_notes: pdfNotes || undefined,
        internal_note: internalNote || undefined,
      };

      const response = await editPayslip(payslipId!, request);

      toast({
        title: 'Succès',
        description: 'Le bulletin a été modifié avec succès',
      });

      setHasUnsavedChanges(false);
      setChangesSummary('');
      setInternalNote('');

      // Recharger les données
      const updatedPayslip = await getPayslipDetails(payslipId!);
      setPayslip(updatedPayslip);
      setEditedData(
        JSON.parse(JSON.stringify(updatedPayslip.payslip_data)) as PayslipBulletinData
      );
      setCumuls(updatedPayslip.cumuls || null);
    } catch (error: any) {
      toast({
        title: 'Erreur',
        description: error.response?.data?.detail || 'Impossible de sauvegarder les modifications',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Avertissement avant de quitter si modifications non sauvegardées
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  if (isLoading) {
    return <SharkFinLoader variant="fullPage" label="Chargement du bulletin…" />;
  }

  if (!payslip || !editedData) {
    return null;
  }

  return (
    <div className="container mx-auto space-y-6">
      <PayslipAlertsBanner data={editedData} />

      {isEditLocked && payslip.manual_edit_lock_reason ? (
        <Alert variant="destructive">
          <AlertTitle>Édition verrouillée</AlertTitle>
          <AlertDescription>{payslip.manual_edit_lock_reason}</AlertDescription>
        </Alert>
      ) : null}

      {showAdminOverride ? (
        <Alert>
          <AlertTitle>Override administrateur</AlertTitle>
          <AlertDescription>
            La période est normalement verrouillée pour les RH, mais vous pouvez
            encore modifier ce bulletin en tant qu&apos;administrateur plateforme.
          </AlertDescription>
        </Alert>
      ) : null}

      {!isEditLocked && payslip.manual_edit_lock_until ? (
        <Alert>
          <AlertDescription>
            Édition manuelle autorisée jusqu&apos;au{' '}
            {new Date(payslip.manual_edit_lock_until).toLocaleDateString('fr-FR')}.
          </AlertDescription>
        </Alert>
      ) : null}

      {/* Header avec navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
          <div>
            <h1 className={pageTitleClassName}>
              Édition du bulletin - {payslip.name}
            </h1>
            <p className="text-muted-foreground">
              {payslip.manually_edited && `Modifié ${payslip.edit_count} fois`}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {payslipStatus === 'valide' ? (
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
              onClick={handleValidatePayslip}
              disabled={validateBusy}
            >
              {validateBusy ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              Valider le bulletin
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => setActiveTab('preview')}>
            <Eye className="h-4 w-4 mr-2" />
            Aperçu
          </Button>
          <Button variant="outline" onClick={() => setActiveTab('history')}>
            <History className="h-4 w-4 mr-2" />
            Historique
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || !hasUnsavedChanges || isEditLocked}
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Enregistrer
          </Button>
        </div>
      </div>

      {/* Indicateur de modifications non sauvegardées */}
      {hasUnsavedChanges && (
        <Card className="border-orange-500 bg-orange-50">
          <CardContent className="py-3">
            <p className="text-sm text-orange-800">
              ⚠️ Vous avez des modifications non sauvegardées
            </p>
          </CardContent>
        </Card>
      )}

      {/* Onglets */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList
          className={cn(
            'grid h-auto w-full gap-1 p-1',
            'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5'
          )}
        >
          <TabsTrigger value="edit">Édition</TabsTrigger>
          <TabsTrigger value="preview">Aperçu</TabsTrigger>
          <TabsTrigger value="history">Historique</TabsTrigger>
          <TabsTrigger value="comparison">Comparaison N-1</TabsTrigger>
          <TabsTrigger value="trend">Tendance</TabsTrigger>
        </TabsList>

        {/* Onglet Édition */}
        <TabsContent value="edit" className="space-y-6 mt-6">
          <fieldset disabled={isEditLocked} className="space-y-6 border-0 p-0 m-0 min-w-0">
          {/* Section En-tête */}
          <PayslipHeaderSection
            data={editedData.en_tete}
            onChange={(newData) => updateEditedData(['en_tete'], newData)}
          />

          {/* Section Congés et Absences */}
          <CongesAbsencesSection
            congesData={editedData.details_conges || []}
            absencesData={editedData.details_absences || []}
            onCongesChange={(data) => updateEditedData(['details_conges'], data)}
            onAbsencesChange={(data) => updateEditedData(['details_absences'], data)}
            detailsMaintien={editedData.details_maintien}
            blocMaintien={editedData.bloc_maintien}
            syntheseNet={editedData.synthese_net}
            onOpenMaintienModal={() => setShowMaintienModal(true)}
          />

          {/* Section Calcul du Brut */}
          <CalculBrutSection
            data={editedData.calcul_du_brut || []}
            salaireBrut={editedData.salaire_brut}
            onChange={(data, newBrut) => {
              updateEditedData(['calcul_du_brut'], data);
              updateEditedData(['salaire_brut'], newBrut);
            }}
          />

          {/* Section Cotisations */}
          <CotisationsSection
            data={editedData.structure_cotisations}
            onChange={(data) => updateEditedData(['structure_cotisations'], data)}
          />

          {/* Section Synthèse Net */}
          <SyntheseNetSection
            data={editedData.synthese_net}
            netAPayer={editedData.net_a_payer}
            totalExonerations={editedData.total_exonerations}
            onChange={(data, newNetAPayer) => {
              updateEditedData(['synthese_net'], data);
              updateEditedData(['net_a_payer'], newNetAPayer);
            }}
          />

          {/* Section Primes non soumises */}
          <PrimesNonSoumisesSection
            data={editedData.primes_non_soumises || []}
            onChange={(data) => updateEditedData(['primes_non_soumises'], data)}
          />

          {/* Section Notes de Frais */}
          <NotesDeFraisSection
            data={editedData.notes_de_frais || []}
            onChange={(data) => updateEditedData(['notes_de_frais'], data)}
          />

          {/* Section Notes */}
          <NotesSection
            pdfNotes={pdfNotes}
            internalNote={internalNote}
            internalNotes={payslip.internal_notes}
            changesSummary={changesSummary}
            onPdfNotesChange={setPdfNotes}
            onInternalNoteChange={setInternalNote}
            onChangesSummaryChange={setChangesSummary}
          />
          </fieldset>
        </TabsContent>

        {/* Onglet Aperçu */}
        <TabsContent value="preview" className="mt-6">
          <PayslipPreviewFrame
            payslipId={payslipId!}
            data={{ ...editedData, cumuls }}
            pdfNotes={pdfNotes}
          />
        </TabsContent>

        {/* Onglet Historique */}
        <TabsContent value="history" className="mt-6">
          <HistoryPanel
            payslipId={payslipId!}
            canRestore={!isEditLocked}
            onRestore={() => {
              // Recharger après restauration
              getPayslipDetails(payslipId!).then((data) => {
                setPayslip(data);
                setEditedData(
                  JSON.parse(JSON.stringify(data.payslip_data)) as PayslipBulletinData
                );
                setCumuls(data.cumuls || null);
                setActiveTab('edit');
              });
            }}
          />
        </TabsContent>

        <TabsContent value="comparison" className="mt-0">
          <PayslipComparisonTab
            payslipId={payslipId!}
            isRH={isRH}
            onShowTrend={() => setActiveTab('trend')}
            onPayslipRefresh={refreshPayslipFromServer}
          />
        </TabsContent>

        <TabsContent value="trend" className="mt-0">
          <PayslipTrendTab
            payslipId={payslipId!}
            referenceYear={payslip.year}
            referenceMonth={payslip.month}
          />
        </TabsContent>
      </Tabs>

      <PayslipValidateBlockedModal
        open={validateModalOpen}
        onOpenChange={setValidateModalOpen}
        payslipId={payslipId!}
        isRH={isRH}
        onValidated={refreshPayslipFromServer}
      />

      {editedData && isPayslipBlocMaintienPresent(editedData.bloc_maintien) ? (
        <MaintenanceDetailModal
          open={showMaintienModal}
          onClose={() => setShowMaintienModal(false)}
          maintien={editedData.bloc_maintien}
        />
      ) : null}
    </div>
  );
}
