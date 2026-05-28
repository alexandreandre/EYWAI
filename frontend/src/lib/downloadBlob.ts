/**
 * Téléchargement et prévisualisation de Blob côté navigateur (DRY exports CSV/PDF).
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = 'noopener';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** Ouvre un PDF ou média dans un nouvel onglet (révocation différée). */
export function openBlobInNewTab(blob: Blob, revokeAfterMs = 100): void {
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  if (revokeAfterMs >= 0) {
    setTimeout(() => URL.revokeObjectURL(url), revokeAfterMs);
  }
}

/** URL objet pour lecteur vidéo / audio (le caller gère revokeObjectURL). */
export function createBlobPreviewUrl(blob: Blob): string {
  return URL.createObjectURL(blob);
}
