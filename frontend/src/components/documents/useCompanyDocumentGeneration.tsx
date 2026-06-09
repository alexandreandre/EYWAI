import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import apiClient from '@/api/apiClient';
import {
  deleteDocument,
  downloadDocument,
  openDocumentPreview,
  triggerSignedDocumentDownload,
  generateDocument,
  updateDocumentStatus,
  type DocumentCategory,
} from '@/api/documents';
import { DOCUMENT_TYPE_LABELS, getTemplates, type DocumentTemplate } from '@/api/documentLibrary';
import { rhCanViewEmployeeDocuments } from '@/lib/employeeExitDocumentsAccess';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from '@/components/ui/use-toast';
import {
  QK_COMPANY_DOCUMENTS_EXPLORER,
} from '@/components/documents/CompanyDocumentsExplorer';
import type { EmployeeDocumentGenerationHandlers } from '@/components/employee-detail/EmployeeDetailDocumentsRhSection';
import { Loader2 } from 'lucide-react';

const CONTRACT_TYPES = ['cdi', 'cdd', 'convention_stage', 'contrat_alternance'] as const;
const AVENANT_TYPES = [
  'avenant_salaire',
  'avenant_poste',
  'avenant_temps',
  'avenant_lieu',
  'avenant_general',
] as const;
const ATTESTATION_COURANTE_TYPES = [
  'attestation_emploi',
  'attestation_presence',
  'attestation_anciennete',
  'attestation_poste',
  'attestation_salaire',
  'attestation_revenus',
  'attestation_location',
  'attestation_pret',
  'attestation_retraite',
] as const;

interface SimpleEmployee {
  id: string;
  first_name: string;
  last_name: string;
  employment_status?: string | null;
  exit_last_working_day?: string | null;
}

type GenMode = 'contrat' | 'avenant' | 'attestation' | null;

