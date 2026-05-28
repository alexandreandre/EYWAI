import { downloadBlob, openBlobInNewTab } from '@/lib/downloadBlob';

export function previewAnnualReviewPdf(blob: Blob): void {
  openBlobInNewTab(blob, 100);
}

export function downloadAnnualReviewPdfFile(blob: Blob, reviewId: string): void {
  downloadBlob(blob, `entretien_${reviewId}.pdf`);
}
