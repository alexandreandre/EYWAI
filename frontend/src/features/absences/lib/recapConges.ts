/**
 * Récapitulatif des congés de la société (lot L21, demande du 27/11/2026) :
 * logique d'écran pure. La période par défaut est le mois de paie ; le
 * serveur refuse les mêmes périodes, l'écran le dit avant d'envoyer.
 */
import type {
  PeriodeRecap,
  RecapConges,
  RecapCongesColonne,
  RecapCongesSalarie,
} from '@/api/absences';
import type { MoisDePaie } from '@/features/payroll/utils/moisDePaie';

export const JOURS_MAXIMUM_RECAP = 366;

const DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

const deux = (n: number) => String(n).padStart(2, '0');

/** Du 1er au dernier jour du mois de paie. */
export function periodeDuMoisDePaie(mois: MoisDePaie): PeriodeRecap {
  const dernier = new Date(Date.UTC(mois.year, mois.month, 0)).getUTCDate();
  return {
    debut: `${mois.year}-${deux(mois.month)}-01`,
    fin: `${mois.year}-${deux(mois.month)}-${deux(dernier)}`,
  };
}

function jourUtc(valeur: string): number | null {
  const m = DATE.exec(valeur);
  if (!m) return null;
  const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const d = new Date(t);
  return d.getUTCDate() === Number(m[3]) && d.getUTCMonth() === Number(m[2]) - 1 ? t : null;
}

/** Pourquoi la période est refusée, ou null si elle convient. */
export function messagePeriodeRecap({ debut, fin }: PeriodeRecap): string | null {
  const d0 = jourUtc(debut);
  const d1 = jourUtc(fin);
  if (d0 === null) return 'Choisissez le premier jour de la période.';
  if (d1 === null) return 'Choisissez le dernier jour de la période.';
  if (d1 < d0) return 'Le premier jour est après le dernier.';
  if ((d1 - d0) / 86_400_000 >= JOURS_MAXIMUM_RECAP) return 'Période trop longue : un an au plus.';
  return null;
}

/**
 * La période à charger au clic sur « Afficher » : la saisie si elle est
 * acceptée et diffère de la période affichée, sinon null (rien à envoyer).
 */
export function periodeAAfficher(saisie: PeriodeRecap, affichee: PeriodeRecap): PeriodeRecap | null {
  if (messagePeriodeRecap(saisie)) return null;
  if (saisie.debut === affichee.debut && saisie.fin === affichee.fin) return null;
  return { debut: saisie.debut, fin: saisie.fin };
}

export type EtatRecap = 'societe' | 'periode' | 'chargement' | 'erreur' | 'vide' | 'pret';

/** Ce que l'écran doit dire : jamais d'état muet. */
export function etatDuRecap(args: {
  sansSociete: boolean;
  periodeRefusee: boolean;
  chargement: boolean;
  erreur: boolean;
  recap: RecapConges | undefined;
}): EtatRecap {
  if (args.sansSociete) return 'societe';
  if (args.periodeRefusee) return 'periode';
  if (args.chargement) return 'chargement';
  if (args.erreur || !args.recap) return 'erreur';
  return args.recap.aucun_jour ? 'vide' : 'pret';
}

/**
 * Les colonnes montrées à l'écran : celles qui ont au moins un jour sur la
 * période (l'Excel les garde toutes). Les autres sont nommées sous le tableau.
 */
export function colonnesDuTableau(recap: RecapConges): {
  affichees: RecapCongesColonne[];
  masquees: RecapCongesColonne[];
} {
  const affichees: RecapCongesColonne[] = [];
  const masquees: RecapCongesColonne[] = [];
  for (const colonne of recap.colonnes) {
    ((recap.totaux[colonne.cle] ?? 0) > 0 ? affichees : masquees).push(colonne);
  }
  return { affichees, masquees };
}

const normaliser = (v: string) =>
  v
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');

/** Recherche par nom, prénom ou matricule, sans tenir compte des accents. */
export function filtrerSalaries(
  salaries: RecapCongesSalarie[],
  recherche: string,
): RecapCongesSalarie[] {
  const terme = normaliser(recherche.trim());
  if (!terme) return salaries;
  return salaries.filter((s) =>
    normaliser(`${s.prenom} ${s.nom} ${s.matricule ?? ''}`).includes(terme),
  );
}

/** Jours à la française : « 2,5 », « 0 » pour aucun jour. */
export function formatJours(valeur: number | null | undefined): string {
  if (valeur === null || valeur === undefined) return 'non calculé';
  return valeur.toLocaleString('fr-FR', { maximumFractionDigits: 2 });
}

/** « du 01/11/2026 au 30/11/2026 » */
export function libellePeriode({ debut, fin }: PeriodeRecap): string {
  const fr = (iso: string) => iso.split('-').reverse().join('/');
  return `du ${fr(debut)} au ${fr(fin)}`;
}
