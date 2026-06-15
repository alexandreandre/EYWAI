// frontend/src/pages/super-admin/CollectiveAgreementsCatalog.tsx

import { log } from '@/lib/logger';
import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
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
import { Switch } from '@/components/ui/switch';
import {
  FileText,
  Loader2,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  X,
  XCircle,
} from 'lucide-react';
import axios from 'axios';
import * as collectiveAgreementsApi from '@/api/collectiveAgreements';
import { CollectiveAgreementRow } from '@/components/collective-agreements/CollectiveAgreementRow';
import { CollectiveAgreementAssignDialog } from '@/components/collective-agreements/CollectiveAgreementAssignDialog';
import type { CollectiveAgreementAssignResult } from '@/components/collective-agreements/CollectiveAgreementAssignDialog';
import { ConventionDocumentViewerDialog } from '@/components/collective-agreements/ConventionDocumentViewerDialog';
import type { DocumentLoadingKind } from '@/components/collective-agreements/CollectiveAgreementRow';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { formatCatalogConventionName } from '@/lib/collectiveAgreementDisplay';
import {
  getReadinessFromRulesStatus,
  getPayrollGridUnavailableReason,
  hasCachedTextFromSource,
  hasPayrollGridFromRules,
  extractLegifranceUrlFromDescription,
} from '@/lib/collectiveAgreementReadiness';
import { printRulesPdfFromJson } from '@/lib/collectiveAgreementRulesPdf';
import { useConventionDocumentViewer } from '@/hooks/useConventionDocumentViewer';
import type { ConventionDocumentKind } from '@/lib/collectiveAgreementDocumentCache';

