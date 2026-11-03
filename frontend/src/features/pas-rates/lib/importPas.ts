// Textes de la fenêtre « Mettre à jour les taux » (import des taux d'impôt).
// La DSN du mois vient en premier, comme dans la vidéo B.5 : la RH ne peut pas
// télécharger le compte rendu métier, net-entreprises l'affiche seulement à l'écran.

import type { PasSource } from '@/api/pasRates';

export const INTRO_IMPORT_PAS =
  "Déposez la DSN du mois : Martine y lit le taux d'impôt de chaque salarié. Rien n'est écrit tant que vous n'avez pas confirmé.";

export const SOURCES_IMPORT_PAS: { value: PasSource; label: string; aide: string }[] = [
  {
    value: 'dsn',
    label: 'DSN du mois',
    aide: 'Le fichier de la DSN mensuelle, tel que votre logiciel de paie l’a déposé.',
  },
  {
    value: 'crm',
    label: 'Compte rendu métier',
    aide: "Seulement si vous l'avez en fichier : net-entreprises l'affiche à l'écran, sans le proposer en téléchargement.",
  },
];
