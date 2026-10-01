/**
 * Affichage des explications déjà posées sur le bulletin.
 *
 * Le front ne recalcule pas la paie : astérisque et info-bulle seulement
 * quand `explication` est présent et non vide.
 */

export type LigneExpliquee = {
  libelle: string;
  explication: string;
};

type LignePossible = {
  libelle?: string | null;
  explication?: string | null;
};

export function texteInfobulle(
  ligne: { libelle?: string | null; explication?: string | null } | null | undefined
): string | null {
  const texte = ligne?.explication;
  if (typeof texte !== 'string') return null;
  const coupe = texte.trim();
  return coupe.length > 0 ? coupe : null;
}

export function afficherAsterisque(
  ligne: { libelle?: string | null; explication?: string | null } | null | undefined
): boolean {
  return texteInfobulle(ligne) !== null;
}

function collecter(lignes: unknown, acc: LigneExpliquee[]): void {
  if (!Array.isArray(lignes)) return;
  for (const ligne of lignes) {
    if (!ligne || typeof ligne !== 'object') continue;
    const candidate = ligne as LignePossible;
    const explication = texteInfobulle(candidate);
    if (!explication) continue;
    const libelle =
      typeof candidate.libelle === 'string' && candidate.libelle.trim()
        ? candidate.libelle
        : 'Ligne du bulletin';
    acc.push({ libelle, explication });
  }
}

export function lignesAvecExplication(
  data: Record<string, unknown> | null | undefined
): LigneExpliquee[] {
  if (!data || typeof data !== 'object') return [];
  const acc: LigneExpliquee[] = [];
  collecter(data.calcul_du_brut, acc);
  collecter(data.details_conges, acc);
  collecter(data.details_absences, acc);
  const structure = data.structure_cotisations;
  if (structure && typeof structure === 'object') {
    collecter((structure as Record<string, unknown>).bloc_allegements, acc);
  }
  const officielles = data.cotisations_officielles;
  if (Array.isArray(officielles)) {
    for (const rubrique of officielles) {
      if (rubrique && typeof rubrique === 'object') {
        collecter((rubrique as { lignes?: unknown }).lignes, acc);
      }
    }
  }
  const vus = new Set<string>();
  return acc.filter((ligne) => {
    const cle = `${ligne.libelle}|${ligne.explication}`;
    if (vus.has(cle)) return false;
    vus.add(cle);
    return true;
  });
}
