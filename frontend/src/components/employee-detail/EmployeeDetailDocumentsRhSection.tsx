import { useMemo, useState, useEffect, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/components/ui/use-toast';
import {
  CONTRACT_TYPES,
  AVENANT_TYPES,
  ATTESTATION_COURANTE_TYPES,
  type DocumentGenMode,
} from '@/lib/documentGenerationConfig';
import {
  deleteDocument,
  downloadDocument,
  openDocumentPreview,
  triggerSignedDocumentDownload,
  generateDocument,
  getDocuments,
  updateDocumentStatus,
  type DocumentCategory,
  type GeneratedDocument,
} from '@/api/documents';
import { DOCUMENT_TYPE_LABELS, getTemplates, type DocumentTemplate } from '@/api/documentLibrary';
import { cn } from '@/lib/utils';
import { resolveGeneratedContractDocType } from '@/lib/employeeContractSetup';
import {
  ArrowDownToLine,
  ChevronDown,
  Eye,
  Loader2,
  Plus,
  Send,
  Settings2,
  Trash2,
  Upload,
} from 'lucide-react';

export const QK_EMPLOYEE_GENERATED_DOCS = (employeeId: string) =>
  ['employee-generated-documents', employeeId] as const;

const QK_FICHE_POSTE_TEMPLATES = ['document-library', 'templates', 'fiche_poste'] as const;

export function documentStatusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    brouillon: { className: 'bg-amber-100 text-amber-900 border-amber-200', label: 'Brouillon' },
    envoye: { className: 'bg-blue-100 text-blue-900 border-blue-200', label: 'Envoyé' },
    signe: { className: 'bg-emerald-100 text-emerald-900 border-emerald-200', label: 'Signé' },
    archive: { className: 'bg-slate-100 text-slate-700 border-slate-200', label: 'Archivé' },
  };
  const m = map[status] ?? { className: 'bg-muted text-muted-foreground', label: status };
  return (
    <Badge variant="outline" className={cn('font-medium', m.className)}>
      {m.label}
    </Badge>
  );
}

export function formatGeneratedDocDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export interface EmployeeDetailDocumentsRhEmployee {
  id: string;
  first_name: string;
  last_name: string;
  job_title?: string | null;
  contract_type?: string | null;
  hire_date?: string | null;
  statut?: string | null;
  salaire_de_base?: unknown;
  duree_hebdomadaire?: unknown;
  lieu_travail?: unknown;
  workplace?: unknown;
  poste?: string | null;
  weekly_hours?: unknown;
  is_subject_to_residence_permit?: boolean | null;
  residence_permit_type?: string | null;
  residence_permit_number?: string | null;
  residence_permit_expiry_date?: string | null;
  employment_status?: string | null;
  exit_last_working_day?: string | null;
}

type GenMode = DocumentGenMode;

export interface EmployeeDocumentGenerationHandlers {
  openContrat: () => void;
  openAvenant: (preset?: { document_type: string; template_id: string | null }) => void;
  openAttestation: () => void;
  openFichePoste: (options?: { jobId?: string; missions?: string }) => void;
  hasFichePosteTemplate: boolean;
  handleView: (id: string) => Promise<void>;
  handleDownload: (id: string, fileName?: string | null) => Promise<void>;
  handleDelete: (id: string) => void;
  handleSend: (id: string) => void;
  deletingId: string | null;
  sendingId: string | null;
  loadingAction: { id: string; kind: 'view' | 'download' } | null;
}

