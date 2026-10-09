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

export function phraseJoursEnConflit(n: number): string {
  const sujet =
    n > 1
      ? `${n} jours portent des heures alors que le planning les marque`
      : `${n} jour porte des heures alors que le planning le marque`;
  return `${sujet} en arrêt ou en absence : le bulletin sera refusé tant que ce n’est pas corrigé (voir détail).`;
}

export function phraseJoursPreserves(n: number): string {
  return `${n} ${n > 1 ? 'jours laissés' : 'jour laissé'} en l’état : absence validée (voir détail).`;
}

export function phraseEnregistrementPartiel(jours: number, echecs: number): string {
  return `${pluriel(jours, 'jour', 'jours')} · ${pluriel(echecs, 'échec', 'échecs')}.`;
}

export function phraseEcartsOcr(n: number): string {
  return `${pluriel(n, 'écart', 'écarts')} vision/OCR — vérifiez les heures signalées.`;
}

export function phraseAlertesMasquees(n: number): string {
  return n > 1 ? `${n} alertes masquées (salariés hors PDF)` : `${n} alerte masquée (salarié hors PDF)`;
}

export function phraseHorsReleve(n: number): string {
  return n > 1
    ? `${n} salariés du roster absents du relevé — normal, non affichés.`
    : `${n} salarié du roster absent du relevé — normal, non affiché.`;
}
