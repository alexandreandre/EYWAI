/**
 * Intitulé court pour l'affichage catalogue CC (sans extensions légales KALI).
 */
export function formatCatalogConventionName(name: string | null | undefined): string {
  if (!name?.trim()) return name ?? '';

  const cuts = [
    /\s*\(c['']est/i,
    /\s*\(occupant/i,
    /\.\s*[ÉE]tendue par/i,
    /\.\s*Elle s['']applique/i,
    /\.\s*Dans sa rédaction/i,
  ];

  for (const pattern of cuts) {
    const match = name.match(pattern);
    if (match?.index !== undefined) {
      return name.slice(0, match.index).trim();
    }
  }

  return name.trim();
}