export function useEmployeeDocumentGeneration(
  employeeId: string,
  employee: EmployeeDetailDocumentsRhEmployee,
  deepLink?: { generate?: 'fiche_poste'; jobId?: string }
) {
  const queryClient = useQueryClient();
  const displayName = `${employee.last_name} ${employee.first_name}`.trim();

  const [genMode, setGenMode] = useState<GenMode>(null);
  const [genDocType, setGenDocType] = useState('');
  const [genTemplate, setGenTemplate] = useState('__eywai__');
  const [genDateEffet, setGenDateEffet] = useState('');
  const [genMotif, setGenMotif] = useState('');
  const [genMissions, setGenMissions] = useState('');
  const [genManager, setGenManager] = useState('');
  const [genRecruitmentJobId, setGenRecruitmentJobId] = useState<string | undefined>();
  const [eywaiBanner, setEywaiBanner] = useState(false);
  const [loadingAction, setLoadingAction] = useState<{
    id: string;
    kind: 'view' | 'download';
  } | null>(null);

  const { data: rows = [], isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: QK_EMPLOYEE_GENERATED_DOCS(employeeId),
    queryFn: () => getDocuments({ employee_id: employeeId }),
  });

  const { data: fichePosteTemplates = [] } = useQuery({
    queryKey: [...QK_FICHE_POSTE_TEMPLATES],
    queryFn: () => getTemplates('active'),
  });

  const hasFichePosteTemplate = useMemo(
    () =>
      fichePosteTemplates.some(
        (t) =>
          t.document_type === 'fiche_poste' &&
          t.status === 'active' &&
          t.current_version != null
      ),
    [fichePosteTemplates]
  );

  const fichePosteTemplatesForType = useMemo(
    () => fichePosteTemplates.filter((t) => t.document_type === 'fiche_poste' && t.status === 'active'),
    [fichePosteTemplates]
  );

  const docTypeForTemplates = genDocType || '';
  const { data: templates = [] } = useQuery({
    queryKey: ['document-library', 'templates', 'active', docTypeForTemplates, genMode],
    queryFn: () => getTemplates('active'),
    enabled: !!genMode && !!docTypeForTemplates,
  });

  const templatesForType = useMemo(
    () =>
      templates.filter(
        (t: DocumentTemplate) => t.document_type === docTypeForTemplates && t.status === 'active'
      ),
    [templates, docTypeForTemplates]
  );

  const invalidateDocs = () => {
    queryClient.invalidateQueries({ queryKey: QK_EMPLOYEE_GENERATED_DOCS(employeeId) });
  };

  const sendMut = useMutation({
    mutationFn: (id: string) => updateDocumentStatus(id, 'envoye'),
    onSuccess: () => {
      invalidateDocs();
      toast({
        title: 'Document envoyé',
        description: 'Le collaborateur a été notifié.',
      });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Envoi impossible',
        description: typeof msg === 'string' ? msg : 'Erreur serveur.',
        variant: 'destructive',
      });
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      invalidateDocs();
      toast({ title: 'Document supprimé' });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Suppression impossible',
        description: typeof msg === 'string' ? msg : 'Erreur serveur.',
        variant: 'destructive',
      });
    },
  });

  const genMut = useMutation({
    mutationFn: generateDocument,
    onSuccess: (doc) => {
      invalidateDocs();
      setEywaiBanner(doc.is_eywai_template);
      setGenMode(null);
      setGenDocType('');
      setGenTemplate('__eywai__');
      setGenDateEffet('');
      setGenMotif('');
      setGenMissions('');
      setGenManager('');
      setGenRecruitmentJobId(undefined);
      toast({
        title: 'Document généré',
        description: doc.file_name ? `Fichier : ${doc.file_name}` : 'Enregistré.',
      });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Échec',
        description: typeof msg === 'string' ? msg : 'Génération impossible.',
        variant: 'destructive',
      });
    },
  });

  const openContrat = () => {
    setGenMode('contrat');
    setGenDocType(resolveGeneratedContractDocType(employee.contract_type));
    setGenTemplate('__eywai__');
    setGenDateEffet(employee.hire_date ?? '');
    setGenMotif('');
    setEywaiBanner(false);
  };

  const openAttestation = () => {
    setGenMode('attestation');
    setGenDocType('');
    setGenTemplate('__eywai__');
    setEywaiBanner(false);
  };

  const openAvenant = (preset?: { document_type: string; template_id: string | null }) => {
    setGenMode('avenant');
    setGenDocType(preset?.document_type ?? '');
    setGenTemplate(preset?.template_id ?? '__eywai__');
    setGenDateEffet('');
    setGenMotif('');
    setEywaiBanner(false);
  };

  const openFichePoste = (options?: { jobId?: string; missions?: string }) => {
    setGenMode('fiche_poste');
    setGenDocType('fiche_poste');
    const firstTpl = fichePosteTemplatesForType[0];
    setGenTemplate(firstTpl?.id ?? '');
    setGenMissions(options?.missions ?? '');
    setGenManager('');
    setGenRecruitmentJobId(options?.jobId);
    setEywaiBanner(false);
  };

  useEffect(() => {
    if (deepLink?.generate === 'fiche_poste' && hasFichePosteTemplate) {
      openFichePoste({ jobId: deepLink.jobId });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ouverture unique au chargement
  }, [deepLink?.generate, deepLink?.jobId, hasFichePosteTemplate]);

  const submitFichePoste = () => {
    if (!genTemplate) {
      toast({
        title: 'Modèle requis',
        description: 'Configurez une fiche de poste dans la bibliothèque.',
        variant: 'destructive',
      });
      return;
    }
    const custom_fields: Record<string, string> = {};
    if (genMissions.trim()) custom_fields.missions = genMissions.trim();
    if (genManager.trim()) custom_fields.manager = genManager.trim();
    genMut.mutate({
      employee_id: employeeId,
      document_type: 'fiche_poste',
      category: 'attestation_courante',
      template_id: genTemplate,
      custom_fields: Object.keys(custom_fields).length ? custom_fields : null,
      recruitment_job_id: genRecruitmentJobId ?? null,
    });
  };

  const submitGen = () => {
    if (!genDocType || !genDateEffet) {
      toast({ title: 'Champs requis', variant: 'destructive' });
      return;
    }
    const category: DocumentCategory = genMode === 'contrat' ? 'contrat' : 'avenant';
    genMut.mutate({
      employee_id: employeeId,
      document_type: genDocType,
      category,
      date_effet: genDateEffet,
      motif: genMotif.trim() || null,
      template_id: genTemplate === '__eywai__' ? null : genTemplate,
    });
  };

  const submitAttestation = () => {
    if (!genDocType) {
      toast({ title: 'Type d’attestation requis', variant: 'destructive' });
      return;
    }
    genMut.mutate({
      employee_id: employeeId,
      document_type: genDocType,
      category: 'attestation_courante',
      template_id: genTemplate === '__eywai__' ? null : genTemplate,
    });
  };

  const handleView = async (id: string) => {
    setLoadingAction({ id, kind: 'view' });
    try {
      await openDocumentPreview(id);
    } catch {
      toast({
        title: 'Aperçu indisponible',
        description: 'Impossible d’ouvrir le document.',
        variant: 'destructive',
      });
    } finally {
      setLoadingAction(null);
    }
  };

  const handleDownload = async (id: string, fileName?: string | null) => {
    setLoadingAction({ id, kind: 'download' });
    try {
      const res = await downloadDocument(id);
      triggerSignedDocumentDownload(res, fileName || 'document.pdf');
    } catch {
      toast({ title: 'Téléchargement', description: 'Lien indisponible.', variant: 'destructive' });
    } finally {
      setLoadingAction(null);
    }
  };

  const handleDelete = (id: string) => {
    if (!window.confirm('Supprimer ce document ? Cette action est irréversible.')) return;
    deleteMut.mutate(id);
  };

  const handleSend = (id: string) => {
    sendMut.mutate(id);
  };

  const canSubmitContrat = genMode === 'contrat' && !!genDocType && !!genDateEffet;
  const canSubmitAvenant = genMode === 'avenant' && !!genDocType && !!genDateEffet;
  const canSubmitAttestation = genMode === 'attestation' && !!genDocType;
  const canSubmitFichePoste = genMode === 'fiche_poste' && !!genTemplate;

  const handlers: EmployeeDocumentGenerationHandlers = {
    openContrat,
    openAvenant,
    openAttestation,
    openFichePoste,
    hasFichePosteTemplate,
    handleView,
    handleDownload,
    handleDelete,
    handleSend,
    deletingId: deleteMut.isPending ? (deleteMut.variables as string) : null,
    sendingId: sendMut.isPending ? (sendMut.variables as string) : null,
    loadingAction,
  };

  const dialogs = (
    <>
      <Dialog open={genMode === 'contrat'} onOpenChange={(o) => !o && setGenMode(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Générer un contrat</DialogTitle>
            <DialogDescription>{displayName}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label>Type de contrat</Label>
              <Select value={genDocType || undefined} onValueChange={setGenDocType}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {CONTRACT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {DOCUMENT_TYPE_LABELS[t] ?? t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Modèle</Label>
              <Select value={genTemplate} onValueChange={setGenTemplate}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__eywai__">Standard EYWAI</SelectItem>
                  {templatesForType.map((tpl) => (
                    <SelectItem key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Date d&apos;effet</Label>
              <Input type="date" value={genDateEffet} onChange={(e) => setGenDateEffet(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenMode(null)}>
              Annuler
            </Button>
            <Button onClick={submitGen} disabled={!canSubmitContrat || genMut.isPending}>
              {genMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={genMode === 'avenant'} onOpenChange={(o) => !o && setGenMode(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Générer un avenant</DialogTitle>
            <DialogDescription>{displayName}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label>Type d&apos;avenant</Label>
              <Select value={genDocType || undefined} onValueChange={setGenDocType}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {AVENANT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {DOCUMENT_TYPE_LABELS[t] ?? t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Modèle</Label>
              <Select value={genTemplate} onValueChange={setGenTemplate}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__eywai__">Standard EYWAI</SelectItem>
                  {templatesForType.map((tpl) => (
                    <SelectItem key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Date d&apos;effet</Label>
              <Input type="date" value={genDateEffet} onChange={(e) => setGenDateEffet(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Motif (optionnel)</Label>
              <Input value={genMotif} onChange={(e) => setGenMotif(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenMode(null)}>
              Annuler
            </Button>
            <Button onClick={submitGen} disabled={!canSubmitAvenant || genMut.isPending}>
              {genMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={genMode === 'attestation'} onOpenChange={(o) => !o && setGenMode(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {employee.last_name} {employee.first_name}
            </DialogTitle>
            <DialogDescription>Générer une attestation courante</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label>Type d&apos;attestation</Label>
              <Select value={genDocType || undefined} onValueChange={setGenDocType}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                  {ATTESTATION_COURANTE_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {DOCUMENT_TYPE_LABELS[t] ?? t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Modèle</Label>
              <Select value={genTemplate} onValueChange={setGenTemplate}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__eywai__">Standard EYWAI</SelectItem>
                  {templatesForType.map((tpl) => (
                    <SelectItem key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenMode(null)}>
              Annuler
            </Button>
            <Button onClick={submitAttestation} disabled={!canSubmitAttestation || genMut.isPending}>
              {genMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={genMode === 'fiche_poste'} onOpenChange={(o) => !o && setGenMode(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Générer une fiche de poste</DialogTitle>
            <DialogDescription>{displayName}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label>Modèle</Label>
              <Select value={genTemplate || undefined} onValueChange={setGenTemplate}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir un modèle…" />
                </SelectTrigger>
                <SelectContent>
                  {fichePosteTemplatesForType.map((tpl) => (
                    <SelectItem key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground space-y-1">
              <p>
                <span className="font-medium text-foreground">Poste :</span>{' '}
                {employee.job_title || employee.poste || '— non renseigné'}
              </p>
              <p>
                <span className="font-medium text-foreground">Nom :</span> {employee.first_name}{' '}
                {employee.last_name}
              </p>
            </div>
            <div className="space-y-2">
              <Label>Missions (optionnel)</Label>
              <Textarea
                value={genMissions}
                onChange={(e) => setGenMissions(e.target.value)}
                rows={3}
                placeholder="Description des missions…"
              />
            </div>
            <div className="space-y-2">
              <Label>Manager (optionnel)</Label>
              <Input value={genManager} onChange={(e) => setGenManager(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenMode(null)}>
              Annuler
            </Button>
            <Button onClick={submitFichePoste} disabled={!canSubmitFichePoste || genMut.isPending}>
              {genMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );

  return {
    rows,
    isLoading,
    isError,
    isFetching,
    refetch,
    eywaiBanner,
    handlers,
    dialogs,
    genMut,
  };
}

export function EmployeeDocumentAddMenu({
  handlers,
  onManageTemplates,
  onImportContract,
  onTransmitDocument,
  menuAlign = 'start',
}: {
  handlers: EmployeeDocumentGenerationHandlers;
  onManageTemplates: () => void;
  onImportContract?: () => void;
  onTransmitDocument?: () => void;
  menuAlign?: 'start' | 'end';
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" size="sm" className="shrink-0">
          <Plus className="mr-2 h-4 w-4" />
          Ajouter un document
          <ChevronDown className="ml-2 h-4 w-4 opacity-70" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={menuAlign} className="w-56">
        {onTransmitDocument ? (
          <>
            <DropdownMenuItem onClick={onTransmitDocument}>
              <Send className="mr-2 h-4 w-4" />
              Transmettre un document
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        ) : null}
        {onImportContract ? (
          <DropdownMenuItem onClick={onImportContract}>
            <Upload className="mr-2 h-4 w-4" />
            Importer un contrat PDF
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem onClick={handlers.openContrat}>Générer un contrat</DropdownMenuItem>
        <DropdownMenuItem onClick={() => handlers.openAvenant()}>Générer un avenant</DropdownMenuItem>
        <DropdownMenuItem onClick={handlers.openAttestation}>Générer une attestation</DropdownMenuItem>
        <DropdownMenuItem
          disabled={!handlers.hasFichePosteTemplate}
          onClick={() => handlers.openFichePoste()}
        >
          Générer une fiche de poste
        </DropdownMenuItem>
        {!handlers.hasFichePosteTemplate ? (
          <p className="px-2 pb-1 text-xs text-muted-foreground">
            Importez un modèle dans la bibliothèque.
          </p>
        ) : null}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={onManageTemplates}>
          <Settings2 className="mr-2 h-4 w-4" />
          Gérer la bibliothèque
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** @deprecated Utiliser EmployeeDetailDocumentsTab — conservé pour compatibilité imports */
export function EmployeeDetailDocumentsRhSection({
  employeeId,
  employee,
}: {
  employeeId: string;
  employee: EmployeeDetailDocumentsRhEmployee;
}) {
  const navigate = useNavigate();
  const { handlers, dialogs, eywaiBanner } = useEmployeeDocumentGeneration(employeeId, employee);

  return (
    <div className="space-y-4">
      <EmployeeDocumentAddMenu handlers={handlers} onManageTemplates={() => navigate('/company?tab=modeles')} />
      {eywaiBanner && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Générée avec le modèle standard EYWAI.
        </div>
      )}
      {dialogs}
    </div>
  );
}

export function GeneratedDocActions({
  doc,
  handlers,
}: {
  doc: GeneratedDocument;
  handlers: EmployeeDocumentGenerationHandlers;
}) {
  const hasFile = Boolean(doc.file_url);
  const canDelete = doc.status === 'brouillon';
  const canSend = doc.status === 'brouillon';
  const viewLoading =
    handlers.loadingAction?.id === doc.id && handlers.loadingAction.kind === 'view';
  const downloadLoading =
    handlers.loadingAction?.id === doc.id && handlers.loadingAction.kind === 'download';
  const isDeleting = handlers.deletingId === doc.id;
  const isSending = handlers.sendingId === doc.id;

  return (
    <div className="flex items-center gap-0.5">
      {canSend ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-primary hover:text-primary"
          disabled={!hasFile || viewLoading || downloadLoading || isDeleting || isSending}
          title="Envoyer au collaborateur"
          onClick={() => handlers.handleSend(doc.id)}
        >
          {isSending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          <span className="sr-only">Envoyer au collaborateur</span>
        </Button>
      ) : null}
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        disabled={!hasFile || viewLoading || downloadLoading || isDeleting || isSending}
        title="Visualiser le document"
        onClick={() => void handlers.handleView(doc.id)}
      >
        {viewLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Eye className="h-4 w-4" />
        )}
        <span className="sr-only">Visualiser</span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        disabled={!hasFile || viewLoading || downloadLoading || isDeleting || isSending}
        title="Télécharger"
        onClick={() => void handlers.handleDownload(doc.id, doc.file_name)}
      >
        {downloadLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <ArrowDownToLine className="h-4 w-4" />
        )}
        <span className="sr-only">Télécharger</span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-destructive hover:text-destructive"
        disabled={!canDelete || viewLoading || downloadLoading || isDeleting || isSending}
        title={
          canDelete
            ? 'Supprimer'
            : 'Suppression réservée aux documents au statut brouillon'
        }
        onClick={() => handlers.handleDelete(doc.id)}
      >
        {isDeleting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Trash2 className="h-4 w-4" />
        )}
        <span className="sr-only">Supprimer</span>
      </Button>
    </div>
  );
}

export function GeneratedDocMeta({ doc }: { doc: GeneratedDocument }): ReactNode {
  const isTransmitted = doc.document_type === 'document_transmis';
  const sourceLabel = isTransmitted
    ? 'Transmis par les RH'
    : doc.is_eywai_template
      ? 'Standard EYWAI'
      : doc.template_name || 'Modèle personnalisé';

  return (
    <>
      {documentStatusBadge(doc.status)}
      <span className="text-xs text-muted-foreground">
        {formatGeneratedDocDate(doc.created_at)}
        {' · '}
        {sourceLabel}
      </span>
    </>
  );
}

