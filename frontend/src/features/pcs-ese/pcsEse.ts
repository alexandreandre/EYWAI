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

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];

export function texteChangement(changement: ChangementPcs | null | undefined, codeActuel: string): string | null {
  if (!changement?.ancien || !changement.date || changement.ancien === codeActuel.trim()) return null;
  const [annee, mois, jour] = changement.date.slice(0, 10).split('-');
  return (
    `Code changé le ${jour}/${mois}/${annee} (avant : ${changement.ancien}) : ` +
    `Martine déclare l’ancien code dans la DSN de ${MOIS[Number(mois) - 1]} ${annee}.`
  );
}

/** Le code que Martine a mis elle-même, et la valeur qu'il a remplacée. */
export interface PreRemplissage {
  code: string;
  avant: string;
}

/**
 * Ce que le champ doit retenir entre deux affichages : gardé par le formulaire parent quand le
 * champ peut être démonté (onglet inactif de la création), sinon par le champ lui-même.
 */
export interface SuiviPcs {
  prerempli: PreRemplissage | null;
  rhAChoisi: boolean;
}

export const SUIVI_PCS_INITIAL: SuiviPcs = { prerempli: null, rhAChoisi: false };

const codeVide = (code: string) => code.trim() === '' || code.trim() === '9999';

/**
 * Ce que Martine fait du champ quand la proposition ou la valeur change. Elle remplit un code
 * vide ou « 9999 » quand elle est sûre ; elle remplace ou retire son propre code si la
 * proposition change (le statut passe à cadre, par exemple) ; elle remplit de nouveau après une
 * remise à zéro du formulaire ; elle ne touche jamais à un code choisi par la RH.
 */
export function prochainEtat(p: {
  valeur: string;
  prerempli: PreRemplissage | null;
  rhAChoisi: boolean;
  proposition: PropositionPcs | undefined;
}): { code: string; prerempli: PreRemplissage | null } | null {
  const { valeur, rhAChoisi, proposition } = p;
  if (rhAChoisi || !proposition) return null;
  let prerempli = p.prerempli;
  if (prerempli && valeur !== prerempli.code) {
    if (!codeVide(valeur)) return null;
    prerempli = null; // le formulaire a été remis à zéro
  }
  if (prerempli) {
    if (proposition.sur && proposition.code && proposition.code !== valeur) {
      return { code: proposition.code, prerempli: { code: proposition.code, avant: prerempli.avant } };
    }
    if (!proposition.sur) return { code: prerempli.avant, prerempli: null };
    return null;
  }
  if (doitPreRemplir(valeur, proposition) && proposition.code) {
    return { code: proposition.code, prerempli: { code: proposition.code, avant: valeur } };
  }
  return null;
}

export function libelleCode(rubriques: RubriquePcs[], code: string): string {
  const rubrique = rubriques.find((r) => r.code === code);
  return rubrique ? `${rubrique.code} — ${rubrique.libelle}` : code;
}

/** Le changement de code noté par le serveur dans la classification de la fiche. */
export function changementPcsDe(classification: unknown): ChangementPcs | null {
  if (!classification || typeof classification !== 'object') return null;
  const c = (classification as Record<string, unknown>).pcs_changement;
  if (!c || typeof c !== 'object') return null;
  const { ancien, date } = c as Record<string, unknown>;
  return typeof ancien === 'string' && typeof date === 'string' ? { ancien, date } : null;
}
