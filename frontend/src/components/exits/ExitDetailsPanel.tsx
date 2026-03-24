/**
 * Panel détaillé pour afficher et gérer une sortie de salarié
 * Avec onglets : Vue d'ensemble, Checklist, Documents, Indemnités
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/hooks/use-toast';
import {
  getEmployeeExit,
  updateChecklistItem,
  calculateExitIndemnities,
  generateExitDocument,
  getDocumentUploadUrl,
  uploadDocument,
  createExitDocument,
  deleteExitDocument,
  publishExitDocuments,
  EmployeeExitWithDetails,
  ExitDocument,
  ChecklistItem,
  ExitIndemnityCalculation,
  exitTypeLabels,
  statusLabels,
  getStatusVariant,
  documentTypeLabels,
  PublishExitDocumentsResponse,
} from '@/api/employeeExits';
import {
  CalendarDays,
  FileText,
  Calculator,
  CheckCircle2,
  Circle,
  Download,
  Upload,
  Loader2,
  Trash2,
  FileUp,
  Eye,
  X,
  Send,
  Edit,
} from 'lucide-react';
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { useAuth } from '@/contexts/AuthContext';

interface ExitDetailsPanelProps {
  exitId: string | null;
  open: boolean;
  onClose: () => void;
  onUpdate?: () => void;
}

export function ExitDetailsPanel({ exitId, open, onClose, onUpdate }: ExitDetailsPanelProps) {
  const { toast } = useToast();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [exitDetails, setExitDetails] = useState<EmployeeExitWithDetails | null>(null);
  const [indemnities, setIndemnities] = useState<ExitIndemnityCalculation | null>(null);
  const [calculatingIndemnities, setCalculatingIndemnities] = useState(false);
  const [generatingDocument, setGeneratingDocument] = useState<string | null>(null);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishingDocuments, setPublishingDocuments] = useState(false);
  const [hasPublishPermission, setHasPublishPermission] = useState(false);

  useEffect(() => {
    if (open && exitId) {
      fetchExitDetails();
    }
  }, [open, exitId]);

  useEffect(() => {
    if (exitDetails && user) {
      checkPublishPermission();
    }
  }, [exitDetails, user]);

  const checkPublishPermission = async () => {
    if (!user || !exitDetails) return;
    
    // RH a la permission par défaut
    const isRH = user.role === 'rh' || user.role === 'admin';
    
    if (isRH) {
      setHasPublishPermission(true);
      return;
    }

    // Vérifier les permissions granulaires
    try {
      const { checkUserPermission } = await import('@/api/permissions');
      const companyId = exitDetails.company_id;
      const result = await checkUserPermission(
        user.id,
        companyId,
        'employee_documents.publish_exit_documents'
      );
      setHasPublishPermission(result.has_permission);
    } catch (error) {
      console.error('Erreur vérification permission:', error);
      setHasPublishPermission(false);
    }
  };

  const fetchExitDetails = async () => {
    if (!exitId) return;

    setLoading(true);
    try {
      const data = await getEmployeeExit(exitId);
      setExitDetails(data);

      // Si des indemnités sont déjà calculées, les afficher
      if (data.calculated_indemnities) {
        setIndemnities(data.calculated_indemnities as any);
      }
    } catch (error) {
      console.error('Erreur lors du chargement des détails:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger les détails de la sortie',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleChecklistItemToggle = async (itemId: string, isCompleted: boolean) => {
    if (!exitId) return;

    try {
      await updateChecklistItem(exitId, itemId, { is_completed: isCompleted });

      toast({
        title: 'Succès',
        description: 'Tâche mise à jour',
      });

      fetchExitDetails();
      onUpdate?.();
    } catch (error) {
      console.error('Erreur lors de la mise à jour:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de mettre à jour la tâche',
        variant: 'destructive',
      });
    }
  };

  const handleCalculateIndemnities = async () => {
    if (!exitId) return;

    setCalculatingIndemnities(true);
    try {
      const result = await calculateExitIndemnities(exitId);
      setIndemnities(result);

      toast({
        title: 'Succès',
        description: 'Indemnités calculées avec succès',
      });

      fetchExitDetails();
    } catch (error: any) {
      console.error('Erreur lors du calcul:', error);
      toast({
        title: 'Erreur',
        description: error.response?.data?.detail || 'Impossible de calculer les indemnités',
        variant: 'destructive',
      });
    } finally {
      setCalculatingIndemnities(false);
    }
  };

  const handleGenerateDocument = async (documentType: 'certificat_travail' | 'attestation_pole_emploi' | 'solde_tout_compte') => {
    if (!exitId) return;

    setGeneratingDocument(documentType);
    try {
      await generateExitDocument(exitId, documentType);

      toast({
        title: 'Succès',
        description: 'Document généré avec succès',
      });

      fetchExitDetails();
    } catch (error: any) {
      console.error('Erreur lors de la génération:', error);
      toast({
        title: 'Erreur',
        description: error.response?.data?.detail || 'Impossible de générer le document',
        variant: 'destructive',
      });
    } finally {
      setGeneratingDocument(null);
    }
  };

  const handleUploadDocument = async (file: File, documentType: string) => {
    if (!exitId) return;

    setUploadingDocument(true);
    try {
      // 1. Obtenir URL signée
      const { upload_url, storage_path } = await getDocumentUploadUrl(exitId, {
        filename: file.name,
        document_type: documentType as any,
        mime_type: file.type,
      });

      // 2. Upload vers Supabase Storage
      await uploadDocument(upload_url, file);

      // 3. Créer le record de document
      await createExitDocument({
        exit_id: exitId,
        document_type: documentType as any,
        storage_path,
        filename: file.name,
        mime_type: file.type,
        file_size_bytes: file.size,
      });

      toast({
        title: 'Succès',
        description: 'Document téléversé avec succès',
      });

      fetchExitDetails();
    } catch (error: any) {
      console.error('Erreur lors du téléversement:', error);
      toast({
        title: 'Erreur',
        description: error.response?.data?.detail || 'Impossible de téléverser le document',
        variant: 'destructive',
      });
    } finally {
      setUploadingDocument(false);
    }
  };

  const handleDeleteDocument = async (documentId: string) => {
    if (!exitId) return;

    if (!confirm('Êtes-vous sûr de vouloir supprimer ce document ?')) {
      return;
    }

    try {
      await deleteExitDocument(exitId, documentId);

      toast({
        title: 'Succès',
        description: 'Document supprimé',
      });

      fetchExitDetails();
    } catch (error) {
      console.error('Erreur lors de la suppression:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de supprimer le document',
        variant: 'destructive',
      });
    }
  };

  const handlePublishDocuments = async (forceUpdate: boolean = false) => {
    if (!exitId) return;

    setPublishingDocuments(true);
    try {
      const response: PublishExitDocumentsResponse = await publishExitDocuments(exitId, {
        document_ids: undefined, // Publier tous les documents générés
        force_update: forceUpdate,
      });

      setShowPublishModal(false);

      // Afficher un résumé
      const successCount = response.total_published + response.total_updated;
      const alreadyPublishedCount = response.total_already_published;
      
      let message = '';
      if (successCount > 0 && alreadyPublishedCount > 0) {
        message = `${successCount} document(s) publié(s) avec succès, ${alreadyPublishedCount} déjà publié(s)`;
      } else if (successCount > 0) {
        message = `${successCount} document(s) publié(s) avec succès`;
      } else if (alreadyPublishedCount > 0) {
        message = `${alreadyPublishedCount} document(s) déjà publié(s)`;
      } else {
        message = 'Aucun document publié';
      }

      toast({
        title: (successCount > 0 || alreadyPublishedCount > 0) ? 'Succès' : 'Information',
        description: message,
        variant: (successCount > 0 || alreadyPublishedCount > 0) ? 'default' : 'default',
      });

      // Afficher les détails si des erreurs
      if (response.total_failed > 0) {
        toast({
          title: 'Attention',
          description: `${response.total_failed} document(s) n'ont pas pu être publiés`,
          variant: 'destructive',
        });
      }

      fetchExitDetails();
    } catch (error: any) {
      console.error('Erreur lors de la publication:', error);
      toast({
        title: 'Erreur',
        description: error.response?.data?.detail || 'Impossible de publier les documents',
        variant: 'destructive',
      });
    } finally {
      setPublishingDocuments(false);
    }
  };


  const handleDownloadDocument = async (downloadUrl: string, filename: string) => {
    try {
      const response = await fetch(downloadUrl);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Erreur lors du téléchargement:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de télécharger le document',
        variant: 'destructive',
      });
    }
  };

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'dd/MM/yyyy', { locale: fr });
    } catch {
      return dateString;
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  if (!exitDetails) {
    return (
      <Sheet open={open} onOpenChange={onClose}>
        <SheetContent className="sm:max-w-3xl overflow-y-auto">
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        </SheetContent>
      </Sheet>
    );
  }

  const employee = exitDetails.employee;
  const checklist = exitDetails.checklist_items || [];
  const documents = exitDetails.documents || [];
  const completionRate = exitDetails.checklist_completion_rate || 0;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="sm:max-w-3xl overflow-y-auto">
        <SheetHeader className="pb-6">
          <SheetTitle className="text-2xl">
            {employee?.first_name} {employee?.last_name}
          </SheetTitle>
          <div className="flex items-center gap-3 pt-2">
            <Badge variant={getStatusVariant(exitDetails.status)}>
              {statusLabels[exitDetails.status]}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {exitTypeLabels[exitDetails.exit_type]}
            </span>
          </div>
        </SheetHeader>

        {/* Carte vue d'ensemble */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CalendarDays className="h-5 w-5" />
              Dates clés
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-muted-foreground">Date de demande</Label>
                <p className="font-medium">{formatDate(exitDetails.exit_request_date)}</p>
              </div>
              {exitDetails.notice_start_date && (
                <div>
                  <Label className="text-muted-foreground">Début préavis</Label>
                  <p className="font-medium">{formatDate(exitDetails.notice_start_date)}</p>
                </div>
              )}
              {exitDetails.notice_end_date && (
                <div>
                  <Label className="text-muted-foreground">Fin préavis</Label>
                  <p className="font-medium">{formatDate(exitDetails.notice_end_date)}</p>
                </div>
              )}
              <div>
                <Label className="text-muted-foreground">Dernier jour travaillé</Label>
                <p className="font-medium">{formatDate(exitDetails.last_working_day)}</p>
              </div>
              {exitDetails.final_settlement_date && (
                <div>
                  <Label className="text-muted-foreground">Date solde de tout compte</Label>
                  <p className="font-medium">{formatDate(exitDetails.final_settlement_date)}</p>
                </div>
              )}
              <div>
                <Label className="text-muted-foreground">Préavis</Label>
                <p className="font-medium">{exitDetails.notice_period_days} jours</p>
              </div>
            </div>
            {exitDetails.exit_reason && (
              <div className="pt-2">
                <Label className="text-muted-foreground">Motif</Label>
                <p className="text-sm">{exitDetails.exit_reason}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tabs */}
        <Tabs defaultValue="checklist" className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="checklist" className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Checklist
            </TabsTrigger>
            <TabsTrigger value="documents" className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Documents
            </TabsTrigger>
            <TabsTrigger value="indemnities" className="flex items-center gap-2">
              <Calculator className="h-4 w-4" />
              Indemnités
            </TabsTrigger>
          </TabsList>

          {/* Onglet Checklist */}
          <TabsContent value="checklist" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Progression</CardTitle>
                <CardDescription>
                  {Math.round(completionRate)}% des tâches complétées
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Progress value={completionRate} className="h-2" />
              </CardContent>
            </Card>

            <div className="space-y-3">
              {checklist.map((item: ChecklistItem) => (
                <Card key={item.id}>
                  <CardContent className="pt-6">
                    <div className="flex items-start gap-3">
                      <Checkbox
                        id={`item-${item.id}`}
                        checked={item.is_completed}
                        onCheckedChange={(checked) =>
                          handleChecklistItemToggle(item.id, checked as boolean)
                        }
                        className="mt-1"
                      />
                      <div className="flex-1">
                        <Label
                          htmlFor={`item-${item.id}`}
                          className={`cursor-pointer font-medium ${
                            item.is_completed ? 'line-through text-muted-foreground' : ''
                          }`}
                        >
                          {item.item_label}
                        </Label>
                        {item.item_description && (
                          <p className="text-sm text-muted-foreground mt-1">
                            {item.item_description}
                          </p>
                        )}
                        {item.is_completed && item.completed_at && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Complété le {formatDate(item.completed_at)}
                          </p>
                        )}
                      </div>
                      {item.is_required && (
                        <Badge variant="outline" className="text-xs">
                          Obligatoire
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          {/* Onglet Documents */}
          <TabsContent value="documents" className="space-y-4">
            {/* Liste des documents */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Documents</CardTitle>
                    <CardDescription>
                      Les documents obligatoires sont générés automatiquement lors de l'initiation de la sortie
                    </CardDescription>
                  </div>
                  {hasPublishPermission && documents.filter(d => d.document_category === 'generated').length > 0 && (
                    <Button
                      onClick={() => setShowPublishModal(true)}
                      variant="default"
                      size="sm"
                      className="flex items-center gap-2"
                    >
                      <Send className="h-4 w-4" />
                      Envoyer sur l'espace Documents du collaborateur
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {documents.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    Aucun document pour le moment. Les documents seront générés automatiquement.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {documents.map((doc: ExitDocument) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <div className="flex items-center gap-3 flex-1">
                          <FileText className="h-5 w-5 text-muted-foreground" />
                          <div className="flex-1">
                            <p className="font-medium text-sm">
                              {documentTypeLabels[doc.document_type]}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {doc.filename} • {formatDate(doc.created_at)}
                              {doc.document_category === 'generated' && (
                                <Badge variant="outline" className="ml-2 text-xs">Généré automatiquement</Badge>
                              )}
                              {doc.published_to_employee && (
                                <Badge variant="default" className="ml-2 text-xs bg-green-600">Publié</Badge>
                              )}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          {doc.document_category === 'generated' && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => navigate(`/employee-exits/${exitId}/documents/${doc.id}/edit`)}
                              title="Modifier le document"
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                          )}
                          {doc.download_url && (
                            <>
                              <Button
                                variant="ghost"
                                size="icon"
                                asChild
                                title="Voir le document"
                              >
                                <a href={doc.download_url} target="_blank" rel="noopener noreferrer">
                                  <Eye className="h-4 w-4" />
                                </a>
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDownloadDocument(doc.download_url!, doc.filename)}
                                title="Télécharger le document"
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                            </>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteDocument(doc.id)}
                            title="Supprimer le document"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Onglet Indemnités */}
          <TabsContent value="indemnities" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Calcul des indemnités</CardTitle>
                <CardDescription>
                  Calcul automatique selon le Code du travail
                </CardDescription>
              </CardHeader>
              <CardContent>
                {!indemnities ? (
                  <div className="text-center py-8">
                    <Button
                      onClick={handleCalculateIndemnities}
                      disabled={calculatingIndemnities}
                    >
                      {calculatingIndemnities && (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      )}
                      <Calculator className="mr-2 h-4 w-4" />
                      Calculer les indemnités
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="grid gap-4">
                      {/* Indemnité de préavis */}
                      {indemnities.indemnite_preavis && (
                        <div className="p-4 border rounded-lg">
                          <div className="flex justify-between items-start mb-2">
                            <div>
                              <p className="font-medium">Indemnité de préavis</p>
                              <p className="text-sm text-muted-foreground">
                                {indemnities.indemnite_preavis.description}
                              </p>
                            </div>
                            <p className="font-bold text-lg">
                              {formatCurrency(indemnities.indemnite_preavis.montant)}
                            </p>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {indemnities.indemnite_preavis.calcul}
                          </p>
                        </div>
                      )}

                      {/* Indemnité de congés */}
                      {indemnities.indemnite_conges && (
                        <div className="p-4 border rounded-lg">
                          <div className="flex justify-between items-start mb-2">
                            <div>
                              <p className="font-medium">Indemnité de congés payés</p>
                              <p className="text-sm text-muted-foreground">
                                {indemnities.indemnite_conges.description}
                              </p>
                            </div>
                            <p className="font-bold text-lg">
                              {formatCurrency(indemnities.indemnite_conges.montant)}
                            </p>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {indemnities.indemnite_conges.calcul}
                          </p>
                        </div>
                      )}

                      {/* Indemnité de licenciement */}
                      {indemnities.indemnite_licenciement && (
                        <div className="p-4 border rounded-lg bg-blue-50 dark:bg-blue-950">
                          <div className="flex justify-between items-start mb-2">
                            <div>
                              <p className="font-medium">Indemnité légale de licenciement</p>
                              <p className="text-sm text-muted-foreground">
                                {indemnities.indemnite_licenciement.description}
                              </p>
                            </div>
                            <p className="font-bold text-lg">
                              {formatCurrency(indemnities.indemnite_licenciement.montant)}
                            </p>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {indemnities.indemnite_licenciement.calcul}
                          </p>
                        </div>
                      )}

                      {/* Indemnité de rupture conventionnelle */}
                      {indemnities.indemnite_rupture_conventionnelle && (
                        <div className="p-4 border rounded-lg bg-green-50 dark:bg-green-950">
                          <div className="flex justify-between items-start mb-2">
                            <div>
                              <p className="font-medium">Indemnité de rupture conventionnelle</p>
                              <p className="text-sm text-muted-foreground">
                                {indemnities.indemnite_rupture_conventionnelle.description}
                              </p>
                            </div>
                            <p className="font-bold text-lg">
                              {formatCurrency(indemnities.indemnite_rupture_conventionnelle.montant_negocie)}
                            </p>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {indemnities.indemnite_rupture_conventionnelle.calcul}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Totaux */}
                    <div className="border-t pt-4 space-y-2">
                      <div className="flex justify-between items-center">
                        <p className="font-medium">Total brut des indemnités</p>
                        <p className="font-bold text-xl">
                          {formatCurrency(indemnities.total_gross_indemnities)}
                        </p>
                      </div>
                      <div className="flex justify-between items-center">
                        <p className="font-medium">Total net estimé</p>
                        <p className="font-bold text-xl text-green-600">
                          {formatCurrency(indemnities.total_net_indemnities)}
                        </p>
                      </div>
                    </div>

                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={handleCalculateIndemnities}
                      disabled={calculatingIndemnities}
                    >
                      {calculatingIndemnities && (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      )}
                      Recalculer
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </SheetContent>

      {/* Modal de confirmation de publication */}
      <Dialog open={showPublishModal} onOpenChange={setShowPublishModal}>
        <DialogPrimitive.Portal>
          {/* Pas d'overlay pour garder le contenu visible */}
          <DialogPrimitive.Content
            className={cn(
              "fixed left-[50%] top-[50%] z-[100] grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg"
            )}
          >
          <DialogHeader>
            <DialogTitle>Publier les documents de sortie</DialogTitle>
            <DialogDescription>
              Les documents suivants seront envoyés dans l'espace Documents du collaborateur (section "Autres") :
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <ul className="space-y-2">
              {documents
                .filter((d) => d.document_category === 'generated')
                .map((doc) => (
                  <li key={doc.id} className="flex items-center gap-2 text-sm">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span>{documentTypeLabels[doc.document_type]}</span>
                    {doc.published_to_employee && (
                      <Badge variant="outline" className="text-xs">
                        Déjà publié
                      </Badge>
                    )}
                  </li>
                ))}
            </ul>
            {documents.filter((d) => d.document_category === 'generated').length === 0 && (
              <p className="text-sm text-muted-foreground">
                Aucun document généré à publier.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowPublishModal(false)}
              disabled={publishingDocuments}
            >
              Annuler
            </Button>
            <Button
              onClick={() => handlePublishDocuments(false)}
              disabled={publishingDocuments || documents.filter((d) => d.document_category === 'generated').length === 0}
            >
              {publishingDocuments ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Publication en cours...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Publier
                </>
              )}
            </Button>
          </DialogFooter>
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </Dialog>
    </Sheet>
  );
}
