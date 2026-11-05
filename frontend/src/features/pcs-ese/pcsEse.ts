/**
 * Le code PCS-ESE : la liste officielle (table DSN PCSESE, 430 codes) et ce que Martine propose.
 * Le serveur trouve le code (`/api/pcs-ese/proposition`) ; l'écran l'affiche et le laisse changer.
 */

export interface RubriquePcs {
  code: string;
  libelle: string;
  /** Professions typiques et assimilées de l'Insee. */
  metiers: string[];
  /** Emploi exigeant des conditions d'aptitude particulières (déduction OETH). */
  ecap: boolean;
  /** Code réservé aux employeurs publics. */
  public: boolean;
}

export interface CandidatPcs {
  code: string;
  libelle: string;
  raison: string;
  ecap: boolean;
}

export interface PropositionPcs {
  code: string | null;
  sur: boolean;
  raison: string;
  regle: 'a' | 'b' | 'c' | null;
  nb_collegues: number;
  candidats: CandidatPcs[];
  ecap: boolean;
}

/** L'ancien code noté par Martine quand le code a changé (bloc DSN S21.G00.41). */
export interface ChangementPcs {
  ancien: string;
  date: string;
}

export const MENTION_ECAP = 'Code ECAP : il réduit la contribution OETH.';

function simple(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

export interface LigneTrouvee {
  rubrique: RubriquePcs;
  /** Le métier Insee qui a fait trouver la ligne, quand ce n'est ni le code ni le libellé. */
  metier: string | null;
}

/** Les lignes qui répondent à la recherche : début de code, puis libellé, puis métier Insee. */
export function filtrerRubriques(rubriques: RubriquePcs[], recherche: string): LigneTrouvee[] {
  const q = simple(recherche);
  if (!q) return rubriques.map((rubrique) => ({ rubrique, metier: null }));
  const rangees: Array<{ rang: number; ligne: LigneTrouvee }> = [];
  for (const rubrique of rubriques) {
    if (rubrique.code.toLowerCase().startsWith(q)) {
      rangees.push({ rang: 0, ligne: { rubrique, metier: null } });
    } else if (simple(rubrique.libelle).includes(q)) {
      rangees.push({ rang: 1, ligne: { rubrique, metier: null } });
    } else {
      const metier = rubrique.metiers.find((m) => simple(m).includes(q));
      if (metier) rangees.push({ rang: 2, ligne: { rubrique, metier } });
    }
  }
  return rangees.sort((a, b) => a.rang - b.rang).map((r) => r.ligne);
}

/** Martine pré-remplit seulement un code vide ou « 9999 », et seulement quand elle est sûre. */
export function doitPreRemplir(codeActuel: string, proposition: PropositionPcs | undefined): boolean {
  if (!proposition?.sur || !proposition.code) return false;
  const actuel = codeActuel.trim();
  return (actuel === '' || actuel === '9999') && proposition.code !== actuel;
}

export function texteChangement(changement: ChangementPcs | null | undefined, codeActuel: string): string | null {
  if (!changement?.ancien || !changement.date || changement.ancien === codeActuel.trim()) return null;
  const [annee, mois, jour] = changement.date.slice(0, 10).split('-');
  return `Code changé le ${jour}/${mois}/${annee} (avant : ${changement.ancien}). Martine déclare ce changement dans la DSN.`;
}

export function libelleCode(rubriques: RubriquePcs[], code: string): string {
  const rubrique = rubriques.find((r) => r.code === code);
  return rubrique ? `${rubrique.code} — ${rubrique.libelle}` : code;
}
