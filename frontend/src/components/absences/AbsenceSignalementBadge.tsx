import { Link } from 'react-router-dom';
import type { SignalementsResponse } from '@/api/exports';
import { Badge } from '@/components/ui/badge';
import { statutSignalementDeLArret } from '@/components/exports/signalementsArret';

interface Props {
  arret: { employee_id: string; selected_days?: string[] | null };
  signalements: SignalementsResponse | undefined;
}

/** Remplace l'attestation de salaire maison : l'arrêt va à la CPAM par la DSN. */
export function AbsenceSignalementBadge({ arret, signalements }: Props) {
  const statut = statutSignalementDeLArret(arret, signalements);
  if (!statut) return null;
  if (statut.fait) {
    return (
      <Badge variant="outline" className="w-fit">
        {statut.texte}
      </Badge>
    );
  }
  return (
    <Link to="/exports?tab=declarations">
      <Badge
        className={
          statut.urgent
            ? 'w-fit border-0 bg-red-600 text-white hover:bg-red-600'
            : 'w-fit border-0 bg-orange-500 text-white hover:bg-orange-500'
        }
      >
        {statut.texte}
      </Badge>
    </Link>
  );
}
