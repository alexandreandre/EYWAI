import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from '@/components/ui/use-toast';
import {
  downloadDocument,
  triggerSignedDocumentDownload,
  generateDocument,
  getDocuments,
  type DocumentCategory,
  type GeneratedDocument,
} from '@/api/documents';
import { DOCUMENT_TYPE_LABELS, getTemplates, type DocumentTemplate } from '@/api/documentLibrary';
import { cn } from '@/lib/utils';
import { FileText, Loader2, RefreshCw, Settings2 } from 'lucide-react';

const QK_DOCS = (employeeId: string) => ['employee-generated-documents', employeeId] as const;

const CONTRACT_TYPES = ['cdi', 'cdd', 'convention_stage', 'contrat_alternance'] as const;
const AVENANT_TYPES = [
  'avenant_salaire',
  'avenant_poste',
  'avenant_temps',
  'avenant_lieu',
  'avenant_general',
] as const;

/** Attestations courantes (+ retraite) — génération PDF category attestation_courante */
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

export interface EmployeeDetailDocumentsRhEmployee {
  id: string;
  first_name: string;
  last_name: string;
  job_title?: string | null;
  salaire_de_base?: unknown;
  duree_hebdomadaire?: unknown;
  lieu_travail?: unknown;
  workplace?: unknown;
  poste?: string | null;
  weekly_hours?: unknown;
}

type GenMode = 'contrat' | 'avenant' | 'attestation' | null;

export function EmployeeDetailDocumentsRhSection({
  employeeId,
  employee,
}: {
  employeeId: string;
  employee: EmployeeDetailDocumentsRhEmployee;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const displayName = `${employee.last_name} ${employee.first_name}`.trim();

  const [genMode, setGenMode] = useState<GenMode>(null);
  const [genDocType, setGenDocType] = useState('');
  const [genTemplate, setGenTemplate] = useState('__eywai__');
  const [genDateEffet, setGenDateEffet] = useState('');
  const [genMotif, setGenMotif] = useState('');
  const [eywaiBanner, setEywaiBanner] = useState(false);

  const { data: rows = [], isLoading, isError, refetch } = useQuery({
    queryKey: QK_DOCS(employeeId),
    queryFn: () => getDocuments({ employee_id: employeeId }),
  });

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
    queryClient.invalidateQueries({ queryKey: QK_DOCS(employeeId) });
  };

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
    setGenDocType('');
    setGenTemplate('__eywai__');
    setGenDateEffet('');
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

  const handleDownload = async (id: string, fileName?: string | null) => {
    try {
      const res = await downloadDocument(id);
      triggerSignedDocumentDownload(res, fileName || 'document.pdf');
    } catch {
      toast({ title: 'Téléchargement', description: 'Lien indisponible.', variant: 'destructive' });
    }
  };

  const handleRegenerate = (row: GeneratedDocument) => {
    if (row.document_type.startsWith('avenant')) {
      openAvenant({
        document_type: row.document_type,
        template_id: row.is_eywai_template ? null : row.template_id,
      });
    } else {
      setGenMode('contrat');
      setGenDocType(row.document_type);
      setGenTemplate(row.is_eywai_template ? '__eywai__' : row.template_id || '__eywai__');
      setGenDateEffet('');
      setGenMotif('');
      setEywaiBanner(false);
    }
  };

  const canSubmitContrat = genMode === 'contrat' && !!genDocType && !!genDateEffet;
  const canSubmitAvenant = genMode === 'avenant' && !!genDocType && !!genDateEffet;
  const canSubmitAttestation = genMode === 'attestation' && !!genDocType;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" size="sm" onClick={openContrat}>
          Générer un contrat
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={() => openAvenant()}>
          Générer un avenant
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={openAttestation}>
          Générer une attestation
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => navigate('/company#bibliotheque')}
        >
          <Settings2 className="mr-2 h-4 w-4" />
          Gérer les modèles
        </Button>
      </div>

      {eywaiBanner && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Générée avec le modèle standard EYWAI.
        </div>
      )}

      <Dialog
        open={genMode === 'contrat'}
        onOpenChange={(o) => {
          if (!o) setGenMode(null);
        }}
      >
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

      <Dialog
        open={genMode === 'avenant'}
        onOpenChange={(o) => {
          if (!o) setGenMode(null);
        }}
      >
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

      <Dialog
        open={genMode === 'attestation'}
        onOpenChange={(o) => {
          if (!o) setGenMode(null);
        }}
      >
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

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4" />
            Documents générés
          </CardTitle>
          <CardDescription>PDF générés via le module Documents (hors contrat uploadé).</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          )}
          {isError && (
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Réessayer
            </Button>
          )}
          {!isLoading && !isError && rows.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Aucun document généré pour ce salarié.
            </p>
          )}
          {!isLoading && !isError && rows.length > 0 && (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Date génération</TableHead>
                    <TableHead>Modèle utilisé</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((d) => (
                    <TableRow key={d.id}>
                      <TableCell>{DOCUMENT_TYPE_LABELS[d.document_type] ?? d.document_type}</TableCell>
                      <TableCell className="whitespace-nowrap text-sm">{formatDate(d.created_at)}</TableCell>
                      <TableCell>
                        {d.is_eywai_template ? 'Standard EYWAI' : d.template_name || '—'}
                      </TableCell>
                      <TableCell>{statusBadge(d.status)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!d.file_url}
                            onClick={() => handleDownload(d.id, d.file_name)}
                          >
                            Télécharger
                          </Button>
                          <Button variant="secondary" size="sm" onClick={() => handleRegenerate(d)}>
                            <RefreshCw className="mr-1 h-3 w-3" />
                            Regénérer
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
    </div>
  );
}
