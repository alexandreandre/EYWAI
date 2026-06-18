import { useCallback, useMemo, useState } from 'react';
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
import { Checkbox } from '@/components/ui/checkbox';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
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
import { useAuth } from '@/contexts/AuthContext';
import {
  DOCUMENT_TYPE_LABELS,
  archiveTemplate,
  createTemplate,
  downloadFichePosteExample,
  getDocumentVariables,
  getMissingTypes,
  getTemplates,
  getVersionDownloadUrl,
  getVersions,
  restoreTemplateVersion,
  updateTemplate,
  uploadTemplateFile,
  validateTemplateFile,
  type DocumentTemplate,
  type DocumentTemplateVersion,
} from '@/api/documentLibrary';
import { BookOpen, Copy, Download, History, Loader2, MoreHorizontal, Plus, Variable } from 'lucide-react';
import { cn } from '@/lib/utils';
import { isPlatformAdmin } from '@/lib/platformAdmin';

const QK_TEMPLATES = ['document-library', 'templates'] as const;
const QK_MISSING = ['document-library', 'missing-types'] as const;
const QK_VARIABLES = ['document-library', 'variables'] as const;

const CONTRACT_TYPES = new Set(['cdi', 'cdd', 'convention_stage', 'contrat_alternance']);

type CategoryFilter = 'all' | 'contrats' | 'avenants' | 'attestations' | 'fiches_poste' | 'participation' | 'autres';

const PARTICIPATION_TYPES = new Set(['bulletin_participation', 'bulletin_interessement']);

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

function hasRhWriteAccess(user: ReturnType<typeof useAuth>['user']): boolean {
  if (!user) return false;
  if (isPlatformAdmin(user)) return true;
  const r = user.role;
  return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
}

function canPrimaryHrActions(user: ReturnType<typeof useAuth>['user']): boolean {
  if (!user) return false;
  if (isPlatformAdmin(user)) return true;
  const ac = user.active_company;
  if (!ac) return false;
  if (ac.role === 'admin') return true;
  return ac.role === 'rh' && ac.is_primary;
}

function axiosErrorDetail(e: unknown): string | undefined {
  if (!e || typeof e !== 'object' || !('response' in e)) return undefined;
  const d = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  return typeof d === 'string' ? d : undefined;
}

function matchesCategory(t: DocumentTemplate, cat: CategoryFilter): boolean {
  if (cat === 'all') return true;
  const dt = t.document_type;
  if (cat === 'contrats') return CONTRACT_TYPES.has(dt);
  if (cat === 'avenants') return dt.startsWith('avenant_');
  if (cat === 'attestations') return dt.startsWith('attestation_');
  if (cat === 'fiches_poste') return dt === 'fiche_poste';
  if (cat === 'participation') return PARTICIPATION_TYPES.has(dt);
  if (cat === 'autres') return dt === 'document_transmis';
  return true;
}

type DocumentLibraryRhAddButtonProps = {
  rh: boolean;
  onClick: () => void;
  size?: 'default' | 'sm' | 'lg' | 'icon';
  variant?: 'default' | 'secondary' | 'outline' | 'destructive' | 'ghost' | 'link';
  className?: string;
  label: string;
  showPlus?: boolean;
  compactPlus?: boolean;
};

function DocumentLibraryRhAddButton({
  rh,
  onClick,
  size = 'default',
  variant = 'default',
  className,
  label,
  showPlus = true,
  compactPlus,
}: DocumentLibraryRhAddButtonProps) {
  if (!rh) return null;
  return (
    <Button type="button" size={size} variant={variant} className={cn(className)} onClick={onClick}>
      {showPlus && (
        <Plus className={cn('h-4 w-4', compactPlus ? 'mr-1 h-3 w-3' : 'mr-1.5')} />
      )}
      {label}
    </Button>
  );
}

