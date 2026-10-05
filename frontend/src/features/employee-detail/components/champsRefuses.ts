/**
 * Les champs refusés par le formulaire de la fiche, en clair.
 *
 * Le formulaire complet est validé même quand certaines sections ne sont pas
 * affichées (mode paie) : sans ce résumé, un refus sur un champ masqué laissait
 * la fenêtre ouverte sans aucun message.
 */
const NOMS: Array<[RegExp, string]> = [
  [/^specificites_paie\.prevoyance/, 'Prévoyance'],
  [/^specificites_paie\.mutuelle/, 'Mutuelle'],
  [/^specificites_paie\.titres_restaurant/, 'Titres-restaurant'],
  [/^specificites_paie\.transport/, 'Transport'],
  [/^specificites_paie\.deplacement_astreinte/, 'Déplacements d’astreinte'],
  [/^specificites_paie/, 'Paie sociale'],
  [/^residence_permit|^is_subject_to_residence_permit/, 'Titre de séjour'],
  [/^classification_conventionnelle|^collective_agreement_id/, 'Classification conventionnelle'],
  [/^code_pcs/, 'Code PCS-ESE'],
  [/^contract_end_date/, 'Date de fin de contrat'],
  [/^adresse/, 'Adresse'],
  [/^coordonnees_bancaires/, 'RIB'],
  [/^nir/, 'N° de sécurité sociale'],
  [/^date_naissance/, 'Date de naissance'],
  [/^email/, 'E-mail'],
  [/^team_id/, 'Équipe'],
  [/^salaire_de_base/, 'Salaire de base'],
];

function chemins(erreurs: unknown, prefixe = ''): Array<{ chemin: string; message: string }> {
  if (!erreurs || typeof erreurs !== 'object') return [];
  const e = erreurs as Record<string, unknown>;
  if (typeof e.message === 'string' && e.message) return [{ chemin: prefixe, message: e.message }];
  return Object.keys(e)
    .filter((k) => k !== 'ref' && k !== 'type')
    .flatMap((k) => chemins(e[k], prefixe ? `${prefixe}.${k}` : k));
}

export function champsRefuses(erreurs: unknown): string[] {
  const vus = new Set<string>();
  for (const { chemin, message } of chemins(erreurs)) {
    const nom = NOMS.find(([motif]) => motif.test(chemin))?.[1] ?? chemin;
    vus.add(`${nom} : ${message}`);
  }
  return [...vus];
}
