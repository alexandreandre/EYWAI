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
  /** Le code des collègues au même poste (proposition de Martine) : la raison, sinon null. */
  propose?: string | null;
}

/** Un code des collègues au même poste, que Martine propose. */
export interface CodePropose {
  code: string;
  raison: string;
}

const MOTS_VIDES = new Set(['de', 'du', 'des', 'd', 'la', 'le', 'les', 'l', 'et', 'en', 'a', 'au', 'aux', 'sur', 'pour']);

function mots(texte: string): string[] {
  return simple(texte)
    .split(/[^a-z0-9]+/)
    .filter((m) => m && !MOTS_VIDES.has(m));
}

/**
 * Un mot cherché retrouve un mot du texte : début du mot (« soud » → « soudeur »), ou même racine
 * de cinq lettres (« industriel » → « industrie », « peinture » → « peintre »).
 */
function memeMot(cherche: string, mot: string): boolean {
  if (mot.startsWith(cherche)) return true;
  return cherche.length >= 5 && mot.length >= 5 && cherche.slice(0, 5) === mot.slice(0, 5);
}

/** Combien des mots cherchés le texte contient. */
function motsTrouves(cherches: string[], texte: string): number {
  const dedans = mots(texte);
  return cherches.filter((c) => dedans.some((m) => memeMot(c, m))).length;
}

/**
 * Les lignes qui répondent à la recherche : début de code, puis libellé, puis métier Insee. Un
 * intitulé de poste (« peintre industriel ») se cherche mot à mot : d'abord les lignes qui ont
 * tous les mots, sinon celles qui en ont le plus. Le code des collègues au même poste (proposé
 * par Martine) passe en tête sans recherche, ou quand on cherche un mot du poste : l'Insee ne
 * range pas toujours le métier là où la société le déclare (« préparateur peintre » en 674a).
 */
export function filtrerRubriques(
  rubriques: RubriquePcs[],
  recherche: string,
  options: { poste?: string; proposes?: CodePropose[] } = {},
): LigneTrouvee[] {
  const q = simple(recherche);
  const cherches = mots(recherche);
  const motsDuPoste = mots(options.poste ?? '');
  const proposes = new Map((options.proposes ?? []).map((p) => [p.code, p.raison]));
  const enTete =
    proposes.size > 0 &&
    (!q || (cherches.length > 0 && cherches.every((c) => motsDuPoste.some((m) => memeMot(c, m)))));

  const rangees: Array<{ rang: number; score: number; ligne: LigneTrouvee }> = [];
  for (const rubrique of rubriques) {
    if (enTete && proposes.has(rubrique.code)) {
      rangees.push({ rang: -1, score: 0, ligne: { rubrique, metier: null, propose: proposes.get(rubrique.code) } });
      continue;
    }
    if (!q) {
      rangees.push({ rang: 0, score: 0, ligne: { rubrique, metier: null, propose: null } });
      continue;
    }
    if (rubrique.code.toLowerCase().startsWith(q)) {
      rangees.push({ rang: 0, score: 0, ligne: { rubrique, metier: null, propose: null } });
      continue;
    }
    const libelle = simple(rubrique.libelle).includes(q) ? cherches.length || 1 : motsTrouves(cherches, rubrique.libelle);
    let metier: string | null = null;
    let parMetier = 0;
    for (const m of rubrique.metiers) {
      const n = simple(m).includes(q) ? cherches.length || 1 : motsTrouves(cherches, m);
      if (n > parMetier) {
        parMetier = n;
        metier = m;
      }
    }
    const tous = Math.max(cherches.length, 1);
    if (libelle >= tous) {
      rangees.push({ rang: 1, score: libelle, ligne: { rubrique, metier: null, propose: null } });
    } else if (parMetier >= tous) {
      rangees.push({ rang: 2, score: parMetier, ligne: { rubrique, metier, propose: null } });
    } else if (Math.max(libelle, parMetier) > 0) {
      const parLibelle = libelle >= parMetier;
      rangees.push({
        rang: 3,
        score: Math.max(libelle, parMetier),
        ligne: { rubrique, metier: parLibelle ? null : metier, propose: null },
      });
    }
  }
  const complets = rangees.filter((r) => r.rang < 3);
  // Une ligne qui n'a qu'une partie des mots ne sert que si aucune ne les a tous.
  const gardees = complets.some((r) => r.rang >= 0 || !q) ? complets : rangees;
  return gardees
    .map((r, i) => ({ ...r, i }))
    .sort((a, b) => a.rang - b.rang || b.score - a.score || a.i - b.i)
    .map((r) => r.ligne);
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
