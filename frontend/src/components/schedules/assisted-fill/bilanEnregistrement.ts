/**
 * Ce que dit le toast après l'enregistrement d'un relevé : le vrai nombre de
 * jours écrits (09/10/2026 : « 6 jour(s) » pour un fichier de 3 jours, parce que
 * l'aperçu du lot porte aussi le prévu), avec des pluriels accordés.
 */

export function joursEcritsDuLot(
  summary: { committed_days?: number | null } | null | undefined,
  employees: { days: { nature?: string | null }[] }[] | null | undefined,
): number {
  if (typeof summary?.committed_days === 'number') return summary.committed_days;
  return (employees ?? []).reduce(
    (n, e) => n + e.days.filter((d) => d.nature !== 'prevu').length,
    0,
  );
}

const pluriel = (n: number, un: string, plusieurs: string) => `${n} ${n > 1 ? plusieurs : un}`;

export function phraseEnregistrement(salaries: number, jours: number): string {
  return `${pluriel(salaries, 'salarié', 'salariés')} · ${pluriel(jours, 'jour', 'jours')} mis à jour.`;
}
