import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { AlertCircle, Download, Loader2 } from 'lucide-react';

export type SignedPdfPreviewDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  subtitle?: string;
  pdfUrl: string | null;
  loading?: boolean;
  error?: string | null;
  canDownload?: boolean;
  onDownload?: () => void;
};

export function SignedPdfPreviewDialog({
  open,
  onOpenChange,
  title,
  subtitle,
  pdfUrl,
  loading = false,
  error = null,
  canDownload = false,
  onDownload,
}: SignedPdfPreviewDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(92vh,900px)] max-w-5xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 space-y-1 border-b px-6 py-4 pr-14">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <DialogTitle>{title}</DialogTitle>
              <DialogDescription className={subtitle ? 'line-clamp-2' : 'sr-only'}>
                {subtitle || 'Aperçu du document PDF.'}
              </DialogDescription>
            </div>
            {canDownload && onDownload ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={loading || Boolean(error) || !pdfUrl}
                onClick={onDownload}
                className="shrink-0"
              >
                <Download className="mr-2 h-4 w-4" />
                Télécharger
              </Button>
            ) : null}
          </div>
        </DialogHeader>

        <div className="relative min-h-0 flex-1 bg-muted/30">
          {loading ? (
            <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin" />
              <p className="text-sm">Chargement du document…</p>
            </div>
          ) : error ? (
            <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 px-6 text-center">
              <AlertCircle className="h-10 w-10 text-destructive" aria-hidden />
              <div>
                <p className="font-medium text-destructive">Erreur</p>
                <p className="mt-1 text-sm text-muted-foreground">{error}</p>
              </div>
            </div>
          ) : pdfUrl ? (
            <iframe
              title={title}
              src={pdfUrl}
              className="h-full min-h-[420px] w-full border-0 bg-white"
            />
          ) : (
            <div className="flex h-full min-h-[420px] items-center justify-center px-6 text-sm text-muted-foreground">
              Impossible d&apos;afficher le document.
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
