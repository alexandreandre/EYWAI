import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  downloadDocument,
  openDocumentPreview,
  triggerSignedDocumentDownload,
  type GeneratedDocument,
} from '@/api/documents';
import { useToast } from '@/hooks/use-toast';
import { ArrowDownToLine, Eye, Loader2 } from 'lucide-react';

export function EmployeeSelfGeneratedDocActions({
  doc,
}: {
  doc: GeneratedDocument;
}) {
  const { toast } = useToast();
  const [loading, setLoading] = useState<'view' | 'download' | null>(null);
  const hasFile = Boolean(doc.file_url);

  const handleView = async () => {
    setLoading('view');
    try {
      await openDocumentPreview(doc.id, {
        title: doc.file_name || 'Document',
        downloadName: doc.file_name || 'document.pdf',
      });
    } catch {
      toast({
        title: 'Aperçu',
        description: 'Impossible d’ouvrir le document.',
        variant: 'destructive',
      });
    } finally {
      setLoading(null);
    }
  };

  const handleDownload = async () => {
    setLoading('download');
    try {
      const res = await downloadDocument(doc.id);
      triggerSignedDocumentDownload(res, doc.file_name || 'document.pdf');
    } catch {
      toast({
        title: 'Téléchargement',
        description: 'Impossible d’obtenir le lien.',
        variant: 'destructive',
      });
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="flex items-center gap-0.5">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        disabled={!hasFile || loading !== null}
        title="Visualiser le document"
        onClick={() => void handleView()}
      >
        {loading === 'view' ? (
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
        disabled={!hasFile || loading !== null}
        title="Télécharger"
        onClick={() => void handleDownload()}
      >
        {loading === 'download' ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <ArrowDownToLine className="h-4 w-4" />
        )}
        <span className="sr-only">Télécharger</span>
      </Button>
    </div>
  );
}
