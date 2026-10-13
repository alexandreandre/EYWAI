/** Statut du titre de séjour déjà calculé par le serveur, pour la fiche. */

export interface TitreSejourConnu {
  is_subject_to_residence_permit?: boolean | null;
  residence_permit_status?: 'valid' | 'to_renew' | 'expired' | 'to_complete' | null;
  residence_permit_expiry_date?: string | null;
}

function dateFr(iso: string | null | undefined): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '');
  if (!match) return null;
  return `${match[3]}/${match[2]}/${match[1]}`;
}

export function libelleStatutTitre(data: TitreSejourConnu): string | null {
  if (!data.is_subject_to_residence_permit) return null;
  const date = dateFr(data.residence_permit_expiry_date);
  switch (data.residence_permit_status) {
    case 'to_complete':
      return 'À compléter';
    case 'to_renew':
      return 'À renouveler';
    case 'valid':
      return date ? `Valide jusqu'au ${date}` : 'Valide';
    case 'expired':
      return date ? `Expiré depuis le ${date}` : 'Expiré';
    default:
      return null;
  }
}
