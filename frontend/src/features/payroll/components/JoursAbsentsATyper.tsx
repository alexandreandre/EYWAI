import { Link } from 'react-router-dom';

import { libellePlages } from '@/features/payroll/lib/joursASaisir';

interface Props {
  /** Jours marqués « absent » sans type, dates ISO, tels que le serveur les a relevés. */
  jours: string[];
  /** Calendrier du salarié, ouvert sur le mois. */
  lienCalendrier: string;
  onLienClick?: () => void;
}

/**
 * Case « absent » de l'import (retour d'Elsa du 28/10/2026) : le refus nomme
 * les jours et mène au calendrier, où la RH donne leur type. Pas de forçage.
 */
export function JoursAbsentsATyper({ jours, lienCalendrier, onLienClick }: Props) {
  return (
    <div className="space-y-2 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
      {jours.length > 0 && (
        <p>
          Jours marqués « absent » : <span className="font-medium">{libellePlages(jours)}</span>.
        </p>
      )}
      <p className="text-xs">
        Donnez le type de chaque jour (congé, RTT, arrêt ou absence non payée). Ce refus ne se
        force pas : la case « absent » ne dit pas ce qu’il faut payer.
      </p>
      <Link
        to={lienCalendrier}
        onClick={onLienClick}
        className="text-xs font-medium underline underline-offset-2"
      >
        Ouvrir le calendrier
      </Link>
    </div>
  );
}
