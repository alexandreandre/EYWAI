import type { DecompteEnMasse, RaisonLaisse, SalarieEnMasse } from '@/api/activitePartielleEnMasse';
import { dateCourte } from './joursEnMasse';
import { accord, pluriel } from './pluriel';

/** Ordre d'affichage des raisons pour lesquelles un jour reste tel quel. */
const ORDRE: RaisonLaisse[] = [
  'absence',
  'repos',
  'bulletin_valide',
  'hors_contrat',
  'deja_ap',
  'heures_saisies',
  'echec',
];

const LIBELLES: Record<RaisonLaisse, string> = {
  absence: "jour d'arrêt, de congé ou d'une autre absence",
  repos: 'repos, week-end ou jour férié',
  bulletin_valide: 'bulletin du mois déjà validé',
  hors_contrat: "hors contrat (avant l'entrée ou après la sortie)",
  deja_ap: 'déjà en activité partielle',
  heures_saisies: 'des heures faites sont déjà saisies ce jour-là',
  echec: 'calendrier non enregistré (erreur)',
};

export function libelleRaison(raison: RaisonLaisse, d?: DecompteEnMasse): string {
  return d?.libelles_raisons?.[raison] ?? LIBELLES[raison] ?? raison;
}

/** La phrase principale : ce qui passe (ou est passé) et ce qui reste. */
export function phraseDuDecompte(d: DecompteEnMasse): string {
  const passes = pluriel(d.total_passes, 'jour');
  const laisses = pluriel(d.total_laisses, 'jour');
  if (d.enregistre) {
    return d.total_laisses > 0
      ? `${passes} ${accord(d.total_passes, 'passé')} en activité partielle, ${laisses} ${accord(d.total_laisses, 'laissé')} tel${d.total_laisses > 1 ? 's' : ''} quel${d.total_laisses > 1 ? 's' : ''}.`
      : `${passes} ${accord(d.total_passes, 'passé')} en activité partielle.`;
  }
  if (d.total_passes === 0) {
    return `Rien à poser : ${d.total_laisses > 1 ? `les ${laisses} choisis restent` : 'le jour choisi reste'} tel${d.total_laisses > 1 ? 's' : ''} quel${d.total_laisses > 1 ? 's' : ''}.`;
  }
  return d.total_laisses > 0
    ? `${passes} ${d.total_passes > 1 ? 'passeront' : 'passera'} en activité partielle, ${laisses} ${d.total_laisses > 1 ? 'resteront' : 'restera'} tel${d.total_laisses > 1 ? 's' : ''} quel${d.total_laisses > 1 ? 's' : ''}.`
    : `${passes} ${d.total_passes > 1 ? 'passeront' : 'passera'} en activité partielle.`;
}

/** Une ligne par raison : « 3 jours : repos, week-end ou jour férié ». */
export function lignesDesRaisons(d: DecompteEnMasse): string[] {
  return ORDRE.filter((r) => (d.laisses_par_raison[r] ?? 0) > 0).map(
    (r) => `${pluriel(d.laisses_par_raison[r] ?? 0, 'jour')} : ${libelleRaison(r, d)}`,
  );
}

/** Le détail d'un salarié : ses jours passés et ses jours laissés avec leur raison. */
export function detailDuSalarie(s: SalarieEnMasse, d: DecompteEnMasse): string {
  const morceaux: string[] = [];
  if (s.passes.length > 0) {
    morceaux.push(
      `${pluriel(s.passes.length, 'jour')} en activité partielle${s.forfait_jours ? ', au forfait jours' : ''}`,
    );
  }
  for (const r of ORDRE) {
    const jours = s.laisses.filter((l) => l.raison === r).map((l) => dateCourte(l.date));
    if (jours.length > 0) morceaux.push(`${libelleRaison(r, d)} : ${jours.join(', ')}`);
  }
  return morceaux.join(' ; ') || 'aucun jour choisi';
}
