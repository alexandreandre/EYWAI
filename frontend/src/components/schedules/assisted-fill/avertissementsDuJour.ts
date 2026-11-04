/**
 * Avertissements de comptabilisation d'un salarié (« Jour N : … ») : rangés
 * sous leur jour dans la revue, et résumés sur la ligne, même quand le
 * salarié est « Prêt ». Sans ça, les heures en plus à valider et les
 * pointages incomplets ne se voyaient nulle part avant l'enregistrement.
 */

const DU_JOUR = /^\s*Jour (\d{1,2}) : (.+)$/;

const INCOMPLET = /pointage incomplet|sans sortie|sans entrée|journée à compléter/i;
const HEURES_EN_PLUS = /HS à valider|heures? en plus|au-delà du seuil/i;

export function avertissementsDuJour(warnings: string[], jour: number): string[] {
  const out: string[] = [];
  for (const w of warnings) {
    const m = DU_JOUR.exec(w);
    if (m && Number(m[1]) === jour) out.push(m[2].trim());
  }
  return out;
}

export function avertissementsHorsJour(warnings: string[]): string[] {
  return warnings.filter((w) => !DU_JOUR.test(w));
}

export interface ResumeAvertissements {
  heuresEnPlus: number;
  incomplets: number;
}

export function resumeAvertissements(warnings: string[]): ResumeAvertissements {
  const enPlus = new Set<number>();
  const incomplets = new Set<number>();
  for (const w of warnings) {
    const m = DU_JOUR.exec(w);
    if (!m) continue;
    const jour = Number(m[1]);
    if (INCOMPLET.test(m[2])) incomplets.add(jour);
    else if (HEURES_EN_PLUS.test(m[2])) enPlus.add(jour);
  }
  return { heuresEnPlus: enPlus.size, incomplets: incomplets.size };
}

const jours = (n: number) => `${n} jour${n > 1 ? 's' : ''}`;

export function phraseResume(r: ResumeAvertissements): string | null {
  const morceaux: string[] = [];
  if (r.heuresEnPlus) morceaux.push(`Heures en plus à valider : ${jours(r.heuresEnPlus)}`);
  if (r.incomplets) morceaux.push(`Pointage incomplet : ${jours(r.incomplets)}`);
  return morceaux.length ? morceaux.join(' · ') : null;
}
