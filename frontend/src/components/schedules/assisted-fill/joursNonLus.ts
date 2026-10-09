/**
 * Jours qu'une feuille PDF ou photo n'a pas permis de lire (couverture 3/5).
 * Ils ne sont jamais écrits (le serveur ne les transforme plus en 0 h) et
 * restent à saisir au calendrier : l'écran le dit avant, le résultat après.
 */

export interface LigneDecompte {
  nom: string;
  joursAttendus: number | null;
  joursLus: number | null;
  enregistrable: boolean;
}

export interface JoursNonLusSalarie {
  nom: string;
  jours: number;
}

export function joursNonLus(rows: LigneDecompte[]): JoursNonLusSalarie[] {
  return rows
    .filter((r) => r.enregistrable && r.joursAttendus != null && r.joursLus != null)
    .map((r) => ({ nom: r.nom, jours: (r.joursAttendus as number) - (r.joursLus as number) }))
    .filter((r) => r.jours > 0);
}

const jours = (n: number) => `${n} ${n > 1 ? 'jours' : 'jour'}`;
const detail = (l: JoursNonLusSalarie[]) => l.map((x) => `${x.nom} (${jours(x.jours)})`).join(', ');

export function phraseJoursNonLus(l: JoursNonLusSalarie[]): string | null {
  if (l.length === 0) return null;
  const total = l.reduce((n, x) => n + x.jours, 0);
  const sujet = total > 1 ? `${total} jours non lus ne seront pas écrits` : '1 jour non lu ne sera pas écrit';
  return `${sujet} et restent à saisir au calendrier : ${detail(l)}.`;
}

export function suiteResultatJoursNonLus(l: JoursNonLusSalarie[]): string {
  return l.length === 0 ? '' : ` Jours non lus, à saisir au calendrier : ${detail(l)}.`;
}
