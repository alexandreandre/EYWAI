/** Ouvre une URL signée en aperçu (dialogue intégré, sans attribut download). */

export type SignedPdfPreviewOptions = {
  title?: string;
  subtitle?: string;
  downloadUrl?: string | null;
  downloadName?: string;
};

type PreviewOpener = (url: string, options?: SignedPdfPreviewOptions) => void;
type BlobPreviewOpener = (blob: Blob, options?: SignedPdfPreviewOptions) => void;

let previewOpener: PreviewOpener | null = null;
let blobPreviewOpener: BlobPreviewOpener | null = null;

export function registerSignedPdfPreviewOpener(opener: PreviewOpener | null): void {
  previewOpener = opener;
}

export function registerSignedPdfBlobOpener(opener: BlobPreviewOpener | null): void {
  blobPreviewOpener = opener;
}

export function openBlobPreview(blob: Blob, options?: SignedPdfPreviewOptions): void {
  if (blobPreviewOpener) {
    blobPreviewOpener(blob, options);
    return;
  }
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

export function openSignedUrlPreview(
  url: string | null | undefined,
  options?: SignedPdfPreviewOptions
): void {
  const trimmed = url?.trim();
  if (!trimmed) return;
  if (previewOpener) {
    previewOpener(trimmed, options);
    return;
  }
  window.open(trimmed, '_blank', 'noopener,noreferrer');
}
