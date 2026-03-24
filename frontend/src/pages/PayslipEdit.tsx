// frontend/src/pages/PayslipEdit.tsx

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { ArrowLeft, Save, Eye, History, Loader2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { getPayslipDetails, editPayslip, PayslipDetail, PayslipEditRequest } from '@/api/payslips';
import { useAuth } from '@/contexts/AuthContext';

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
import PreviewPanel from '@/components/payslip-edit/PreviewPanel';

export default function PayslipEdit() {
  const { payslipId } = useParams<{ payslipId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();

  const [payslip, setPayslip] = useState<PayslipDetail | null>(null);
  const [editedData, setEditedData] = useState<any>(null);
  const [cumuls, setCumuls] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [changesSummary, setChangesSummary] = useState('');
  const [pdfNotes, setPdfNotes] = useState('');
  const [internalNote, setInternalNote] = useState('');
  const [activeTab, setActiveTab] = useState('edit');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

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
        setEditedData(JSON.parse(JSON.stringify(data.payslip_data))); // Deep clone
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

  // Fonction pour mettre à jour les données éditées
  const updateEditedData = (path: string[], value: any) => {
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
      setEditedData(JSON.parse(JSON.stringify(updatedPayslip.payslip_data)));
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
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!payslip || !editedData) {
    return null;
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header avec navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
          <div>
            <h1 className="text-3xl font-bold">
              Édition du bulletin - {payslip.name}
            </h1>
            <p className="text-muted-foreground">
              {payslip.manually_edited && `Modifié ${payslip.edit_count} fois`}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
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
            disabled={isSaving || !hasUnsavedChanges}
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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="edit">Édition</TabsTrigger>
          <TabsTrigger value="preview">Aperçu</TabsTrigger>
          <TabsTrigger value="history">Historique</TabsTrigger>
        </TabsList>

        {/* Onglet Édition */}
        <TabsContent value="edit" className="space-y-6 mt-6">
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
        </TabsContent>

        {/* Onglet Aperçu */}
        <TabsContent value="preview" className="mt-6">
          <PreviewPanel data={editedData} pdfNotes={pdfNotes} cumuls={cumuls} />
        </TabsContent>

        {/* Onglet Historique */}
        <TabsContent value="history" className="mt-6">
          <HistoryPanel
            payslipId={payslipId!}
            onRestore={() => {
              // Recharger après restauration
              getPayslipDetails(payslipId!).then((data) => {
                setPayslip(data);
                setEditedData(JSON.parse(JSON.stringify(data.payslip_data)));
                setCumuls(data.cumuls || null);
                setActiveTab('edit');
              });
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
