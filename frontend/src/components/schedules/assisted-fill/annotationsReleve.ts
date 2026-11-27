/**
 * Annotations d'un relevé de pointage (MBC, Cegid hebdomadaire) : ce que la
 * gestionnaire a écrit à la main sur le relevé (« CP », « absent 7,5 »,
 * « PANIERS 3 ») et les badgeages incomplets. Martine retient les heures du
 * badge ; le serveur le dit en une phrase par semaine
 * (`cegid_weekly.describe_day_notes`). Elsa (26/11) : la phrase coupée était
 * illisible. On la relit jour par jour, regroupée par salarié.
 */

export interface JourAnnote {
  /** « lun 21/09 » ; vide si le message n'a pas pu être lu. */
  jour: string;
  annotation: string;
}

export interface AnnotationsSalarie {
  cle: string;
  nom: string;
  jours: JourAnnote[];
}

const ENTETE = /^Relevé à relire\s*—[^:]*:\s*/;
const JOUR = /^((?:lun|mar|mer|jeu|ven|sam|dim) \d{2}\/\d{2})\s+(.+)$/;

export function estAnnotationReleve(message: string): boolean {
  return message.trim().startsWith('Relevé à relire');
}

export function lireAnnotationsReleve(message: string): JourAnnote[] {
  const texte = message.trim();
  if (!ENTETE.test(texte)) return [{ jour: '', annotation: texte }];
  const corps = texte.replace(ENTETE, '').replace(/\.\s*$/, '');
  const jours: JourAnnote[] = [];
  for (const morceau of corps.split(/\s;\s/).map((m) => m.trim()).filter(Boolean)) {
    const m = JOUR.exec(morceau);
    if (m) {
      jours.push({ jour: m[1], annotation: m[2].trim() });
    } else if (jours.length > 0) {
      // « ; » écrit dans l'annotation même : le morceau reste avec son jour.
      const precedent = jours[jours.length - 1];
      precedent.annotation = `${precedent.annotation} ; ${morceau}`;
    } else {
      jours.push({ jour: '', annotation: morceau });
    }
  }
  return jours.length ? jours : [{ jour: '', annotation: texte }];
}

/** Les salariés dont le relevé porte des annotations, chacun avec ses jours. */
export function annotationsDesLignes(
  lignes: readonly { cle: string; nom: string; warnings: readonly string[] }[],
): AnnotationsSalarie[] {
  const groupes: AnnotationsSalarie[] = [];
  for (const ligne of lignes) {
    const vus = new Set<string>();
    const jours: JourAnnote[] = [];
    for (const message of ligne.warnings) {
      if (!estAnnotationReleve(message)) continue;
      for (const jour of lireAnnotationsReleve(message)) {
        const cle = `${jour.jour}|${jour.annotation}`;
        if (vus.has(cle)) continue;
        vus.add(cle);
        jours.push(jour);
      }
    }
    if (jours.length) groupes.push({ cle: ligne.cle, nom: ligne.nom, jours });
  }
  return groupes;
}

export function phraseAnnotations(jours: number, salaries: number): string {
  const j = `${jours} jour${jours > 1 ? 's' : ''} annoté${jours > 1 ? 's' : ''} sur le relevé`;
  return salaries > 1 ? `${j}, pour ${salaries} salariés` : j;
}
