/**
 * Section « Documents générés » (PDF créés par les RH, module Documents).
 * Intégrée en bas de la page Mes documents collaborateur.
 */

import { useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileText } from 'lucide-react';

import {
  downloadDocument,
  getDocuments,
  triggerSignedDocumentDownload,
  type GeneratedDocument,
} from '@/api/documents';
import { DOCUMENT_TYPE_LABELS } from '@/api/documentLibrary';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import { useCurrentEmployee } from '@/hooks/useCurrentEmployee';
import { cn } from '@/lib/utils';

const QK = ['employee', 'generated-documents', 'embedded'] as const;

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

export function EmployeeGeneratedDocumentsSection() {
  const { toast } = useToast();
  const { employee, isLoading: empLoading, notConfigured } = useCurrentEmployee();

  const {
    data: rows = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [...QK, employee?.id],
    queryFn: () => getDocuments({ employee_id: employee!.id }),
    enabled: Boolean(employee?.id),
  });

  const handleDownload = useCallback(
    async (id: string, fileName?: string | null) => {
      try {
        const res = await downloadDocument(id);
        triggerSignedDocumentDownload(res, fileName || 'document.pdf');
      } catch {
        toast({ title: 'Téléchargement', description: 'Impossible d’obtenir le lien.', variant: 'destructive' });
      }
    },
    [toast]
  );

  const showSkeleton = empLoading || (Boolean(employee?.id) && isLoading);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <FileText className="h-5 w-5" />
          Documents générés
        </CardTitle>
        <CardDescription>
          PDF générés par les services RH (contrats, attestations, etc.). Lecture et téléchargement uniquement.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {notConfigured && (
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50/50 p-4 text-sm text-amber-950">
            <p className="font-medium">Profil non relié</p>
            <p className="text-muted-foreground">
              Aucune fiche collaborateur n’est associée à votre compte pour cette entreprise. Contactez les RH pour
              consulter vos documents générés.
            </p>
          </div>
        )}

        {showSkeleton && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}
        {!showSkeleton && isError && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">
            <p className="font-medium text-destructive">Erreur de chargement</p>
            <p className="text-muted-foreground">{(error as Error)?.message}</p>
            <Button variant="outline" size="sm" className="mt-2" type="button" onClick={() => refetch()}>
              Réessayer
            </Button>
          </div>
        )}
        {!showSkeleton && !isError && employee?.id && rows.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Aucun document généré disponible pour le moment.
          </p>
        )}
        {!showSkeleton && !isError && employee?.id && rows.length > 0 && (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Date génération</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((d: GeneratedDocument) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-medium">
                      {DOCUMENT_TYPE_LABELS[d.document_type] ?? d.document_type}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                      {formatDate(d.created_at)}
                    </TableCell>
                    <TableCell>{statusBadge(d.status)}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={!d.file_url}
                        onClick={() => handleDownload(d.id, d.file_name)}
                      >
                        Télécharger
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
