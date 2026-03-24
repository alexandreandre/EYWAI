// frontend/src/pages/ExitDocumentEdit.tsx

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { ArrowLeft, Save, Eye, History, Loader2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

import {
  getExitDocumentDetails,
  editExitDocument,
  ExitDocumentDetails,
  ExitDocumentEditRequest,
  documentTypeLabels,
} from '@/api/employeeExits';
import { useAuth } from '@/contexts/AuthContext';

// Import des composants d'édition
import CertificatTravailSection from '@/components/exit-document-edit/CertificatTravailSection';
import AttestationPoleEmploiSection from '@/components/exit-document-edit/AttestationPoleEmploiSection';
import SoldeToutCompteSection from '@/components/exit-document-edit/SoldeToutCompteSection';

export default function ExitDocumentEdit() {
  const { exitId, documentId } = useParams<{ exitId: string; documentId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();

  const [document, setDocument] = useState<ExitDocumentDetails | null>(null);
  const [editedData, setEditedData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [changesSummary, setChangesSummary] = useState('');
  const [internalNote, setInternalNote] = useState('');
  const [activeTab, setActiveTab] = useState('edit');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Charger les détails du document
  useEffect(() => {
    if (!exitId || !documentId) {
      navigate('/employee-exits');
      return;
    }

    const fetchDocument = async () => {
      setIsLoading(true);
      try {
        const data = await getExitDocumentDetails(exitId, documentId);
        setDocument(data);
        setEditedData(JSON.parse(JSON.stringify(data.document_data || {}))); // Deep clone
      } catch (error: any) {
        toast({
          title: 'Erreur',
          description: error.response?.data?.detail || 'Impossible de charger le document',
          variant: 'destructive',
        });
        navigate('/employee-exits');
      } finally {
        setIsLoading(false);
      }
    };

    fetchDocument();
  }, [exitId, documentId, navigate, toast]);

  // Fonction pour mettre à jour les données éditées
  const updateEditedData = (path: string[], value: any) => {
    const newData = JSON.parse(JSON.stringify(editedData));
    let current = newData;

    for (let i = 0; i < path.length - 1; i++) {
      if (!current[path[i]]) {
        current[path[i]] = {};
      }
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
      const request: ExitDocumentEditRequest = {
        document_data: editedData,
        changes_summary: changesSummary,
        internal_note: internalNote || undefined,
      };

      await editExitDocument(exitId!, documentId!, request);

      toast({
        title: 'Succès',
        description: 'Le document a été modifié avec succès',
      });

      setHasUnsavedChanges(false);
      setChangesSummary('');
      setInternalNote('');

      // Recharger les données
      const updatedDocument = await getExitDocumentDetails(exitId!, documentId!);
      setDocument(updatedDocument);
      setEditedData(JSON.parse(JSON.stringify(updatedDocument.document_data || {})));
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

  if (!document || !editedData) {
    return null;
  }

  const renderEditSection = () => {
    switch (document.document_type) {
      case 'certificat_travail':
        return (
          <CertificatTravailSection
            data={editedData}
            onChange={(newData) => setEditedData(newData)}
          />
        );
      case 'attestation_pole_emploi':
        return (
          <AttestationPoleEmploiSection
            data={editedData}
            onChange={(newData) => setEditedData(newData)}
          />
        );
      case 'solde_tout_compte':
        return (
          <SoldeToutCompteSection
            data={editedData}
            onChange={(newData) => setEditedData(newData)}
          />
        );
      default:
        return (
          <Card>
            <CardContent className="py-6">
              <p className="text-muted-foreground">
                L'édition de ce type de document n'est pas encore supportée.
              </p>
            </CardContent>
          </Card>
        );
    }
  };

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
              Édition - {documentTypeLabels[document.document_type]}
            </h1>
            <p className="text-muted-foreground">
              {document.manually_edited && `Version ${document.version || 1}`}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          {document.download_url && (
            <Button variant="outline" asChild>
              <a href={document.download_url} target="_blank" rel="noopener noreferrer">
                <Eye className="h-4 w-4 mr-2" />
                Voir le PDF
              </a>
            </Button>
          )}
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
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="edit">Édition</TabsTrigger>
          <TabsTrigger value="notes">Notes et résumé</TabsTrigger>
        </TabsList>

        {/* Onglet Édition */}
        <TabsContent value="edit" className="space-y-6 mt-6">
          {renderEditSection()}
        </TabsContent>

        {/* Onglet Notes */}
        <TabsContent value="notes" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Résumé des modifications</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="changes-summary">
                  Résumé des modifications <span className="text-red-500">*</span>
                </Label>
                <Textarea
                  id="changes-summary"
                  placeholder="Décrivez les modifications apportées au document..."
                  value={changesSummary}
                  onChange={(e) => setChangesSummary(e.target.value)}
                  rows={4}
                  className="mt-2"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Ce résumé sera enregistré dans l'historique des modifications
                </p>
              </div>

              <div>
                <Label htmlFor="internal-note">Note interne (optionnelle)</Label>
                <Textarea
                  id="internal-note"
                  placeholder="Note interne (non visible dans le PDF)..."
                  value={internalNote}
                  onChange={(e) => setInternalNote(e.target.value)}
                  rows={3}
                  className="mt-2"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Cette note est uniquement visible en interne et n'apparaîtra pas dans le document
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
