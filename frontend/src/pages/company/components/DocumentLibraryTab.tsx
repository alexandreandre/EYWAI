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
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useCompanyPlan } from '@/hooks/useCompanyPlan';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import {
  DOCUMENT_TYPE_LABELS,
  archiveTemplate,
  createTemplate,
  getMissingTypes,
  getTemplates,
  getVersionDownloadUrl,
  getVersions,
  restoreTemplateVersion,
  updateTemplate,
  uploadTemplateFile,
  type DocumentTemplate,
  type DocumentTemplateVersion,
} from '@/api/documentLibrary';
import { BookOpen, Download, History, Loader2, MoreHorizontal, Plus, Variable } from 'lucide-react';
import { cn } from '@/lib/utils';

const QK_TEMPLATES = ['document-library', 'templates'] as const;
const QK_MISSING = ['document-library', 'missing-types'] as const;

const CONTRACT_TYPES = new Set(['cdi', 'cdd', 'convention_stage', 'contrat_alternance']);

type CategoryFilter = 'all' | 'contrats' | 'avenants' | 'attestations';

const VARIABLE_ROWS: { category: string; rows: { variable: string; description: string; example: string }[] }[] = [
  {
    category: 'Salarié',
    rows: [
      { variable: '{{salarie.nom}}', description: 'Nom de famille', example: 'Dupont' },
      { variable: '{{salarie.prenom}}', description: 'Prénom', example: 'Marie' },
      { variable: '{{salarie.date_embauche}}', description: 'Date d’embauche', example: '01/09/2023' },
    ],
  },
  {
    category: 'Avenant',
    rows: [
      { variable: '{{avenant.date_effet}}', description: 'Date d’effet', example: '01/01/2026' },
      { variable: '{{avenant.motif}}', description: 'Motif', example: 'Évolution de poste' },
    ],
  },
  {
    category: 'Entreprise',
    rows: [
      { variable: '{{entreprise.raison_sociale}}', description: 'Raison sociale', example: 'ACME SAS' },
      { variable: '{{entreprise.siret}}', description: 'SIRET', example: '123 456 789 00012' },
    ],
  },
  {
    category: 'Système',
    rows: [
      { variable: '{{date_du_jour}}', description: 'Date du jour', example: '18/04/2026' },
      { variable: '{{document.reference}}', description: 'Référence document', example: 'DOC-2026-0042' },
    ],
  },
];

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
  if (user.is_super_admin) return true;
  const r = user.role;
  return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
}

function canPrimaryHrActions(user: ReturnType<typeof useAuth>['user']): boolean {
  if (!user) return false;
  if (user.is_super_admin) return true;
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
  return true;
}

type DocumentLibraryRhAddButtonProps = {
  rh: boolean;
  isPremium: boolean;
  isPlanLoading: boolean;
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
  isPremium,
  isPlanLoading,
  onClick,
  size = 'default',
  variant = 'default',
  className,
  label,
  showPlus = true,
  compactPlus,
}: DocumentLibraryRhAddButtonProps) {
  if (!rh) return null;
  const locked = !isPremium || isPlanLoading;
  const inner = (
    <Button type="button" size={size} variant={variant} className={cn(className)} disabled={locked} onClick={onClick}>
      {showPlus && (
        <Plus className={cn('h-4 w-4', compactPlus ? 'mr-1 h-3 w-3' : 'mr-1.5')} />
      )}
      {label}
    </Button>
  );
  if (!locked) return inner;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex">{inner}</span>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs text-sm">
          Disponible dans le plan premium. Contactez-nous pour activer.
        </TooltipContent>
      </Tooltip>
      <Badge
        variant="outline"
        className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
      >
        Premium
      </Badge>
    </div>
  );
}

export default function DocumentLibraryTab() {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { isPremium, isLoading: isPlanLoading } = useCompanyPlan();
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

  const [replaceFor, setReplaceFor] = useState<DocumentTemplate | null>(null);
  const [replaceFile, setReplaceFile] = useState<File | null>(null);

  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const [premiumRequiredOpen, setPremiumRequiredOpen] = useState(false);

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
      await uploadTemplateFile(created.id, vars.file);
      if (vars.asDefault && primaryHr) {
        await updateTemplate(created.id, { is_default: true });
      }
      return created.id;
    },
    onSuccess: () => {
      setAddOpen(false);
      invalidateAll();
      toast({ title: 'Modèle enregistré', description: 'Le modèle a été ajouté à la bibliothèque.' });
    },
    onError: (e: unknown) => {
      if (axiosErrorDetail(e) === 'PREMIUM_REQUIRED') {
        setAddOpen(false);
        setPremiumRequiredOpen(true);
        return;
      }
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
      if (axiosErrorDetail(e) === 'PREMIUM_REQUIRED') {
        setReplaceFor(null);
        setReplaceFile(null);
        setPremiumRequiredOpen(true);
        return;
      }
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
    setAddOpen(true);
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
          <h2 className="text-xl font-semibold tracking-tight">Bibliothèque de modèles</h2>
          <p className="text-sm text-muted-foreground">
            Modèles Word/HTML utilisés pour les documents RH de votre entreprise.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DocumentLibraryRhAddButton
            rh={rh}
            isPremium={isPremium}
            isPlanLoading={isPlanLoading}
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
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={() => setVariablesOpen(true)}>
            <Variable className="mr-1.5 h-4 w-4" />
            Variables disponibles
          </Button>
        </div>
      </div>

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
                  isPremium={isPremium}
                  isPlanLoading={isPlanLoading}
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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
              isPremium={isPremium}
              isPlanLoading={isPlanLoading}
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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
                            disabled={tpl.status !== 'active' || !isPremium}
                            onClick={() => {
                              if (tpl.status !== 'active' || !isPremium) return;
                              setReplaceFor(tpl);
                              setReplaceFile(null);
                            }}
                          >
                            Remplacer (nouvelle version)
                            {!isPremium ? ' (Premium)' : ''}
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
              Placeholders à insérer dans vos modèles Word ou HTML (syntaxe indicative).
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6 space-y-8 pr-2">
            {VARIABLE_ROWS.map((block) => (
              <div key={block.category}>
                <h3 className="mb-2 text-sm font-semibold">{block.category}</h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Variable</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Exemple</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {block.rows.map((r) => (
                      <TableRow key={r.variable}>
                        <TableCell className="font-mono text-xs">{r.variable}</TableCell>
                        <TableCell className="text-xs">{r.description}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{r.example}</TableCell>
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
                if (f) setAddFile(f);
              }}
              onClick={() => document.getElementById('dl-add-file')?.click()}
            >
              <input
                id="dl-add-file"
                type="file"
                accept=".docx,.html,.htm,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/html"
                className="hidden"
                onChange={(e) => setAddFile(e.target.files?.[0] ?? null)}
              />
              {addFile ? (
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

      <Dialog open={premiumRequiredOpen} onOpenChange={setPremiumRequiredOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Fonctionnalité Premium</DialogTitle>
            <DialogDescription className="text-left text-sm text-muted-foreground">
              L&apos;upload de modèles personnalisés est disponible dans le plan premium EYWAI. Contactez-nous pour
              activer cette fonctionnalité.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" onClick={() => setPremiumRequiredOpen(false)}>
              Fermer
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