export function useCompanyDocumentGeneration() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [genMode, setGenMode] = useState<GenMode>(null);
  const [genEmployeeId, setGenEmployeeId] = useState('');
  const [genDocType, setGenDocType] = useState('');
  const [genTemplate, setGenTemplate] = useState('__eywai__');
  const [genDateEffet, setGenDateEffet] = useState('');
  const [genMotif, setGenMotif] = useState('');
  const [eywaiBanner, setEywaiBanner] = useState(false);
  const [loadingAction, setLoadingAction] = useState<{
    id: string;
    kind: 'view' | 'download';
  } | null>(null);

  const { data: employeesRaw = [] } = useQuery({
    queryKey: ['employees', 'company-documents-gen'],
    queryFn: async () => {
      const r = await apiClient.get<SimpleEmployee[]>('/api/employees', { params: { limit: 500 } });
      return r.data ?? [];
    },
  });

  const employees = useMemo(
    () =>
      employeesRaw.filter((employee) => {
        const status = (employee.employment_status || 'actif').toLowerCase();
        if (status === 'parti') return false;
        return rhCanViewEmployeeDocuments(employee);
      }),
    [employeesRaw],
  );

  const selectedEmployee = useMemo(
    () => employees.find((e) => e.id === genEmployeeId),
    [employees, genEmployeeId]
  );

  const displayName = selectedEmployee
    ? `${selectedEmployee.last_name} ${selectedEmployee.first_name}`.trim()
    : '';

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

  const invalidateExplorer = () => {
    void queryClient.invalidateQueries({ queryKey: QK_COMPANY_DOCUMENTS_EXPLORER });
    void queryClient.invalidateQueries({ queryKey: ['rh-documents'] });
  };

  const sendMut = useMutation({
    mutationFn: (id: string) => updateDocumentStatus(id, 'envoye'),
    onSuccess: () => {
      invalidateExplorer();
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
      invalidateExplorer();
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
      invalidateExplorer();
      setEywaiBanner(doc.is_eywai_template);
      setGenMode(null);
      setGenDocType('');
      setGenTemplate('__eywai__');
      setGenDateEffet('');
      setGenMotif('');
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

  const openGen = (mode: GenMode) => {
    setGenMode(mode);
    setGenDocType('');
    setGenTemplate('__eywai__');
    setGenDateEffet('');
    setGenMotif('');
    setEywaiBanner(false);
  };

  const submitGen = () => {
    if (!genEmployeeId || !genDocType || !genDateEffet) {
      toast({ title: 'Champs requis', variant: 'destructive' });
      return;
    }
    const category: DocumentCategory = genMode === 'contrat' ? 'contrat' : 'avenant';
    genMut.mutate({
      employee_id: genEmployeeId,
      document_type: genDocType,
      category,
      date_effet: genDateEffet,
      motif: genMotif.trim() || null,
      template_id: genTemplate === '__eywai__' ? null : genTemplate,
    });
  };

  const submitAttestation = () => {
    if (!genEmployeeId || !genDocType) {
      toast({ title: 'Champs requis', variant: 'destructive' });
      return;
    }
    genMut.mutate({
      employee_id: genEmployeeId,
      document_type: genDocType,
      category: 'attestation_courante',
      template_id: genTemplate === '__eywai__' ? null : genTemplate,
    });
  };

  const handlers: EmployeeDocumentGenerationHandlers = {
    openContrat: () => openGen('contrat'),
    openAvenant: () => openGen('avenant'),
    openAttestation: () => openGen('attestation'),
    handleView: async (id: string) => {
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
    },
    handleDownload: async (id: string, fileName?: string | null) => {
      setLoadingAction({ id, kind: 'download' });
      try {
        const res = await downloadDocument(id);
        triggerSignedDocumentDownload(res, fileName || 'document.pdf');
      } catch {
        toast({ title: 'Téléchargement', description: 'Lien indisponible.', variant: 'destructive' });
      } finally {
        setLoadingAction(null);
      }
    },
    handleDelete: (id: string) => {
      if (!window.confirm('Supprimer ce document ? Cette action est irréversible.')) return;
      deleteMut.mutate(id);
    },
    handleSend: (id: string) => {
      sendMut.mutate(id);
    },
    deletingId: deleteMut.isPending ? (deleteMut.variables as string) : null,
    sendingId: sendMut.isPending ? (sendMut.variables as string) : null,
    loadingAction,
  };

  const employeeSelect = (
    <div className="space-y-2">
      <Label>Collaborateur</Label>
      <Select value={genEmployeeId || undefined} onValueChange={setGenEmployeeId}>
        <SelectTrigger>
          <SelectValue placeholder="Choisir un collaborateur…" />
        </SelectTrigger>
        <SelectContent className="max-h-72">
          {employees.map((e) => (
            <SelectItem key={e.id} value={e.id}>
              {e.first_name} {e.last_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const dialogs = (
    <>
      <Dialog open={genMode === 'contrat'} onOpenChange={(o) => !o && setGenMode(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Générer un contrat</DialogTitle>
            <DialogDescription>
              {displayName || 'Sélectionnez un collaborateur ci-dessous.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {employeeSelect}
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
            <Button
              onClick={submitGen}
              disabled={!genEmployeeId || !genDocType || !genDateEffet || genMut.isPending}
            >
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
            <DialogDescription>
              {displayName || 'Sélectionnez un collaborateur ci-dessous.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {employeeSelect}
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
            <Button
              onClick={submitGen}
              disabled={!genEmployeeId || !genDocType || !genDateEffet || genMut.isPending}
            >
              {genMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={genMode === 'attestation'} onOpenChange={(o) => !o && setGenMode(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Générer une attestation</DialogTitle>
            <DialogDescription>
              {displayName || 'Sélectionnez un collaborateur ci-dessous.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {employeeSelect}
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
            <Button
              onClick={submitAttestation}
              disabled={!genEmployeeId || !genDocType || genMut.isPending}
            >
              {genMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );

  return {
    handlers,
    dialogs,
    eywaiBanner,
    onManageTemplates: () => navigate('/company#bibliotheque'),
  };
}
