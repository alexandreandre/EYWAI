/**
 * Texte du manuel opérateur (mode paie). Pas de nom de salarié, pas de
 * société réelle : Alexandre relit avant mise en ligne.
 */

export type EtapeManuel = {
  titre: string;
  paragraphes: string[];
};

export type PiegeManuel = {
  titre: string;
  quoiFaire: string;
};

export const SECTIONS_MANUEL: { id: string; titre: string; intro?: string }[] = [
  {
    id: 'etapes',
    titre: 'La paie du mois, étape par étape',
    intro: 'Faites-les dans l’ordre. La liste de contrôle de la page Paie dit ce qui est déjà prouvé.',
  },
  {
    id: 'pieges',
    titre: 'Pièges déjà vus, et quoi faire',
    intro: 'Si l’écran dit une chose et que vous en voyez une autre, croyez l’écran à jour — ou rechargez.',
  },
];

export const ETAPES_MANUEL: EtapeManuel[] = [
  {
    titre: '1. Importer les pointages',
    paragraphes: [
      'Ouvrez Calendrier, puis importez le fichier de pointages du mois. Le récapitulatif liste les salariés reconnus et ceux qu’il reste à associer.',
      'Une ligne de pointage qui tombe un jour d’arrêt n’est plus écrite en silence : elle apparaît dans le récapitulatif. Traitez-la avant de continuer.',
    ],
  },
  {
    titre: '2. Compléter le calendrier',
    paragraphes: [
      'Chaque jour de la fenêtre des variables doit avoir des heures prévues et des heures réelles. Un calendrier incomplet bloque la génération, sauf si vous forcez après un message clair.',
      'La liste de contrôle de la page Paie coche cette étape seulement quand plus aucun jour n’est à saisir.',
    ],
  },
  {
    titre: '3. Saisir les absences',
    paragraphes: [
      'Ouvrez Congés & absences et saisissez les arrêts, congés et RTT du mois. Un arrêt validé met le calendrier à jour.',
      'Le logiciel ne peut pas prouver que toutes les absences sont là. Cette étape reste à confirmer par vous, chaque mois.',
    ],
  },
  {
    titre: '4. Générer les bulletins',
    paragraphes: [
      'Sur la page Paie, onglet Par mois, générez le mois. Si un calendrier est incomplet ou si des heures sont saisies un jour d’arrêt, la génération s’arrête et dit pourquoi. Rien n’est calculé en silence.',
      'Après une génération, les listes se rechargent. Le PDF affiché est celui du dernier calcul.',
    ],
  },
  {
    titre: '5. Vérifier les bulletins',
    paragraphes: [
      'Ouvrez chaque bulletin qui sort de l’ordinaire : heures sup, absence, net négatif, premier ou dernier mois. Un astérisque sur une ligne explique le calcul.',
      'Comparez aussi avec le mois dernier, en bas du bulletin. Si un montant change sans raison, ne validez pas.',
    ],
  },
  {
    titre: '6. Recalculer ce qui a changé',
    paragraphes: [
      'Si vous corrigez après la génération ce que le bulletin lit (planning, absence, variables, fiche, mutuelle, compteur de congés, départ, salaire…), le bulletin concerné porte « À recalculer » et dit ce qui a changé. Un bouton « Recalculer tout ce qui a changé » relance seulement ceux-là.',
      'Une fiche modifiée ne remet en cause que les bulletins non validés du contrat en cours : un bulletin validé reste tel quel, celui d’un ancien contrat n’est jamais signalé.',
      'Un bulletin d’avant cette marque, ou repris de l’ancien logiciel, n’est pas « à recalculer ». Seul un vrai changement depuis le calcul l’est.',
    ],
  },
  {
    titre: '7. Valider',
    paragraphes: [
      'Ne validez un bulletin que s’il n’est pas à recalculer. Le message dit alors pourquoi il faut d’abord relancer le calcul.',
      'Valider envoie le bulletin vers la suite (PDF, documents). Ce n’est pas la même action que générer.',
    ],
  },
  {
    titre: '8. Traiter les sorties',
    paragraphes: [
      'Un salarié dont le contrat finit dans le mois doit avoir un dossier de départ. Sans ce dossier, il n’y a pas de bulletin de sortie.',
      'Sur l’onglet Par mois, un bandeau dit de créer le départ, puis de générer le bulletin de sortie. Les documents (solde de tout compte, attestation) restent grisés tant que ce bulletin n’existe pas.',
    ],
  },
];

export const PIEGES_MANUEL: PiegeManuel[] = [
  {
    titre: 'Des heures sont saisies un jour d’arrêt',
    quoiFaire:
      'Le calendrier montre les jours en conflit. Choisissez : le salarié était en arrêt (effacer ces heures) ou il a travaillé (modifier l’arrêt). Sans ce clic, rien ne se corrige. Ensuite le bulletin passe « à recalculer ».',
  },
  {
    titre: 'L’écran montre un bulletin périmé',
    quoiFaire:
      'Rechargez la page. Après une génération, une régénération ou une suppression, les listes viennent du serveur. Si le bulletin n’existe plus, l’écran dit qu’il a été remplacé et propose de revenir à la liste — pas une erreur brute.',
  },
  {
    titre: 'Le bulletin est à recalculer',
    quoiFaire:
      'Une donnée que le bulletin lit a changé depuis le calcul ; le bandeau dit laquelle (planning, fiche, mutuelle, congés…). Cliquez « Recalculer » (ou « Recalculer tout ce qui a changé » sur la page du mois). Un message résume les écarts (heures sup, brut, net). Ne validez pas avant.',
  },
  {
    titre: 'Le net à payer est négatif',
    quoiFaire:
      'C’est possible, par exemple un mois entier d’arrêt sans maintien, avec les indemnités versées ailleurs. Le net n’est pas ramené à zéro. Le mois suivant, une saisie « Report NAP négatif » reprend la somme. Créez-la depuis le bandeau du bulletin.',
  },
  {
    titre: 'Un départ sans bulletin de sortie',
    quoiFaire:
      'Créer le départ ne génère pas le bulletin tout seul. Après le dossier, générez le bulletin de sortie (indemnité de congés comprise). Tant qu’il manque, les documents de sortie restent grisés.',
  },
  {
    titre: 'Le RIB n’est pas encore là',
    quoiFaire:
      'La fiche s’enregistre sans RIB. Elle porte « RIB à compléter » dans la liste. Complétez-le dans la fiche avant de valider la paie. Le virement ne peut pas partir sans ces coordonnées.',
  },
];

export function titresDesEtapes(): string[] {
  return ETAPES_MANUEL.map((e) => e.titre);
}

export function TEXTE_MANUEL(): string {
  const etapes = ETAPES_MANUEL.flatMap((e) => [e.titre, ...e.paragraphes]);
  const pieges = PIEGES_MANUEL.flatMap((p) => [p.titre, p.quoiFaire]);
  const sections = SECTIONS_MANUEL.flatMap((s) => [s.titre, s.intro ?? '']);
  return [...sections, ...etapes, ...pieges].join('\n');
}
