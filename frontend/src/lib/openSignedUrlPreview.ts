/** Ouvre une URL signée en aperçu (nouvel onglet, sans attribut download). */
export function openSignedUrlPreview(url: string | null | undefined): void {
  const trimmed = url?.trim();
  if (!trimmed) return;
  window.open(trimmed, '_blank', 'noopener,noreferrer');
}
