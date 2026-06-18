import { downloadBlob } from '@/lib/downloadBlob';
import { openBlobPreview } from '@/lib/openSignedUrlPreview';

export function previewAnnualReviewPdf(blob: Blob, reviewId?: string): void {
  openBlobPreview(blob, {
    title: 'Entretien annuel',
    downloadName: reviewId ? `entretien_${reviewId}.pdf` : 'entretien.pdf',
  });
}

export function downloadAnnualReviewPdfFile(blob: Blob, reviewId: string): void {
  downloadBlob(blob, `entretien_${reviewId}.pdf`);
}

export function previewConvocationPdf(blob: Blob, reviewId?: string): void {
  openBlobPreview(blob, {
    title: 'Convocation entretien',
    downloadName: reviewId ? `convocation_${reviewId}.pdf` : 'convocation.pdf',
  });
}

export function downloadConvocationPdfFile(blob: Blob, reviewId: string): void {
  downloadBlob(blob, `convocation_${reviewId}.pdf`);
}
