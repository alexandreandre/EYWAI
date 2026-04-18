import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';
import apiClient from '@/api/apiClient';
import {
  deleteDocument,
  downloadDocument,
  triggerSignedDocumentDownload,
  generateDocument,
  getDocuments,
  updateDocumentStatus,
  type DocumentCategory,
  type DocumentStatus,
  type GeneratedDocument,
} from '@/api/documents';
import { DOCUMENT_TYPE_LABELS, getTemplates, type DocumentTemplate } from '@/api/documentLibrary';
import { FileText, Loader2, Plus, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const QK = ['rh-documents'] as const;

const CATEGORY_OPTIONS: { value: DocumentCategory; label: string }[] = [
  { value: 'contrat', label: 'Contrat' },
  { value: 'avenant', label: 'Avenant' },
  { value: 'attestation_sortie', label: 'Attestation (sortie)' },
  { value: 'attestation_situation', label: 'Attestation (situation)' },
  { value: 'attestation_courante', label: 'Attestation (courante)' },
];

const CONTRACT_TYPES = new Set(['cdi', 'cdd', 'convention_stage', 'contrat_alternance']);

const ATTESTATION_COURANTE_TYPES = new Set([
  'attestation_emploi',
  'attestation_presence',
  'attestation_anciennete',
  'attestation_poste',
  'attestation_salaire',
  'attestation_revenus',
  'attestation_location',
  'attestation_pret',
  'attestation_retraite',
]);

function needsDateEffet(documentType: string): boolean {
  return CONTRACT_TYPES.has(documentType) || documentType.includes('avenant');
}

function statusBadge(status: string) {
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

function formatDate(iso: string): string {
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

interface SimpleEmployee {
  id: string;
  first_name: string;
  last_name: string;
}

const DOC_GROUPS: { label: string; types: string[] }[] = [
  {
    label: 'Contrats',
    types: ['cdi', 'cdd', 'convention_stage', 'contrat_alternance'],
  },
  {
    label: 'Avenants',
    types: [
      'avenant_salaire',
      'avenant_poste',
      'avenant_temps',
      'avenant_lieu',
      'avenant_general',
    ],
  },
  {
    label: 'Attestations courantes',
    types: [
      'attestation_emploi',
      'attestation_presence',
      'attestation_anciennete',
      'attestation_poste',
      'attestation_salaire',
      'attestation_revenus',
      'attestation_location',
      'attestation_pret',
      'attestation_retraite',
    ],
  },
];

export default function DocumentsRhPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [employeeId, setEmployeeId] = useState<string>('');
  const [documentType, setDocumentType] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  const [genOpen, setGenOpen] = useState(false);
  const [genEmployee, setGenEmployee] = useState('');
  const [genDocType, setGenDocType] = useState('');
  const [genCategory, setGenCategory] = useState<DocumentCategory>('attestation_courante');
  const [genTemplate, setGenTemplate] = useState<string>('__eywai__');
  const [genDateEffet, setGenDateEffet] = useState('');
  const [genMotif, setGenMotif] = useState('');
  const [eywaiBanner, setEywaiBanner] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<GeneratedDocument | null>(null);

  useEffect(() => {
    if (!genDocType) return;
    if (ATTESTATION_COURANTE_TYPES.has(genDocType)) {
      setGenCategory('attestation_courante');
    } else if (CONTRACT_TYPES.has(genDocType)) {
      setGenCategory('contrat');
    } else if (genDocType.startsWith('avenant_')) {
      setGenCategory('avenant');
    }
  }, [genDocType]);

  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (employeeId) f.employee_id = employeeId;
    if (documentType) f.document_type = documentType;
    if (statusFilter) f.status = statusFilter;
    if (dateFrom) f.date_from = `${dateFrom}T00:00:00`;
    if (dateTo) f.date_to = `${dateTo}T23:59:59`;
    return f;
  }, [employeeId, documentType, statusFilter, dateFrom, dateTo]);

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'documents-rh'],
    queryFn: async () => {
      const r = await apiClient.get<SimpleEmployee[]>('/api/employees', { params: { limit: 500 } });
      return r.data;
    },
  });

  const { data: templates = [] } = useQuery({
    queryKey: ['document-library', 'templates', 'active', genDocType],
    queryFn: () => getTemplates('active'),
    enabled: genOpen && !!genDocType,
  });

  const templatesForType = useMemo(
    () => templates.filter((t: DocumentTemplate) => t.document_type === genDocType && t.status === 'active'),
    [templates, genDocType]
  );

  const {
    data: rows = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [...QK, filters],
    queryFn: () => getDocuments(filters),
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [...QK] });
  }, [queryClient]);

  const genMut = useMutation({
    mutationFn: generateDocument,
    onSuccess: (doc) => {
      invalidate();
      setEywaiBanner(doc.is_eywai_template);
      setGenOpen(false);
      toast({
        title: 'Document généré',
        description: doc.file_name ? `Fichier : ${doc.file_name}` : 'Document enregistré.',
      });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Échec de la génération',
        description: typeof msg === 'string' ? msg : 'Une erreur est survenue.',
        variant: 'destructive',
      });
    },
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: DocumentStatus }) =>
      updateDocumentStatus(id, status),
    onSuccess: () => {
      invalidate();
      toast({ title: 'Statut mis à jour' });
    },
    onError: () => {
      toast({ title: 'Erreur', description: 'Mise à jour du statut impossible.', variant: 'destructive' });
    },
  });

  const delMut = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      invalidate();
      setDeleteTarget(null);
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

  const resetFilters = () => {
    setEmployeeId('');
    setDocumentType('');
    setStatusFilter('');
    setDateFrom('');
    setDateTo('');
  };

  const openGenerate = () => {
    setGenEmployee('');
    setGenDocType('');
    setGenCategory('attestation_courante');
    setGenTemplate('__eywai__');
    setGenDateEffet('');
    setGenMotif('');
    setEywaiBanner(false);
    setGenOpen(true);
  };

  const submitGenerate = () => {
    if (!genEmployee || !genDocType) {
      toast({ title: 'Champs requis', description: 'Collaborateur et type de document.', variant: 'destructive' });
      return;
    }
    if (needsDateEffet(genDocType) && !genDateEffet) {
      toast({ title: 'Date d’effet requise', variant: 'destructive' });
      return;
    }
    genMut.mutate({
      employee_id: genEmployee,
      document_type: genDocType,
      category: genCategory,
      ...(genDateEffet ? { date_effet: genDateEffet } : {}),
      ...(genMotif.trim() ? { motif: genMotif.trim() } : {}),
      template_id: genTemplate === '__eywai__' ? null : genTemplate,
    });
  };

  const handleDownload = async (id: string, fileName?: string | null) => {
    try {
      const res = await downloadDocument(id);
      triggerSignedDocumentDownload(res, fileName || 'document.pdf');
    } catch {
      toast({ title: 'Téléchargement', description: 'Impossible d’obtenir le lien.', variant: 'destructive' });
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
          <p className="text-sm text-muted-foreground">
            Liste des documents générés et création manuelle (PDF).
          </p>
        </div>
        <Button onClick={openGenerate}>
          <Plus className="mr-2 h-4 w-4" />
          Générer un document
        </Button>
      </div>

      {eywaiBanner && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          Dernier document généré avec le <strong>modèle standard EYWAI</strong>.
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filtres</CardTitle>
          <CardDescription>Affinez la liste des documents générés.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end">
          <div className="grid flex-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <div className="space-y-2">
              <Label>Collaborateur</Label>
              <Select value={employeeId || '__all__'} onValueChange={(v) => setEmployeeId(v === '__all__' ? '' : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Tous" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Tous</SelectItem>
                  {employees.map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.first_name} {e.last_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Type de document</Label>
              <Select value={documentType || '__all__'} onValueChange={(v) => setDocumentType(v === '__all__' ? '' : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Tous" />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                  <SelectItem value="__all__">Tous</SelectItem>
                  {Object.entries(DOCUMENT_TYPE_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>
                      {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Statut</Label>
              <Select value={statusFilter || '__all__'} onValueChange={(v) => setStatusFilter(v === '__all__' ? '' : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Tous" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Tous</SelectItem>
                  <SelectItem value="brouillon">Brouillon</SelectItem>
                  <SelectItem value="envoye">Envoyé</SelectItem>
                  <SelectItem value="signe">Signé</SelectItem>
                  <SelectItem value="archive">Archivé</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Du</Label>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Au</Label>
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
          </div>
          <Button type="button" variant="outline" onClick={resetFilters}>
            Réinitialiser
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4" />
            Documents générés
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          )}
          {isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">
              <p className="font-medium text-destructive">Erreur de chargement</p>
              <p className="text-muted-foreground">{(error as Error)?.message}</p>
              <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
                Réessayer
              </Button>
            </div>
          )}
          {!isLoading && !isError && rows.length === 0 && (
            <p className="py-12 text-center text-sm text-muted-foreground">Aucun document pour ces critères.</p>
          )}
          {!isLoading && !isError && rows.length > 0 && (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Collaborateur</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Catégorie</TableHead>
                    <TableHead>Date génération</TableHead>
                    <TableHead>Modèle utilisé</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((d) => (
                    <TableRow key={d.id}>
                      <TableCell className="font-medium">{d.employee_name || '—'}</TableCell>
                      <TableCell>{DOCUMENT_TYPE_LABELS[d.document_type] ?? d.document_type}</TableCell>
                      <TableCell className="text-muted-foreground">{d.category}</TableCell>
                      <TableCell className="whitespace-nowrap text-sm">{formatDate(d.created_at)}</TableCell>
                      <TableCell>
                        {d.is_eywai_template ? (
                          <span className="text-sm">Standard EYWAI</span>
                        ) : (
                          <span className="text-sm">{d.template_name || '—'}</span>
                        )}
                      </TableCell>
                      <TableCell>{statusBadge(d.status)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex flex-wrap items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!d.file_url}
                            onClick={() => handleDownload(d.id, d.file_name)}
                          >
                            PDF
                          </Button>
                          <Select
                            value={d.status}
                            onValueChange={(v) =>
                              statusMut.mutate({ id: d.id, status: v as DocumentStatus })
                            }
                          >
                            <SelectTrigger className="h-8 w-[130px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="brouillon">Brouillon</SelectItem>
                              <SelectItem value="envoye">Envoyé</SelectItem>
                              <SelectItem value="signe">Signé</SelectItem>
                              <SelectItem value="archive">Archivé</SelectItem>
                            </SelectContent>
                          </Select>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive"
                            disabled={d.status !== 'brouillon'}
                            title={d.status !== 'brouillon' ? 'Suppression réservée au brouillon' : 'Supprimer'}
                            onClick={() => setDeleteTarget(d)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Générer un document</DialogTitle>
            <DialogDescription>Le PDF est stocké dans l’espace entreprise (statut brouillon).</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Collaborateur</Label>
              <Select value={genEmployee || undefined} onValueChange={setGenEmployee}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {employees.map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.first_name} {e.last_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Type de document</Label>
              <Select value={genDocType || undefined} onValueChange={setGenDocType}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                  {DOC_GROUPS.map((g) => (
                    <SelectGroup key={g.label}>
                      <SelectLabel>{g.label}</SelectLabel>
                      {g.types.map((t) => (
                        <SelectItem key={t} value={t}>
                          {DOCUMENT_TYPE_LABELS[t] ?? t}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Catégorie</Label>
              <Select value={genCategory} onValueChange={(v) => setGenCategory(v as DocumentCategory)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
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
                      {tpl.name} (v{tpl.current_version?.version ?? '?'})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {needsDateEffet(genDocType) && (
              <div className="space-y-2">
                <Label>Date d’effet</Label>
                <Input type="date" value={genDateEffet} onChange={(e) => setGenDateEffet(e.target.value)} required />
              </div>
            )}
            <div className="space-y-2">
              <Label>Motif (optionnel)</Label>
              <Input value={genMotif} onChange={(e) => setGenMotif(e.target.value)} placeholder="Ex. évolution salariale" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenOpen(false)}>
              Annuler
            </Button>
            <Button onClick={submitGenerate} disabled={genMut.isPending}>
              {genMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce document ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. Réservée aux documents au statut brouillon.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteTarget && delMut.mutate(deleteTarget.id)}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
