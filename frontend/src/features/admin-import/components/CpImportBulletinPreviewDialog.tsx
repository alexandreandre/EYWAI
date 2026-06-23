import { useEffect, useMemo, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

type CpImportBulletinPreviewDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  file: File | null;
  pageNumber: number;
  employeeLabel?: string;
  sourceFile?: string;
  periodLabel?: string;
};

export function CpImportBulletinPreviewDialog({
  open,
  onOpenChange,
  file,
  pageNumber,
  employeeLabel,
  sourceFile,
  periodLabel,
}: CpImportBulletinPreviewDialogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pageWidth, setPageWidth] = useState(720);

  const fileUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  useEffect(() => {
    const updateWidth = () => {
      setPageWidth(Math.min(720, window.innerWidth - 120));
    };
    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  useEffect(() => {
    if (!fileUrl) return undefined;
    return () => URL.revokeObjectURL(fileUrl);
  }, [fileUrl]);

  useEffect(() => {
    if (!open) {
      setNumPages(null);
      setLoadError(null);
    }
  }, [open]);

  const safePage =
    numPages != null ? Math.min(Math.max(1, pageNumber), numPages) : Math.max(1, pageNumber);

  useEffect(() => {
    if (!open) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = 0;
  }, [open, safePage, fileUrl]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="!flex max-h-[92vh] max-w-4xl flex-col gap-3 overflow-hidden p-4 sm:p-6">
        <DialogHeader>
          <DialogTitle className="text-base">
            Bulletin — {employeeLabel?.trim() || 'Salarié'}
          </DialogTitle>
          <DialogDescription className="text-left">
            {sourceFile ? `${sourceFile}` : null}
            {periodLabel ? ` · ${periodLabel}` : null}
            {numPages != null ? ` · page ${safePage}/${numPages}` : ` · page ${safePage}`}
          </DialogDescription>
        </DialogHeader>
        <div
          ref={scrollRef}
          className="min-h-0 flex-1 overflow-auto rounded-md border bg-muted/30 p-3"
        >
          {!file || !fileUrl ? (
            <p className="p-4 text-sm text-muted-foreground">
              Fichier PDF introuvable — réimportez le bulletin puis ré-analysez.
            </p>
          ) : loadError ? (
            <p className="p-4 text-sm text-destructive">{loadError}</p>
          ) : (
            <div className="mx-auto w-fit [&_.react-pdf__Page]:!block [&_.react-pdf__Page_canvas]:!block">
              <Document
                file={fileUrl}
                onLoadSuccess={({ numPages: total }) => {
                  setNumPages(total);
                  setLoadError(null);
                  requestAnimationFrame(() => {
                    if (scrollRef.current) scrollRef.current.scrollTop = 0;
                  });
                }}
                onLoadError={(error) => {
                  setLoadError(error.message || 'Impossible d’afficher le PDF.');
                }}
                loading={
                  <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Chargement du bulletin…
                  </div>
                }
              >
                <Page
                  pageNumber={safePage}
                  width={pageWidth}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                  onRenderSuccess={() => {
                    if (scrollRef.current) scrollRef.current.scrollTop = 0;
                  }}
                />
              </Document>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
