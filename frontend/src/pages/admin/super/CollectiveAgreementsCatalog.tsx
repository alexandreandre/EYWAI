// frontend/src/pages/super-admin/CollectiveAgreementsCatalog.tsx

import { log } from '@/lib/logger';
import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Download,
  Edit,
  FileText,
  Loader2,
  Plus,
  Search,
  Trash2,
  CheckCircle,
  XCircle,
  Sparkles,
  Eye,
  Landmark,
} from 'lucide-react';
import * as collectiveAgreementsApi from '@/api/collectiveAgreements';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';

export default function CollectiveAgreementsCatalog() {
  const { toast } = useToast();

  // États pour le catalogue
  const [catalog, setCatalog] = useState<collectiveAgreementsApi.CollectiveAgreementCatalog[]>([]);
  const [filteredCatalog, setFilteredCatalog] = useState<collectiveAgreementsApi.CollectiveAgreementCatalog[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // États pour les filtres
  const [searchTerm, setSearchTerm] = useState('');
  const [sectorFilter, setSectorFilter] = useState<string>('all');

  // États pour le modal de création/édition
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [editingAgreement, setEditingAgreement] = useState<collectiveAgreementsApi.CollectiveAgreementCatalog | null>(null);

  // États pour le formulaire
  const [formData, setFormData] = useState({
    name: '',
    idcc: '',
    description: '',
    sector: '',
    effective_date: '',
    is_active: true,
  });

  // États pour l'upload de PDF
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // États pour la suppression
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [agreementToDelete, setAgreementToDelete] = useState<collectiveAgreementsApi.CollectiveAgreementCatalog | null>(null);
  const [companyAssignments, setCompanyAssignments] = useState<
    collectiveAgreementsApi.CompanyWithAssignments[]
  >([]);

  // Règles paie (extraction IA)
  const [rulesStatusMap, setRulesStatusMap] = useState<
    Record<string, collectiveAgreementsApi.RulesStatusResponse>
  >({});
  const [extractingId, setExtractingId] = useState<string | null>(null);
  const [rulesModalOpen, setRulesModalOpen] = useState(false);
  const [rulesModalContent, setRulesModalContent] = useState<Record<string, unknown> | null>(null);
  const [rulesModalTitle, setRulesModalTitle] = useState('');

  // Import Légifrance (KALI)
  const [importIdcc, setImportIdcc] = useState('');
  const [isImportingKali, setIsImportingKali] = useState(false);
  const [isBatchImportingKali, setIsBatchImportingKali] = useState(false);
  const [reimportingId, setReimportingId] = useState<string | null>(null);

  // Liste des secteurs
  const sectors = [
    'Commerce',
    'BTP',
    'Industrie',
    'Services',
    'Hôtellerie-Restauration',
    'Santé-Social',
    'Banque-Finance',
    'Assurance',
    'Télécommunications',
    'Numérique-Conseil',
    'Transport',
    'Immobilier',
    'Agriculture',
    'Édition-Presse',
    'Communication',
    'Autre',
  ];

  useEffect(() => {
    fetchCatalog();
    void collectiveAgreementsApi
      .getAllCompanyAssignments()
      .then((res) => setCompanyAssignments(res.data ?? []))
      .catch(() => setCompanyAssignments([]));
  }, []);

  useEffect(() => {
    // Filtrer le catalogue selon les critères
    let filtered = [...catalog];

    // Filtre par recherche (nom ou IDCC)
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (agreement) =>
          agreement.name.toLowerCase().includes(search) ||
          agreement.idcc.toLowerCase().includes(search)
      );
    }

    // Filtre par secteur
    if (sectorFilter !== 'all') {
      filtered = filtered.filter((agreement) => agreement.sector === sectorFilter);
    }

    setFilteredCatalog(filtered);
  }, [searchTerm, sectorFilter, catalog]);

  const fetchCatalog = async () => {
    setIsLoading(true);
    try {
      const response = await collectiveAgreementsApi.getCatalog({ active_only: false });
      const items = response.data || [];
      setCatalog(items);
      void fetchRulesStatuses(items);
    } catch (err: any) {
      log.error('Erreur lors de la récupération du catalogue:', err);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger le catalogue des conventions collectives.',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchRulesStatuses = async (
    items: collectiveAgreementsApi.CollectiveAgreementCatalog[]
  ) => {
    const results = await Promise.allSettled(
      items.map((item) => collectiveAgreementsApi.getRulesStatus(item.id))
    );
    const map: Record<string, collectiveAgreementsApi.RulesStatusResponse> = {};
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        map[items[index].id] = result.value.data;
      }
    });
    setRulesStatusMap(map);
  };

  const handleExtractRules = async (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog
  ) => {
    const textSource = rulesStatusMap[agreement.id]?.text_source;
    const hasText =
      textSource === 'kali' || textSource === 'text' || textSource === 'pdf';
    if (!agreement.rules_pdf_path && !hasText) {
      toast({
        title: 'Texte requis',
        description:
          'Importez depuis Légifrance ou uploadez un PDF avant d\'extraire les règles paie.',
        variant: 'destructive',
      });
      return;
    }
    setExtractingId(agreement.id);
    try {
      const response = await collectiveAgreementsApi.extractRules(agreement.id);
      const data = response.data;
      if (data.success) {
        toast({
          title: 'Règles extraites',
          description: `IDCC ${data.idcc} — confiance ${data.confidence ?? 'n/a'}`,
        });
        if (data.confidence === 'low') {
          toast({
            title: 'Attention',
            description: 'Confiance faible : vérifiez le JSON extrait.',
            variant: 'destructive',
          });
        }
      } else {
        toast({
          title: 'Extraction échouée',
          description: data.error ?? 'Validation ou IA en échec',
          variant: 'destructive',
        });
      }
      const statusRes = await collectiveAgreementsApi.getRulesStatus(agreement.id);
      setRulesStatusMap((prev) => ({ ...prev, [agreement.id]: statusRes.data }));
    } catch (err: any) {
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Extraction impossible',
        variant: 'destructive',
      });
    } finally {
      setExtractingId(null);
    }
  };

  const handleViewRules = (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog
  ) => {
    const status = rulesStatusMap[agreement.id];
    setRulesModalTitle(`${agreement.name} (IDCC ${agreement.idcc})`);
    setRulesModalContent(status?.rules ?? null);
    setRulesModalOpen(true);
  };

  const renderRulesBadge = (agreementId: string) => {
    const status = rulesStatusMap[agreementId];
    if (!status) {
      return <Badge variant="secondary">…</Badge>;
    }
    if (status.has_rules) {
      const lowConf = status.confidence === 'low';
      return (
        <Badge variant={lowConf ? 'destructive' : 'default'} className={lowConf ? '' : 'bg-green-600'}>
          {lowConf ? 'OK (faible)' : 'OK'}
        </Badge>
      );
    }
    if (status.latest_log_status === 'rejected_validation' || status.latest_log_status === 'error') {
      return <Badge variant="destructive">Erreur</Badge>;
    }
    return <Badge variant="outline">Manquant</Badge>;
  };

  const renderTextSourceBadge = (agreementId: string) => {
    const source = rulesStatusMap[agreementId]?.text_source;
    if (!source) return <Badge variant="secondary">…</Badge>;
    if (source === 'kali') {
      return <Badge className="bg-blue-600">Légifrance</Badge>;
    }
    if (source === 'pdf') {
      return <Badge variant="secondary">PDF</Badge>;
    }
    if (source === 'text') {
      return <Badge variant="secondary">Texte</Badge>;
    }
    return <Badge variant="outline">Manquant</Badge>;
  };

  const refreshAgreementStatus = async (agreementId: string) => {
    const statusRes = await collectiveAgreementsApi.getRulesStatus(agreementId);
    setRulesStatusMap((prev) => ({ ...prev, [agreementId]: statusRes.data }));
  };

  const handleImportKali = async () => {
    const idcc = importIdcc.trim();
    if (!idcc) {
      toast({ title: 'IDCC requis', description: 'Saisissez un numéro IDCC.', variant: 'destructive' });
      return;
    }
    setIsImportingKali(true);
    try {
      const res = await collectiveAgreementsApi.importFromLegifrance({
        idcc,
        extract_rules: true,
      });
      const data = res.data;
      if (data.success) {
        toast({
          title: 'Import Légifrance réussi',
          description: `${data.title ?? 'CC'} — ${data.character_count?.toLocaleString('fr-FR') ?? 0} caractères`,
        });
        if (data.rules && !data.rules.success) {
          toast({
            title: 'Règles paie non extraites',
            description: data.rules.error ?? 'Validation IA en échec',
            variant: 'destructive',
          });
        }
        await fetchCatalog();
        if (data.agreement_id) {
          await refreshAgreementStatus(data.agreement_id);
        }
        setImportIdcc('');
      } else {
        toast({
          title: 'Import échoué',
          description: data.error ?? 'Erreur API Légifrance',
          variant: 'destructive',
        });
      }
    } catch (err: any) {
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Import impossible',
        variant: 'destructive',
      });
    } finally {
      setIsImportingKali(false);
    }
  };

  const handleBatchImportKali = async () => {
    setIsBatchImportingKali(true);
    try {
      const res = await collectiveAgreementsApi.importFromLegifranceBatch({
        priority_only: true,
        extract_rules: true,
      });
      const data = res.data;
      toast({
        title: 'Import lot prioritaire terminé',
        description: `${data.succeeded}/${data.total} réussis`,
        variant: data.failed > 0 ? 'destructive' : 'default',
      });
      await fetchCatalog();
    } catch (err: any) {
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Import batch impossible',
        variant: 'destructive',
      });
    } finally {
      setIsBatchImportingKali(false);
    }
  };

  const handleReimportKali = async (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog
  ) => {
    setReimportingId(agreement.id);
    try {
      const res = await collectiveAgreementsApi.reimportFromLegifrance(agreement.id);
      const data = res.data;
      if (data.success) {
        toast({
          title: 'Texte Légifrance mis à jour',
          description: `${data.character_count?.toLocaleString('fr-FR') ?? 0} caractères`,
        });
        await refreshAgreementStatus(agreement.id);
        await fetchCatalog();
      } else {
        toast({
          title: 'Ré-import échoué',
          description: data.error ?? 'Erreur',
          variant: 'destructive',
        });
      }
    } catch (err: any) {
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Ré-import impossible',
        variant: 'destructive',
      });
    } finally {
      setReimportingId(null);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingAgreement(null);
    setFormData({
      name: '',
      idcc: '',
      description: '',
      sector: '',
      effective_date: '',
      is_active: true,
    });
    setPdfFile(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (agreement: collectiveAgreementsApi.CollectiveAgreementCatalog) => {
    setEditingAgreement(agreement);
    setFormData({
      name: agreement.name,
      idcc: agreement.idcc,
      description: agreement.description || '',
      sector: agreement.sector || '',
      effective_date: agreement.effective_date || '',
      is_active: agreement.is_active,
    });
    setPdfFile(null);
    setIsModalOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.idcc) {
      toast({
        title: 'Erreur',
        description: 'Le nom et l\'IDCC sont obligatoires.',
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      let agreementId = editingAgreement?.id;

      // Nettoyer les données : convertir les strings vides en undefined
      const cleanedData = {
        ...formData,
        description: formData.description || undefined,
        sector: formData.sector || undefined,
        effective_date: formData.effective_date || undefined,
      };

      // 1. Créer ou mettre à jour la convention
      if (editingAgreement) {
        await collectiveAgreementsApi.updateCatalogItem(editingAgreement.id, cleanedData as any);
        toast({ title: 'Succès', description: 'Convention mise à jour avec succès.' });
      } else {
        const response = await collectiveAgreementsApi.createCatalogItem(cleanedData as any);
        agreementId = response.data.id;
        toast({ title: 'Succès', description: 'Convention créée avec succès.' });
      }

      // 2. Si un PDF est fourni, l'uploader
      if (pdfFile && agreementId) {
        await handleUploadPdf(agreementId, pdfFile);
      }

      setIsModalOpen(false);
      await fetchCatalog();
    } catch (err: any) {
      let errorMsg = 'Une erreur est survenue.';

      // Gérer les erreurs de validation Pydantic (422)
      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          errorMsg = err.response.data.detail.map((e: any) => e.msg).join(', ');
        } else if (typeof err.response.data.detail === 'string') {
          errorMsg = err.response.data.detail;
        }
      } else if (err.message) {
        errorMsg = err.message;
      }

      toast({ title: 'Erreur', description: errorMsg, variant: 'destructive' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUploadPdf = async (agreementId: string, file: File) => {
    setIsUploading(true);
    try {
      // 1. Obtenir une URL signée pour l'upload
      const uploadResponse = await collectiveAgreementsApi.getUploadUrl(file.name);
      const { signedURL, path } = uploadResponse.data;

      // 2. Uploader le fichier
      await collectiveAgreementsApi.uploadPdfToSignedUrl(signedURL, file);

      // 3. Mettre à jour la convention avec le chemin du fichier
      await collectiveAgreementsApi.updateCatalogItem(agreementId, {
        rules_pdf_path: path,
        rules_pdf_filename: file.name,
      });

      toast({ title: 'Succès', description: 'PDF uploadé avec succès.' });
    } catch (err: any) {
      let errorMsg = 'Échec de l\'upload du PDF.';

      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          errorMsg = err.response.data.detail.map((e: any) => e.msg).join(', ');
        } else if (typeof err.response.data.detail === 'string') {
          errorMsg = err.response.data.detail;
        }
      } else if (err.message) {
        errorMsg = err.message;
      }

      toast({ title: 'Erreur', description: errorMsg, variant: 'destructive' });
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemovePdf = async () => {
    if (!editingAgreement?.id) return;

    try {
      await collectiveAgreementsApi.updateCatalogItem(editingAgreement.id, {
        rules_pdf_path: null as any,
        rules_pdf_filename: null as any,
      });

      toast({ title: 'Succès', description: 'PDF supprimé avec succès.' });

      // Mettre à jour l'état local
      setFormData({
        ...formData,
      });

      // Rafraîchir le catalogue pour refléter les changements
      await fetchCatalog();

      // Mettre à jour les données d'édition
      if (editingAgreement) {
        setEditingAgreement({
          ...editingAgreement,
          rules_pdf_path: null,
          rules_pdf_filename: null,
        });
      }
    } catch (err: any) {
      let errorMsg = 'Échec de la suppression du PDF.';

      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          errorMsg = err.response.data.detail.map((e: any) => e.msg).join(', ');
        } else if (typeof err.response.data.detail === 'string') {
          errorMsg = err.response.data.detail;
        }
      } else if (err.message) {
        errorMsg = err.message;
      }

      toast({ title: 'Erreur', description: errorMsg, variant: 'destructive' });
    }
  };

  const handleDeleteClick = (agreement: collectiveAgreementsApi.CollectiveAgreementCatalog) => {
    setAgreementToDelete(agreement);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!agreementToDelete) return;

    try {
      await collectiveAgreementsApi.deleteCatalogItem(agreementToDelete.id);
      toast({ title: 'Succès', description: 'Convention supprimée.' });
      setDeleteDialogOpen(false);
      setAgreementToDelete(null);
      await fetchCatalog();
    } catch (err: any) {
      let errorMsg = 'Une erreur est survenue.';

      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          errorMsg = err.response.data.detail.map((e: any) => e.msg).join(', ');
        } else if (typeof err.response.data.detail === 'string') {
          errorMsg = err.response.data.detail;
        }
      } else if (err.message) {
        errorMsg = err.message;
      }

      toast({ title: 'Erreur', description: errorMsg, variant: 'destructive' });
    }
  };

  const handleDownload = (agreement: collectiveAgreementsApi.CollectiveAgreementCatalog) => {
    const pdfUrl = agreement.rules_pdf_url;
    if (!pdfUrl) {
      toast({
        title: 'Erreur',
        description: 'Aucun fichier PDF disponible pour cette convention.',
        variant: 'destructive'
      });
      return;
    }

    window.open(pdfUrl, '_blank');
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-96">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Conventions collectives"
        description="Catalogue IDCC et suivi des assignations par entreprise."
        actions={
          <Button onClick={handleOpenCreateModal}>
            <Plus className="mr-2 h-4 w-4" />
            Nouvelle convention
          </Button>
        }
      />

      <Card className="border-blue-200 bg-blue-50/40 dark:border-blue-900 dark:bg-blue-950/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Landmark className="h-5 w-5 text-blue-600" />
            Importer depuis Légifrance (officiel)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Récupère le texte officiel KALI via l&apos;API PISTE, crée ou met à jour la fiche
            catalogue, puis extrait automatiquement les règles paie. Nécessite{' '}
            <code className="text-xs">PISTE_CLIENT_ID</code> et{' '}
            <code className="text-xs">PISTE_CLIENT_SECRET</code> côté backend.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="import-idcc">IDCC</Label>
              <Input
                id="import-idcc"
                placeholder="Ex. 1486"
                value={importIdcc}
                onChange={(e) => setImportIdcc(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void handleImportKali()}
              />
            </div>
            <Button onClick={() => void handleImportKali()} disabled={isImportingKali}>
              {isImportingKali ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Landmark className="mr-2 h-4 w-4" />
              )}
              Importer
            </Button>
            <Button
              variant="outline"
              onClick={() => void handleBatchImportKali()}
              disabled={isBatchImportingKali}
            >
              {isBatchImportingKali ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Lot prioritaire (5 IDCC)
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Assignations par entreprise</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {companyAssignments.length === 0 ? (
            <p className="text-muted-foreground">Chargement ou aucune donnée.</p>
          ) : (
            <>
              <p className="text-muted-foreground">
                {companyAssignments.filter((c) => c.assigned_agreements.length === 0).length}{' '}
                entreprise(s) sans convention assignée sur {companyAssignments.length}.
              </p>
              <ul className="max-h-40 space-y-1 overflow-y-auto">
                {companyAssignments
                  .filter((c) => c.assigned_agreements.length === 0)
                  .slice(0, 8)
                  .map((c) => (
                    <li key={c.id} className="flex items-center gap-2 text-amber-700 dark:text-amber-400">
                      <XCircle className="h-3.5 w-3.5 shrink-0" />
                      {c.company_name}
                    </li>
                  ))}
              </ul>
            </>
          )}
        </CardContent>
      </Card>

      {/* Filtres */}
      <Card>
        <CardHeader>
          <CardTitle>Filtres</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-2">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Rechercher par nom ou IDCC..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={sectorFilter} onValueChange={setSectorFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Tous les secteurs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les secteurs</SelectItem>
                {sectors.map((sector) => (
                  <SelectItem key={sector} value={sector}>
                    {sector}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Tableau */}
      <Card>
        <CardHeader>
          <CardTitle>
            Conventions ({filteredCatalog.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nom</TableHead>
                <TableHead>IDCC</TableHead>
                <TableHead>Secteur</TableHead>
                <TableHead>PDF</TableHead>
                <TableHead>Texte</TableHead>
                <TableHead>Règles paie</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredCatalog.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                    <FileText className="mx-auto h-8 w-8 mb-2" />
                    Aucune convention trouvée
                  </TableCell>
                </TableRow>
              ) : (
                filteredCatalog.map((agreement) => (
                  <TableRow key={agreement.id}>
                    <TableCell className="font-medium">{agreement.name}</TableCell>
                    <TableCell>{agreement.idcc}</TableCell>
                    <TableCell>
                      {agreement.sector ? (
                        <Badge variant="secondary">{agreement.sector}</Badge>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {agreement.rules_pdf_path ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownload(agreement)}
                        >
                          <Download className="h-4 w-4 text-green-600" />
                        </Button>
                      ) : (
                        <XCircle className="h-4 w-4 text-muted-foreground" />
                      )}
                    </TableCell>
                    <TableCell>{renderTextSourceBadge(agreement.id)}</TableCell>
                    <TableCell>{renderRulesBadge(agreement.id)}</TableCell>
                    <TableCell>
                      {agreement.is_active ? (
                        <Badge variant="default" className="bg-green-600">
                          <CheckCircle className="mr-1 h-3 w-3" />
                          Actif
                        </Badge>
                      ) : (
                        <Badge variant="secondary">
                          <XCircle className="mr-1 h-3 w-3" />
                          Inactif
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Importer / mettre à jour depuis Légifrance"
                          disabled={reimportingId === agreement.id}
                          onClick={() => void handleReimportKali(agreement)}
                        >
                          {reimportingId === agreement.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Landmark className="h-4 w-4 text-blue-600" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Extraire règles paie (IA)"
                          disabled={extractingId === agreement.id}
                          onClick={() => handleExtractRules(agreement)}
                        >
                          {extractingId === agreement.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Sparkles className="h-4 w-4 text-violet-600" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Voir JSON règles"
                          disabled={!rulesStatusMap[agreement.id]?.has_rules}
                          onClick={() => handleViewRules(agreement)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenEditModal(agreement)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteClick(agreement)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Modal de création/édition */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingAgreement ? 'Modifier la Convention' : 'Nouvelle Convention'}
            </DialogTitle>
            <DialogDescription>
              {editingAgreement
                ? 'Modifiez les informations de la convention collective.'
                : 'Ajoutez une nouvelle convention collective au catalogue.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nom complet *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Convention collective nationale..."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="idcc">IDCC *</Label>
              <Input
                id="idcc"
                value={formData.idcc}
                onChange={(e) => setFormData({ ...formData, idcc: e.target.value })}
                placeholder="1234"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="sector">Secteur</Label>
              <Select
                value={formData.sector}
                onValueChange={(value) => setFormData({ ...formData, sector: value })}
              >
                <SelectTrigger id="sector">
                  <SelectValue placeholder="Sélectionner un secteur" />
                </SelectTrigger>
                <SelectContent>
                  {sectors.map((sector) => (
                    <SelectItem key={sector} value={sector}>
                      {sector}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Description de la convention..."
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="effective_date">Date d'effet</Label>
              <Input
                id="effective_date"
                type="date"
                value={formData.effective_date}
                onChange={(e) => setFormData({ ...formData, effective_date: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label>Statut</Label>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="h-4 w-4"
                />
                <Label htmlFor="is_active" className="font-normal">
                  Convention active
                </Label>
              </div>
            </div>

            <div className="space-y-2">
              <Label>PDF des règles</Label>
              <div className="flex items-center gap-2">
                <Input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                  className="flex-1"
                />
                {pdfFile && (
                  <Badge variant="secondary">
                    <FileText className="mr-1 h-3 w-3" />
                    {pdfFile.name}
                  </Badge>
                )}
              </div>
              {editingAgreement?.rules_pdf_path && (
                <div className="flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">
                    PDF actuel : {editingAgreement.rules_pdf_filename}
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleRemovePdf}
                    className="text-red-500 hover:text-red-700 hover:bg-red-50"
                  >
                    <Trash2 className="mr-1 h-3 w-3" />
                    Supprimer le PDF
                  </Button>
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsModalOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting || isUploading}>
              {(isSubmitting || isUploading) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingAgreement ? 'Mettre à jour' : 'Créer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog de confirmation de suppression */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Êtes-vous sûr ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action supprimera définitivement la convention "{agreementToDelete?.name}" du
              catalogue. Les entreprises qui l'utilisent ne pourront plus y accéder.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-red-600 hover:bg-red-700">
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Modal JSON règles paie */}
      <Dialog open={rulesModalOpen} onOpenChange={setRulesModalOpen}>
        <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Règles paie — {rulesModalTitle}</DialogTitle>
            <DialogDescription>
              JSON structuré consommé par le moteur de paie (lecture seule).
            </DialogDescription>
          </DialogHeader>
          <pre className="rounded-md bg-muted p-4 text-xs overflow-x-auto whitespace-pre-wrap">
            {rulesModalContent
              ? JSON.stringify(rulesModalContent, null, 2)
              : 'Aucune règle extraite.'}
          </pre>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRulesModalOpen(false)}>
              Fermer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
