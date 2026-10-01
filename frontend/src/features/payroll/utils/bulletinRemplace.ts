/**
 * Bulletin qui n'existe plus, à l'écran de correction : la logique, sans React.
 *
 * Régénérer garde l'identifiant du bulletin ; le supprimer puis le générer à
 * nouveau en donne un autre. Le lien vers l'ancien répond alors 404 : l'écran
 * le dit et renvoie vers la liste, rechargée. Seul un 404 veut dire
 * « remplacé » : une coupure réseau, un refus de droits ou une panne du
 * serveur gardent un message qui dit quoi faire.
 */

import axios from 'axios';

import { extractDetail, getApiErrorStatus, sanitizeBackendMessage } from '@/lib/errorMessages';

export type MessageEcran = { title: string; description: string };

export const MESSAGE_BULLETIN_REMPLACE = 'Ce bulletin a été remplacé : rechargement…';

export function estBulletinIntrouvable(error: unknown): boolean {
  return getApiErrorStatus(error) === 404;
}

export function messageBulletinRemplace(): MessageEcran {
  return {
    title: MESSAGE_BULLETIN_REMPLACE,
    description:
      'Il a été supprimé ou généré à nouveau depuis un autre écran. Rouvrez-le depuis la liste des bulletins.',
  };
}

export function messageBulletinNonCharge(error: unknown): MessageEcran {
  const title = 'Bulletin non chargé';
  if (axios.isAxiosError(error) && !error.response) {
    return {
      title,
      description: 'Connexion impossible. Vérifiez votre connexion internet, puis rechargez la page.',
    };
  }
  const status = getApiErrorStatus(error);
  if (status === 401) {
    return { title, description: 'Votre session a expiré. Reconnectez-vous, puis rouvrez le bulletin.' };
  }
  if (status === 403) {
    return {
      title,
      description:
        'Vous n’avez pas accès à ce bulletin. Vérifiez la société active, ou demandez l’accès à un administrateur.',
    };
  }
  if (status !== undefined && status >= 500) {
    return {
      title,
      description: 'Le service rencontre un problème. Rechargez la page dans quelques instants.',
    };
  }
  const detail = sanitizeBackendMessage(extractDetail(error));
  return {
    title,
    description: `${detail ? `${detail} ` : ''}Rechargez la page, ou rouvrez le bulletin depuis la liste des bulletins.`,
  };
}

/** Page de paie, sur le salarié et le mois du bulletin quand on les connaît. */
export function lienListeDesBulletins(
  bulletin: { employee_id: string; year: number; month: number } | null | undefined
): string {
  if (!bulletin) return '/payroll';
  const params = new URLSearchParams({
    employee: bulletin.employee_id,
    month: `${bulletin.year}-${String(bulletin.month).padStart(2, '0')}`,
  });
  return `/payroll?${params.toString()}`;
}