export default function CollectiveAgreementsCatalog() {
  const { toast } = useToast();
  const { viewer, openDocument, closeViewer, downloadFromViewer } =
    useConventionDocumentViewer();

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
  const [rulesModalOpen, setRulesModalOpen] = useState(false);
  const [rulesModalContent, setRulesModalContent] = useState<Record<string, unknown> | null>(null);
  const [rulesModalTitle, setRulesModalTitle] = useState('');
  const [rulesModalIdcc, setRulesModalIdcc] = useState('');
  const [rulesModalAgreementName, setRulesModalAgreementName] = useState('');
  const [trainingModalAgreement, setTrainingModalAgreement] =
    useState<collectiveAgreementsApi.CollectiveAgreementCatalog | null>(null);
  const [trainingRecos, setTrainingRecos] = useState<
    collectiveAgreementsApi.CcTrainingRecommendation[]
  >([]);
  const [trainingRecosLoading, setTrainingRecosLoading] = useState(false);
  const [extractingTrainingsId, setExtractingTrainingsId] = useState<string | null>(null);
  const [docLoading, setDocLoading] = useState<{
    id: string;
    kind: DocumentLoadingKind;
  } | null>(null);

  // Import Légifrance (KALI)
  const [importIdcc, setImportIdcc] = useState('');
  const [updateAgreementId, setUpdateAgreementId] = useState('');
  const [isImportingKali, setIsImportingKali] = useState(false);
  const [isSyncingCatalog, setIsSyncingCatalog] = useState(false);
  const [reimportingId, setReimportingId] = useState<string | null>(null);
  const [isCancellingImport, setIsCancellingImport] = useState(false);
  const kaliImportAbortRef = useRef<AbortController | null>(null);
  const [assignDialogAgreement, setAssignDialogAgreement] =
    useState<collectiveAgreementsApi.CollectiveAgreementCatalog | null>(null);
  const [assignDialogCompany, setAssignDialogCompany] = useState<{
    id: string;
    company_name: string;
  } | null>(null);

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

  const refreshCompanyAssignments = async () => {
    try {
      const res = await collectiveAgreementsApi.getAllCompanyAssignments();
      setCompanyAssignments(res.data ?? []);
    } catch (err) {
      log.error('Erreur lors du rafraîchissement des assignations:', err);
    }
  };

  const handleCompanyAssigned = async (result: CollectiveAgreementAssignResult) => {
    if (result.agreementDetails) {
      setCompanyAssignments((prev) =>
        prev.map((company) => {
          if (company.id !== result.companyId) return company;
          if (
            company.assigned_agreements.some(
              (assignment) =>
                assignment.collective_agreement_id === result.collectiveAgreementId
            )
          ) {
            return company;
          }
          return {
            ...company,
            assigned_agreements: [
              ...company.assigned_agreements,
              {
                id: `optimistic-${result.collectiveAgreementId}`,
                company_id: result.companyId,
                collective_agreement_id: result.collectiveAgreementId,
                assigned_at: new Date().toISOString(),
                agreement_details: result.agreementDetails!,
              },
            ],
          };
        })
      );
    }
    await refreshCompanyAssignments();
    setAssignDialogAgreement(null);
    setAssignDialogCompany(null);
  };

  useEffect(() => {
    fetchCatalog();
    void refreshCompanyAssignments();
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

  const handleViewRules = (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog
  ) => {
    const status = rulesStatusMap[agreement.id];
    setRulesModalTitle(`IDCC ${agreement.idcc}`);
    setRulesModalIdcc(agreement.idcc);
    setRulesModalAgreementName(formatCatalogConventionName(agreement.name));
    setRulesModalContent(status?.rules ?? null);
    setRulesModalOpen(true);
  };

  const loadTrainingRecommendations = async (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog
  ) => {
    setTrainingRecosLoading(true);
    try {
      const res = await collectiveAgreementsApi.listTrainingRecommendations(agreement.id);
      setTrainingRecos(res.data ?? []);
    } catch (err: unknown) {
      toast({
        title: 'Erreur',
        description: await parseApiErrorDetail(err, 'Impossible de charger les propositions formation.'),
        variant: 'destructive',
      });
      setTrainingRecos([]);
    } finally {
      setTrainingRecosLoading(false);
    }
  };

  const handleOpenTrainingModal = (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog
  ) => {
    setTrainingModalAgreement(agreement);
    void loadTrainingRecommendations(agreement);
  };

  const handleExtractTrainings = async () => {
    if (!trainingModalAgreement) return;
    setExtractingTrainingsId(trainingModalAgreement.id);
    try {
      const res = await collectiveAgreementsApi.extractTrainings(trainingModalAgreement.id);
      const data = res.data;
      if (data.success) {
        toast({
          title: 'Extraction terminée',
          description: `${data.count} proposition(s) enregistrée(s) pour l'IDCC ${data.idcc}.`,
        });
        setTrainingRecos(data.recommendations ?? []);
      } else {
        toast({
          title: 'Extraction échouée',
          description: data.error ?? 'Erreur inconnue',
          variant: 'destructive',
        });
      }
    } catch (err: unknown) {
      toast({
        title: 'Erreur',
        description: await parseApiErrorDetail(err, "Impossible d'extraire les formations."),
        variant: 'destructive',
      });
    } finally {
      setExtractingTrainingsId(null);
    }
  };

  const handleToggleTrainingReco = async (
    reco: collectiveAgreementsApi.CcTrainingRecommendation,
    isActive: boolean
  ) => {
    try {
      const res = await collectiveAgreementsApi.patchTrainingRecommendation(reco.id, {
        is_active: isActive,
      });
      setTrainingRecos((prev) =>
        prev.map((r) => (r.id === reco.id ? { ...r, ...res.data } : r))
      );
    } catch (err: unknown) {
      toast({
        title: 'Erreur',
        description: await parseApiErrorDetail(err, 'Mise à jour impossible.'),
        variant: 'destructive',
      });
    }
  };

  const parseApiErrorDetail = async (err: any, fallback: string): Promise<string> => {
    let detail = err?.response?.data?.detail || err?.message || fallback;
    if (err?.response?.data instanceof Blob) {
      try {
        const text = await err.response.data.text();
        detail = JSON.parse(text)?.detail || detail;
      } catch {
        /* garde le message par défaut */
      }
    }
    return detail;
  };

  const handleViewDocument = async (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog,
    kind: ConventionDocumentKind
  ) => {
    const textSource = rulesStatusMap[agreement.id]?.text_source;
    if (!hasCachedTextFromSource(textSource) && !agreement.rules_pdf_path) {
      toast({
        title: 'Texte indisponible',
        description: 'Importez la convention depuis Légifrance avant de générer le PDF.',
        variant: 'destructive',
      });
      return;
    }

    setDocLoading({ id: agreement.id, kind });
    try {
      await openDocument({
        agreementId: agreement.id,
        idcc: agreement.idcc,
        agreementName: formatCatalogConventionName(agreement.name),
        kind,
        sourceTextHash: rulesStatusMap[agreement.id]?.source_text_hash,
      });
    } finally {
      setDocLoading(null);
    }
  };

  const handleExportRulesPdf = (params: {
    rules: Record<string, unknown>;
    agreementName: string;
    idcc: string;
    loadingId?: string;
  }) => {
    setDocLoading(
      params.loadingId ? { id: params.loadingId, kind: 'rules' } : null
    );
    try {
      printRulesPdfFromJson({
        rules: params.rules,
        agreementName: params.agreementName,
        idcc: params.idcc,
      });
    } catch (err: any) {
      toast({
        title: 'Erreur',
        description: err?.message ?? 'Export PDF impossible',
        variant: 'destructive',
      });
    } finally {
      if (params.loadingId) {
        window.setTimeout(() => setDocLoading(null), 400);
      }
    }
  };

  const handleExportRulesPdfForAgreement = (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog,
    rules?: Record<string, unknown> | null
  ) => {
    const payload = rules ?? rulesStatusMap[agreement.id]?.rules;
    const status = rulesStatusMap[agreement.id];
    if (!payload || !hasPayrollGridFromRules(payload)) {
      toast({
        title: 'Grille indisponible',
        description:
          getPayrollGridUnavailableReason(status) ??
          'Relancez « Mettre à jour » pour extraire les minima salariaux.',
        variant: 'destructive',
      });
      return;
    }
    handleExportRulesPdf({
      rules: payload,
      agreementName: formatCatalogConventionName(agreement.name),
      idcc: agreement.idcc,
      loadingId: agreement.id,
    });
  };

  const getCompletudeFromRules = (rules: Record<string, unknown> | null | undefined) => {
    const completude = rules?.completude as
      | { niveau?: string; avertissements?: string[]; grilles_count?: number }
      | undefined;
    return completude;
  };

  const getRowLoading = (agreementId: string): DocumentLoadingKind | null => {
    if (docLoading?.id === agreementId) return docLoading.kind;
    if (reimportingId === agreementId) return 'sync';
    return null;
  };

  const isKaliImportRunning = Boolean(
    isImportingKali || isSyncingCatalog || reimportingId
  );

  const isAbortError = (err: unknown) =>
    axios.isCancel(err) ||
    (err instanceof DOMException && err.name === 'AbortError') ||
    (typeof err === 'object' &&
      err !== null &&
      'code' in err &&
      (err as { code?: string }).code === 'ERR_CANCELED');

  const formatKaliBatchFailureDetails = (
    results: collectiveAgreementsApi.KaliImportResponse[],
    limit = 2
  ) =>
    results
      .filter((result) => !result.success && result.error)
      .slice(0, limit)
      .map((result) => `IDCC ${result.idcc} : ${result.error}`)
      .join(' · ');

  const beginKaliImportRequest = () => {
    kaliImportAbortRef.current?.abort();
    const controller = new AbortController();
    kaliImportAbortRef.current = controller;
    return controller.signal;
  };

  const finishKaliImportRequest = () => {
    kaliImportAbortRef.current = null;
  };

  const handleCancelKaliImport = async () => {
    if (!isKaliImportRunning || isCancellingImport) return;
    setIsCancellingImport(true);
    try {
      if (isSyncingCatalog) {
        await collectiveAgreementsApi.cancelKaliImport({ catalog_sync: true });
      } else if (reimportingId) {
        const agreement = catalog.find((item) => item.id === reimportingId);
        if (agreement) {
          await collectiveAgreementsApi.cancelKaliImport({ idcc: agreement.idcc });
        }
      } else if (isImportingKali && importIdcc.trim()) {
        await collectiveAgreementsApi.cancelKaliImport({ idcc: importIdcc.trim() });
      }
      kaliImportAbortRef.current?.abort();
    } catch (err: unknown) {
      toast({
        title: 'Erreur',
        description:
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? "Impossible d'annuler la mise à jour",
        variant: 'destructive',
      });
    } finally {
      setIsCancellingImport(false);
    }
  };

  const notifyRulesExtraction = (data: collectiveAgreementsApi.KaliImportResponse) => {
    if (data.rules_skipped) {
      return;
    }
    const rules = data.rules;
    if (!rules) return;
    if (rules.success) {
      toast({
        title: 'Règles paie mises à jour',
        description: `IDCC ${data.idcc} — confiance ${rules.confidence ?? 'n/a'}`,
      });
      if (rules.confidence === 'low') {
        toast({
          title: 'Attention',
          description: 'Confiance faible sur les règles paie : vérifiez le détail technique.',
          variant: 'destructive',
        });
      }
      return;
    }
    toast({
      title: 'Règles paie non mises à jour',
      description: rules.error ?? 'Extraction ou validation en échec',
      variant: 'destructive',
    });
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
    const signal = beginKaliImportRequest();
    try {
      const res = await collectiveAgreementsApi.importFromLegifrance(
        {
          idcc,
          extract_rules: true,
        },
        { signal }
      );
      const data = res.data;
      if (data.cancelled) {
        toast({
          title: 'Import annulé',
          description: `IDCC ${data.idcc} — mise à jour interrompue.`,
        });
        return;
      }
      if (data.success) {
        toast({
          title: data.created ? 'Convention ajoutée' : 'Convention mise à jour',
          description: data.title ?? `IDCC ${data.idcc}`,
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
    } catch (err: unknown) {
      if (isAbortError(err)) {
        toast({
          title: 'Import annulé',
          description: 'La mise à jour Légifrance a été interrompue.',
        });
        return;
      }
      toast({
        title: 'Erreur',
        description:
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'Import impossible',
        variant: 'destructive',
      });
    } finally {
      finishKaliImportRequest();
      setIsImportingKali(false);
    }
  };

  const handleSyncCatalog = async () => {
    setIsSyncingCatalog(true);
    const signal = beginKaliImportRequest();
    try {
      const res = await collectiveAgreementsApi.syncCatalogFromLegifrance(
        { extract_rules: true },
        { signal }
      );
      const data = res.data;
      if ((data.cancelled ?? 0) > 0) {
        toast({
          title: 'Mise à jour interrompue',
          description: `${data.succeeded} convention(s) traitée(s) avant l'annulation.`,
        });
        await fetchCatalog();
        return;
      }
      const failed = data.failed > 0;
      const failureDetails = failed ? formatKaliBatchFailureDetails(data.results) : '';
      toast({
        title: failed ? 'Mise à jour partielle' : 'Mise à jour terminée',
        description: failed
          ? [
              `${data.succeeded} convention(s) sur ${data.total} mises à jour.`,
              failureDetails,
            ]
              .filter(Boolean)
              .join(' ')
          : `${data.total} convention(s) vérifiée(s)${(data.updated ?? 0) > 0 ? `, ${data.updated} modifiée(s).` : '.'}`,
        variant: failed ? 'destructive' : 'default',
      });
      await fetchCatalog();
    } catch (err: unknown) {
      if (isAbortError(err)) {
        toast({
          title: 'Mise à jour interrompue',
          description: 'La synchronisation Légifrance a été annulée.',
        });
        return;
      }
      toast({
        title: 'Erreur',
        description:
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'La mise à jour a échoué.',
        variant: 'destructive',
      });
    } finally {
      finishKaliImportRequest();
      setIsSyncingCatalog(false);
    }
  };

  const handleUpdateSelectedConvention = async () => {
    const agreement = catalog.find((item) => item.id === updateAgreementId);
    if (!agreement) {
      toast({
        title: 'Convention requise',
        description: 'Choisissez une convention dans la liste.',
        variant: 'destructive',
      });
      return;
    }
    await handleReimportKali(agreement);
  };

  const handleReimportKali = async (
    agreement: collectiveAgreementsApi.CollectiveAgreementCatalog
  ) => {
    setReimportingId(agreement.id);
    const signal = beginKaliImportRequest();
    try {
      const res = await collectiveAgreementsApi.reimportFromLegifrance(
        agreement.id,
        true,
        { signal }
      );
      const data = res.data;
      if (data.cancelled) {
        toast({
          title: 'Mise à jour annulée',
          description: `${agreement.name} — import interrompu.`,
        });
        return;
      }
      if (data.success) {
        toast({
          title: data.text_changed === false ? 'Déjà à jour' : 'Convention mise à jour',
          description:
            data.text_changed === false
              ? `${agreement.name} — aucun changement détecté sur Légifrance.`
              : agreement.name,
        });
        notifyRulesExtraction(data);
        await refreshAgreementStatus(agreement.id);
        await fetchCatalog();
      } else {
        toast({
          title: 'Ré-import échoué',
          description: data.error ?? 'Erreur',
          variant: 'destructive',
        });
      }
    } catch (err: unknown) {
      if (isAbortError(err)) {
        toast({
          title: 'Mise à jour annulée',
          description: 'La mise à jour Légifrance a été interrompue.',
        });
        return;
      }
      toast({
        title: 'Erreur',
        description:
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'Ré-import impossible',
        variant: 'destructive',
      });
    } finally {
      finishKaliImportRequest();
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
    return <SharkFinLoader variant="fullPage" label="Chargement du catalogue…" />;
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

      <Card className="relative">
        {(isSyncingCatalog || isImportingKali) && (
          <button
            type="button"
            className="absolute right-3 top-3 z-10 flex h-7 w-7 items-center justify-center rounded-md text-red-600 transition-colors hover:bg-red-50 hover:text-red-700 disabled:opacity-50 dark:hover:bg-red-950/40"
            onClick={() => void handleCancelKaliImport()}
            disabled={isCancellingImport}
            aria-label="Annuler la mise à jour Légifrance"
          >
            {isCancellingImport ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <X className="h-4 w-4" />
            )}
          </button>
        )}
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <RefreshCw className="h-5 w-5 text-muted-foreground" />
            Mise à jour Légifrance
          </CardTitle>
          <CardDescription>
            Actualise les textes officiels et les règles de paie. Automatique le 1er de
            chaque mois — vous pouvez aussi lancer une mise à jour manuelle.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <Button
            onClick={() => void handleSyncCatalog()}
            disabled={isSyncingCatalog || isCancellingImport}
          >
            {isSyncingCatalog ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Mettre à jour tout le catalogue
          </Button>

          <div className="border-t pt-4 space-y-3">
            <p className="text-sm font-medium">Mettre à jour une convention</p>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Select value={updateAgreementId} onValueChange={setUpdateAgreementId}>
                <SelectTrigger className="sm:max-w-md">
                  <SelectValue placeholder="Choisir une convention..." />
                </SelectTrigger>
                <SelectContent>
                  {catalog
                    .filter((item) => item.is_active)
                    .map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {formatCatalogConventionName(item.name)} (IDCC {item.idcc})
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                onClick={() => void handleUpdateSelectedConvention()}
                disabled={
                  !updateAgreementId ||
                  (reimportingId === updateAgreementId && !isCancellingImport) ||
                  isCancellingImport
                }
              >
                {reimportingId === updateAgreementId ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Mettre à jour
              </Button>
            </div>
          </div>

          <div className="border-t pt-4 space-y-2">
            <p className="text-sm font-medium">Ajouter une nouvelle convention</p>
            <p className="text-xs text-muted-foreground">
              Si la convention n&apos;est pas encore dans le catalogue, saisissez son numéro IDCC.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Input
                id="import-idcc"
                placeholder="Numéro IDCC (ex. 1486)"
                value={importIdcc}
                onChange={(e) => setImportIdcc(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void handleImportKali()}
                className="sm:max-w-xs"
              />
              <Button
                variant="outline"
                onClick={() => void handleImportKali()}
                disabled={(isImportingKali && !isCancellingImport) || isCancellingImport}
              >
                {isImportingKali ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 h-4 w-4" />
                )}
                Ajouter
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Assignations par entreprise</CardTitle>
          <CardDescription>
            {companyAssignments.length > 0 && (
              <>
                {companyAssignments.filter((c) => c.assigned_agreements.length === 0).length}{' '}
                entreprise(s) sans convention sur {companyAssignments.length}.
              </>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {companyAssignments.length === 0 ? (
            <p className="text-muted-foreground">Chargement ou aucune donnée.</p>
          ) : (
            <ul className="max-h-72 space-y-2 overflow-y-auto">
              {companyAssignments.map((company) => {
                const hasAssignments = company.assigned_agreements.length > 0;
                return (
                  <li
                    key={company.id}
                    className="flex items-start justify-between gap-3 rounded-md border p-3"
                  >
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <p className="flex items-center gap-2 font-medium leading-tight">
                        {!hasAssignments && (
                          <XCircle className="h-3.5 w-3.5 shrink-0 text-amber-600" />
                        )}
                        <span className="truncate">{company.company_name}</span>
                      </p>
                      {hasAssignments ? (
                        <div className="flex flex-wrap gap-1">
                          {company.assigned_agreements.map((assignment) => (
                            <Badge key={assignment.id} variant="secondary" className="text-xs font-normal">
                              {formatCatalogConventionName(assignment.agreement_details?.name)}
                              {assignment.agreement_details?.idcc
                                ? ` · IDCC ${assignment.agreement_details.idcc}`
                                : ''}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-amber-700 dark:text-amber-400">
                          Aucune convention assignée
                        </p>
                      )}
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="shrink-0"
                      onClick={() => {
                        setAssignDialogAgreement(null);
                        setAssignDialogCompany({
                          id: company.id,
                          company_name: company.company_name,
                        });
                      }}
                    >
                      <Plus className="mr-1 h-3 w-3" />
                      Assigner
                    </Button>
                  </li>
                );
              })}
            </ul>
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

      {/* Liste des conventions */}
      <Card>
        <CardHeader>
          <CardTitle>Conventions ({filteredCatalog.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredCatalog.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <FileText className="mx-auto mb-2 h-8 w-8" />
              Aucune convention trouvée
            </div>
          ) : (
            <div className="space-y-3">
              {filteredCatalog.map((agreement) => {
                const status = rulesStatusMap[agreement.id];
                const hasText =
                  hasCachedTextFromSource(status?.text_source) ||
                  Boolean(agreement.rules_pdf_path);

                const hasRules = Boolean(status?.has_rules);
                const hasPayrollGrid = hasPayrollGridFromRules(status?.rules);

                return (
                  <CollectiveAgreementRow
                    key={agreement.id}
                    variant="admin"
                    name={formatCatalogConventionName(agreement.name)}
                    idcc={agreement.idcc}
                    sector={agreement.sector}
                    isActive={agreement.is_active}
                    readiness={getReadinessFromRulesStatus(status)}
                    hasText={hasText}
                    legifranceUrl={extractLegifranceUrlFromDescription(agreement.description)}
                    hasRules={hasRules}
                    hasPayrollGrid={hasPayrollGrid}
                    payrollGridUnavailableReason={getPayrollGridUnavailableReason(status)}
                    hasUploadedPdf={Boolean(agreement.rules_pdf_path)}
                    loading={getRowLoading(agreement.id)}
                    onViewFullText={() => void handleViewDocument(agreement, 'full-text')}
                    onViewSynthesis={() => void handleViewDocument(agreement, 'synthesis')}
                    onExportRulesPdf={() => handleExportRulesPdfForAgreement(agreement)}
                    onDownloadSourcePdf={() => handleDownload(agreement)}
                    onSync={() => void handleReimportKali(agreement)}
                    onCancelSync={() => void handleCancelKaliImport()}
                    isCancellingSync={isCancellingImport && reimportingId === agreement.id}
                    onAssignToCompany={() => {
                      setAssignDialogCompany(null);
                      setAssignDialogAgreement(agreement);
                    }}
                    onViewTechnical={() => handleViewRules(agreement)}
                    onManageTrainings={() => handleOpenTrainingModal(agreement)}
                    onEdit={() => handleOpenEditModal(agreement)}
                    onDelete={() => handleDeleteClick(agreement)}
                  />
                );
              })}
            </div>
          )}
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
            <DialogTitle>Détail technique — {rulesModalTitle}</DialogTitle>
            <DialogDescription>
              Données extraites pour le moteur de paie (lecture seule).
            </DialogDescription>
          </DialogHeader>
          {(() => {
            const completude = getCompletudeFromRules(rulesModalContent);
            if (!completude) return null;
            const variant =
              completude.niveau === 'complet'
                ? 'default'
                : completude.niveau === 'partiel'
                  ? 'outline'
                  : 'secondary';
            return (
              <div className="space-y-2 rounded-md border p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">Complétude :</span>
                  <Badge variant={variant}>{completude.niveau ?? 'inconnu'}</Badge>
                  {typeof completude.grilles_count === 'number' && completude.grilles_count > 0 && (
                    <span className="text-muted-foreground">
                      {completude.grilles_count} grille(s) salariale(s)
                    </span>
                  )}
                </div>
                {completude.avertissements && completude.avertissements.length > 0 && (
                  <ul className="list-disc pl-5 text-muted-foreground space-y-1">
                    {completude.avertissements.map((msg, i) => (
                      <li key={i}>{msg}</li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })()}
          <pre className="rounded-md bg-muted p-4 text-xs overflow-x-auto whitespace-pre-wrap">
            {rulesModalContent
              ? JSON.stringify(rulesModalContent, null, 2)
              : 'Aucune règle extraite.'}
          </pre>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              disabled={!rulesModalContent}
              onClick={() => {
                if (!rulesModalContent) return;
                handleExportRulesPdf({
                  rules: rulesModalContent,
                  agreementName: rulesModalAgreementName,
                  idcc: rulesModalIdcc,
                });
              }}
            >
              <FileText className="mr-2 h-4 w-4" />
              Exporter PDF règles paie
            </Button>
            <Button variant="ghost" onClick={() => setRulesModalOpen(false)}>
              Fermer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(trainingModalAgreement)}
        onOpenChange={(open) => {
          if (!open) {
            setTrainingModalAgreement(null);
            setTrainingRecos([]);
          }
        }}
      >
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Formations CC — IDCC {trainingModalAgreement?.idcc}
            </DialogTitle>
            <DialogDescription>
              Propositions extraites par IA depuis le texte de la convention. Activez ou
              désactivez avant publication aux entreprises assignées.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => void handleExtractTrainings()}
              disabled={
                !trainingModalAgreement ||
                extractingTrainingsId === trainingModalAgreement.id
              }
            >
              {extractingTrainingsId === trainingModalAgreement?.id ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Extraire les formations
            </Button>
          </div>
          {trainingRecosLoading ? (
            <div className="py-8 flex justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : trainingRecos.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">
              Aucune proposition. Lancez l&apos;extraction après import du texte Légifrance.
            </p>
          ) : (
            <div className="space-y-3">
              {trainingRecos.map((reco) => (
                <div
                  key={reco.id}
                  className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{reco.title}</span>
                      <Badge variant={reco.obligation_level === 'obligatoire' ? 'destructive' : 'secondary'}>
                        {reco.obligation_level === 'obligatoire' ? 'Obligatoire' : 'Recommandée'}
                      </Badge>
                      {!reco.is_active && (
                        <Badge variant="outline">Inactive</Badge>
                      )}
                    </div>
                    {reco.legal_reference ? (
                      <p className="text-xs text-muted-foreground">{reco.legal_reference}</p>
                    ) : null}
                    {reco.pedagogical_objective ? (
                      <p className="text-sm text-muted-foreground">{reco.pedagogical_objective}</p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Label htmlFor={`reco-active-${reco.id}`} className="text-xs">
                      Active
                    </Label>
                    <Switch
                      id={`reco-active-${reco.id}`}
                      checked={reco.is_active}
                      onCheckedChange={(checked) =>
                        void handleToggleTrainingReco(reco, Boolean(checked))
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTrainingModalAgreement(null)}>
              Fermer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConventionDocumentViewerDialog
        open={viewer.open}
        onOpenChange={(open) => {
          if (!open) closeViewer();
        }}
        title={viewer.title}
        subtitle={viewer.subtitle}
        pdfUrl={viewer.pdfUrl}
        loading={viewer.loading}
        canDownload={Boolean(viewer.blob)}
        onDownload={downloadFromViewer}
      />

      <CollectiveAgreementAssignDialog
        open={Boolean(assignDialogAgreement || assignDialogCompany)}
        onOpenChange={(open) => {
          if (!open) {
            setAssignDialogAgreement(null);
            setAssignDialogCompany(null);
          }
        }}
        companies={companyAssignments.map((a) => ({
          id: a.id,
          company_name: a.company_name,
        }))}
        fixedAgreement={assignDialogAgreement}
        fixedCompanyId={assignDialogCompany?.id}
        fixedCompanyName={assignDialogCompany?.company_name}
        excludedAgreementIds={
          assignDialogCompany
            ? (companyAssignments
                .find((c) => c.id === assignDialogCompany.id)
                ?.assigned_agreements.map((a) => a.collective_agreement_id) ?? [])
            : []
        }
        excludedCompanyIds={
          assignDialogAgreement
            ? companyAssignments
                .filter((a) =>
                  a.assigned_agreements.some(
                    (ag) => ag.collective_agreement_id === assignDialogAgreement.id
                  )
                )
                .map((a) => a.id)
            : []
        }
        onAssigned={(result) => void handleCompanyAssigned(result)}
      />
    </div>
  );
}