export default function DocumentLibraryTab() {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const rh = hasRhWriteAccess(user);
  const primaryHr = canPrimaryHrActions(user);

  const [category, setCategory] = useState<CategoryFilter>('all');
  const [variablesOpen, setVariablesOpen] = useState(false);
  const [historyFor, setHistoryFor] = useState<DocumentTemplate | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<DocumentTemplate | null>(null);

  const [addOpen, setAddOpen] = useState(false);
  const [presetDocType, setPresetDocType] = useState<string | undefined>(undefined);
  const [addDocType, setAddDocType] = useState<string>('');
  const [addName, setAddName] = useState('');
  const [addDefault, setAddDefault] = useState(false);
  const [addFile, setAddFile] = useState<File | null>(null);
  const [addDrag, setAddDrag] = useState(false);
  const [addUnknownVars, setAddUnknownVars] = useState<string[]>([]);
  const [addValidating, setAddValidating] = useState(false);

  const [replaceFor, setReplaceFor] = useState<DocumentTemplate | null>(null);
  const [replaceFile, setReplaceFile] = useState<File | null>(null);

  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const {
    data: templates = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [...QK_TEMPLATES],
    queryFn: () => getTemplates(),
  });

  const { data: missingTypes = [] } = useQuery({
    queryKey: [...QK_MISSING],
    queryFn: () => getMissingTypes(),
  });

  const { data: variableItems = [] } = useQuery({
    queryKey: [...QK_VARIABLES],
    queryFn: () => getDocumentVariables(),
    enabled: variablesOpen,
  });

  const variableBlocks = useMemo(() => {
    const byCat = new Map<string, typeof variableItems>();
    for (const v of variableItems) {
      const list = byCat.get(v.category) ?? [];
      list.push(v);
      byCat.set(v.category, list);
    }
    return [...byCat.entries()].map(([category, rows]) => ({ category, rows }));
  }, [variableItems]);

  const hasFichePosteTemplate = useMemo(
    () =>
      templates.some(
        (t) =>
          t.document_type === 'fiche_poste' &&
          t.status === 'active' &&
          t.current_version != null
      ),
    [templates]
  );

  const filtered = useMemo(
    () => templates.filter((t) => matchesCategory(t, category)),
    [templates, category]
  );

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [...QK_TEMPLATES] });
    queryClient.invalidateQueries({ queryKey: [...QK_MISSING] });
  }, [queryClient]);

  const createMut = useMutation({
    mutationFn: async (vars: {
      document_type: string;
      name?: string;
      file: File;
      asDefault: boolean;
    }) => {
      const created = await createTemplate({
        document_type: vars.document_type,
        name: vars.name || undefined,
      });
      const uploaded = await uploadTemplateFile(created.id, vars.file);
      if (vars.asDefault && primaryHr) {
        await updateTemplate(created.id, { is_default: true });
      }
      return uploaded.unknown_variables ?? [];
    },
    onSuccess: (unknownVars) => {
      setAddOpen(false);
      setAddUnknownVars([]);
      invalidateAll();
      const unknown = unknownVars.length;
      toast({
        title: 'Modèle enregistré',
        description:
          unknown > 0
            ? `Le modèle a été ajouté. ${unknown} variable(s) non reconnue(s) dans le fichier.`
            : 'Le modèle a été ajouté à la bibliothèque.',
      });
    },
    onError: (e: unknown) => {
      const msg = axiosErrorDetail(e);
      toast({
        title: 'Erreur',
        description: typeof msg === 'string' ? msg : "Impossible d'enregistrer le modèle.",
        variant: 'destructive',
      });
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateTemplate>[1] }) =>
      updateTemplate(id, body),
    onSuccess: () => {
      invalidateAll();
      toast({ title: 'Mis à jour', description: 'Les modifications ont été enregistrées.' });
    },
    onError: (e: unknown) => {
      const msg = e && typeof e === 'object' && 'response' in e ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail : undefined;
      toast({
        title: 'Erreur',
        description: typeof msg === 'string' ? msg : 'Mise à jour impossible.',
        variant: 'destructive',
      });
    },
  });

  const archiveMut = useMutation({
    mutationFn: (id: string) => archiveTemplate(id),
    onSuccess: () => {
      invalidateAll();
      setArchiveTarget(null);
      toast({ title: 'Modèle archivé', description: 'Le modèle a été retiré de la bibliothèque active.' });
    },
    onError: (e: unknown) => {
      const msg = e && typeof e === 'object' && 'response' in e ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail : undefined;
      toast({
        title: 'Archivage impossible',
        description: typeof msg === 'string' ? msg : 'Vérifiez les documents générés liés à ce modèle.',
        variant: 'destructive',
      });
    },
  });

  const uploadReplaceMut = useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) => uploadTemplateFile(id, file),
    onSuccess: () => {
      invalidateAll();
      setReplaceFor(null);
      setReplaceFile(null);
      toast({ title: 'Nouvelle version', description: 'Le fichier a été importé.' });
    },
    onError: (e: unknown) => {
      const msg = axiosErrorDetail(e);
      toast({
        title: 'Échec de l’envoi',
        description: typeof msg === 'string' ? msg : 'Import impossible.',
        variant: 'destructive',
      });
    },
  });

  const openAddModal = (docType?: string) => {
    setPresetDocType(docType);
    setAddDocType(docType ?? '');
    setAddName('');
    setAddDefault(false);
    setAddFile(null);
    setAddUnknownVars([]);
    setAddOpen(true);
  };

  const handleAddFileSelected = async (file: File | null) => {
    setAddFile(file);
    setAddUnknownVars([]);
    if (!file) return;
    setAddValidating(true);
    try {
      const result = await validateTemplateFile(file);
      setAddUnknownVars(result.unknown_variables ?? []);
    } catch {
      toast({
        title: 'Analyse du fichier',
        description: 'Impossible de valider les variables du modèle.',
        variant: 'destructive',
      });
    } finally {
      setAddValidating(false);
    }
  };

  const handleSubmitAdd = () => {
    if (!addDocType) {
      toast({ title: 'Type requis', description: 'Choisissez un type de document.', variant: 'destructive' });
      return;
    }
    if (!addFile) {
      toast({ title: 'Fichier requis', description: 'Ajoutez un fichier .docx ou .html (max 5 Mo).', variant: 'destructive' });
      return;
    }
    createMut.mutate({
      document_type: addDocType,
      name: addName.trim() || undefined,
      file: addFile,
      asDefault: addDefault,
    });
  };

  const onRenameCommit = (tpl: DocumentTemplate) => {
    if (!renameValue.trim() || renameValue.trim() === tpl.name) {
      setRenameId(null);
      return;
    }
    updateMut.mutate({ id: tpl.id, body: { name: renameValue.trim() } });
    setRenameId(null);
  };

  const downloadVersion = async (templateId: string, v: DocumentTemplateVersion) => {
    try {
      const url = await getVersionDownloadUrl(templateId, v.id);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch {
      toast({ title: 'Téléchargement', description: 'Impossible d’obtenir le lien signé.', variant: 'destructive' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            Bibliothèque de modèles Word/HTML pour générer les documents RH de votre entreprise.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DocumentLibraryRhAddButton
            rh={rh}
            onClick={() => openAddModal()}
            size="sm"
            label="Ajouter un modèle"
          />
          <Select value={category} onValueChange={(v) => setCategory(v as CategoryFilter)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Catégorie" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous</SelectItem>
              <SelectItem value="contrats">Contrats</SelectItem>
              <SelectItem value="avenants">Avenants</SelectItem>
              <SelectItem value="attestations">Attestations</SelectItem>
              <SelectItem value="fiches_poste">Fiches de poste</SelectItem>
              <SelectItem value="participation">Participation & intéressement</SelectItem>
              <SelectItem value="autres">Autres</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={() => setVariablesOpen(true)}>
            <Variable className="mr-1.5 h-4 w-4" />
            Variables disponibles
          </Button>
        </div>
      </div>

      {!hasFichePosteTemplate && (
        <Card className="border-amber-200 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-950/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Fiche de poste</CardTitle>
            <CardDescription>
              Importez votre modèle Word — aucun modèle standard EYWAI pour ce type. EYWAI remplira
              automatiquement les champs salarié et entreprise.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => void downloadFichePosteExample()}>
              <Download className="mr-1.5 h-4 w-4" />
              Modèle exemple
            </Button>
            <DocumentLibraryRhAddButton
              rh={rh}
              onClick={() => openAddModal('fiche_poste')}
              size="sm"
              label="Importer ma fiche de poste"
            />
          </CardContent>
        </Card>
      )}

      {missingTypes.length > 0 && (
        <Card className="border-dashed bg-muted/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Types sans modèle personnalisé</CardTitle>
            <CardDescription>
              Le modèle standard EYWAI sera utilisé pour ces types tant qu’aucun fichier n’est importé.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {missingTypes.map((dt) => (
              <div
                key={dt}
                className="flex items-center gap-2 rounded-md border bg-background px-3 py-1.5 text-sm"
              >
                <span>{DOCUMENT_TYPE_LABELS[dt] ?? dt}</span>
                <DocumentLibraryRhAddButton
                  rh={rh}
                  onClick={() => openAddModal(dt)}
                  variant="secondary"
                  size="sm"
                  className="h-7"
                  label="Ajouter"
                  compactPlus
                />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
              </CardHeader>
              <CardContent className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-8 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {isError && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-base text-destructive">Erreur de chargement</CardTitle>
            <CardDescription>
              {(error as Error)?.message || 'Impossible de charger la bibliothèque.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Réessayer
            </Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && filtered.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-2 py-16 text-center text-muted-foreground">
            <BookOpen className="h-10 w-10 opacity-40" />
            <p className="text-sm">Aucun modèle dans cette catégorie.</p>
            <DocumentLibraryRhAddButton
              rh={rh}
              onClick={() => openAddModal()}
              size="sm"
              variant="secondary"
              label="Créer un premier modèle"
              showPlus={false}
            />
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((tpl) => {
            const cv = tpl.current_version;
            const typeLabel = DOCUMENT_TYPE_LABELS[tpl.document_type] ?? tpl.document_type;
            return (
              <Card key={tpl.id} className={cn(tpl.status === 'archived' && 'opacity-80')}>
                <CardHeader className="space-y-1 pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      {renameId === tpl.id ? (
                        <Input
                          autoFocus
                          className="h-8"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => onRenameCommit(tpl)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') onRenameCommit(tpl);
                            if (e.key === 'Escape') setRenameId(null);
                          }}
                        />
                      ) : (
                        <CardTitle className="truncate text-base">{tpl.name}</CardTitle>
                      )}
                      <div className="mt-1 flex flex-wrap gap-1">
                        <Badge variant="secondary" className="text-xs font-normal">
                          {typeLabel}
                        </Badge>
                        {tpl.is_default && <Badge className="text-xs">Par défaut</Badge>}
                        {tpl.status === 'archived' && (
                          <Badge variant="outline" className="text-xs">
                            Archivé
                          </Badge>
                        )}
                      </div>
                    </div>
                    {rh && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-56">
                          <DropdownMenuItem
                            disabled={!primaryHr || tpl.status !== 'active'}
                            onClick={() => {
                              if (!primaryHr) return;
                              updateMut.mutate({ id: tpl.id, body: { is_default: true } });
                            }}
                          >
                            Définir comme modèle par défaut
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={tpl.status !== 'active'}
                            onClick={() => {
                              if (tpl.status !== 'active') return;
                              setReplaceFor(tpl);
                              setReplaceFile(null);
                            }}
                          >
                            Remplacer (nouvelle version)
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={tpl.status !== 'active'}
                            onClick={() => {
                              setRenameId(tpl.id);
                              setRenameValue(tpl.name);
                            }}
                          >
                            Renommer
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            disabled={!primaryHr || tpl.status !== 'active'}
                            onClick={() => setArchiveTarget(tpl)}
                          >
                            Archiver
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => setHistoryFor(tpl)}>
                            <History className="mr-2 h-4 w-4" />
                            Historique des versions
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div className="text-muted-foreground">
                    {cv ? (
                      <>
                        <p>
                          Version active :{' '}
                          <span className="font-medium text-foreground">v{cv.version}</span>
                        </p>
                        <p className="truncate" title={cv.file_name}>
                          Fichier : {cv.file_name}
                        </p>
                        <p>Mise à jour : {formatDate(tpl.updated_at)}</p>
                      </>
                    ) : (
                      <p className="text-amber-700">Aucune version importée.</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" disabled title="Disponible au prochain bloc (prévisualisation)">
                      Prévisualiser
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Sheet open={variablesOpen} onOpenChange={setVariablesOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>Variables disponibles</SheetTitle>
            <SheetDescription>
              Placeholders à insérer dans vos modèles Word ou HTML — syntaxe{' '}
              <code className="text-xs">{'{{nom_variable}}'}</code>.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6 space-y-8 pr-2">
            {variableBlocks.map((block) => (
              <div key={block.category}>
                <h3 className="mb-2 text-sm font-semibold">{block.category}</h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Variable</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead className="w-10" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {block.rows.map((r) => (
                      <TableRow key={r.key}>
                        <TableCell className="font-mono text-xs">{`{{${r.key}}}`}</TableCell>
                        <TableCell className="text-xs">
                          <div>{r.label}</div>
                          <div className="text-muted-foreground">ex. {r.example}</div>
                        </TableCell>
                        <TableCell>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => {
                              void navigator.clipboard.writeText(`{{${r.key}}}`);
                              toast({ title: 'Copié', description: `{{${r.key}}}` });
                            }}
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ))}
          </div>
        </SheetContent>
      </Sheet>

      <HistoryDrawer
        template={historyFor}
        open={!!historyFor}
        onOpenChange={(o) => !o && setHistoryFor(null)}
        primaryHr={primaryHr}
        onDownload={downloadVersion}
        onRestored={invalidateAll}
        toast={toast}
      />

      <Dialog
        open={addOpen}
        onOpenChange={(o) => {
          setAddOpen(o);
          if (!o) setPresetDocType(undefined);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Ajouter un modèle</DialogTitle>
            <DialogDescription>Importez un fichier source (.docx ou .html, max 5 Mo).</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Type de document</Label>
              <Select
                value={addDocType}
                onValueChange={setAddDocType}
                disabled={!!presetDocType}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                  {Object.entries(DOCUMENT_TYPE_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>
                      {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Nom du modèle (optionnel)</Label>
              <Input value={addName} onChange={(e) => setAddName(e.target.value)} placeholder="Ex. CDI cadre commercial" />
            </div>
            <div
              className={cn(
                'flex min-h-[120px] cursor-pointer flex-col items-center justify-center rounded-md border border-dashed p-4 text-center text-sm transition-colors',
                addDrag ? 'border-primary bg-primary/5' : 'border-muted-foreground/30'
              )}
              onDragOver={(e) => {
                e.preventDefault();
                setAddDrag(true);
              }}
              onDragLeave={() => setAddDrag(false)}
              onDrop={(e) => {
                e.preventDefault();
                setAddDrag(false);
                const f = e.dataTransfer.files?.[0];
                if (f) void handleAddFileSelected(f);
              }}
              onClick={() => document.getElementById('dl-add-file')?.click()}
            >
              <input
                id="dl-add-file"
                type="file"
                accept=".docx,.html,.htm,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/html"
                className="hidden"
                onChange={(e) => void handleAddFileSelected(e.target.files?.[0] ?? null)}
              />
              {addValidating ? (
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyse des variables…
                </span>
              ) : addFile ? (
                <span className="font-medium">{addFile.name}</span>
              ) : (
                <span className="text-muted-foreground">Glissez-déposez ou cliquez pour choisir un fichier</span>
              )}
            </div>
            {primaryHr && (
              <div className="flex items-center space-x-2">
                <Checkbox id="add-def" checked={addDefault} onCheckedChange={(c) => setAddDefault(c === true)} />
                <Label htmlFor="add-def" className="text-sm font-normal">
                  Définir comme modèle par défaut
                </Label>
              </div>
            )}
            {addUnknownVars.length > 0 && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
                Variables non reconnues : {addUnknownVars.map((v) => `{{${v}}}`).join(', ')}. Ces
                champs resteront vides à la génération.
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleSubmitAdd} disabled={createMut.isPending}>
              {createMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!replaceFor} onOpenChange={(o) => !o && setReplaceFor(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouvelle version</DialogTitle>
            <DialogDescription>
              {replaceFor ? `Modèle : ${replaceFor.name}` : ''} — envoi d’un fichier .docx ou .html (max 5 Mo).
            </DialogDescription>
          </DialogHeader>
          <div
            className="flex min-h-[100px] cursor-pointer flex-col items-center justify-center rounded-md border border-dashed p-4 text-center text-sm"
            onClick={() => document.getElementById('dl-rep-file')?.click()}
          >
            <input
              id="dl-rep-file"
              type="file"
              accept=".docx,.html,.htm"
              className="hidden"
              onChange={(e) => setReplaceFile(e.target.files?.[0] ?? null)}
            />
            {replaceFile ? replaceFile.name : 'Choisir un fichier'}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReplaceFor(null)}>
              Annuler
            </Button>
            <Button
              disabled={!replaceFor || !replaceFile || uploadReplaceMut.isPending}
              onClick={() => {
                if (replaceFor && replaceFile) uploadReplaceMut.mutate({ id: replaceFor.id, file: replaceFile });
              }}
            >
              {uploadReplaceMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Importer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!archiveTarget} onOpenChange={(o) => !o && setArchiveTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archiver ce modèle ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le modèle ne sera plus proposé pour les nouvelles générations. Cette action est réservée au RH principal.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => archiveTarget && archiveMut.mutate(archiveTarget.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Archiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function HistoryDrawer({
  template,
  open,
  onOpenChange,
  primaryHr,
  onDownload,
  onRestored,
  toast,
}: {
  template: DocumentTemplate | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  primaryHr: boolean;
  onDownload: (templateId: string, v: DocumentTemplateVersion) => void;
  onRestored: () => void;
  toast: ReturnType<typeof useToast>['toast'];
}) {
  const queryClient = useQueryClient();
  const tid = template?.id;
  const { data: versions = [], isLoading } = useQuery({
    queryKey: ['document-library', 'versions', tid],
    queryFn: () => getVersions(tid as string),
    enabled: open && !!tid,
  });

  const restoreMut = useMutation({
    mutationFn: ({ templateId, versionId }: { templateId: string; versionId: string }) =>
      restoreTemplateVersion(templateId, versionId),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['document-library', 'versions', vars.templateId] });
      onRestored();
      toast({ title: 'Version restaurée', description: 'Une nouvelle version a été créée à partir de ce fichier.' });
    },
    onError: (e: unknown) => {
      const msg = e && typeof e === 'object' && 'response' in e ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail : undefined;
      toast({
        title: 'Restauration impossible',
        description: typeof msg === 'string' ? msg : 'Action refusée ou erreur serveur.',
        variant: 'destructive',
      });
    },
  });

  const maxV = versions.length ? Math.max(...versions.map((v) => v.version)) : 0;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Historique des versions</SheetTitle>
          <SheetDescription>{template?.name}</SheetDescription>
        </SheetHeader>
        <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
          {isLoading && (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {!isLoading &&
            versions.map((v) => {
              const isCurrent = v.version === maxV;
              return (
                <div
                  key={v.id}
                  className="flex flex-col gap-2 rounded-md border bg-card p-3 text-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">v{v.version}</span>
                    {isCurrent && <Badge variant="outline">Active</Badge>}
                  </div>
                  <p className="text-xs text-muted-foreground">{formatDate(v.created_at)}</p>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => tid && onDownload(tid, v)}>
                      <Download className="mr-1 h-3 w-3" />
                      Télécharger
                    </Button>
                    {!isCurrent && primaryHr && tid && (
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={restoreMut.isPending}
                        onClick={() => restoreMut.mutate({ templateId: tid, versionId: v.id })}
                      >
                        Restaurer
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
      </SheetContent>
    </Sheet>
  );
}
