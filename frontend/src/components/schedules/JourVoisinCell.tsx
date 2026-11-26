import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import {
  CALENDAR_TYPE_BAR_COLORS,
  formatCalendarValue,
  getCalendarTypeLabel,
} from '@/lib/calendarTypes';
import { cn } from '@/lib/utils';

/**
 * Jour d'un mois voisin dans la grille (retour d'Elsa du 26/11) : en lecture,
 * pour contrôler une semaine à cheval sur deux mois. Un clic ouvre son mois.
 */
export function JourVoisinCell({
  date,
  prevu,
  reel,
  isForfaitJour,
  chargement,
  erreur,
  bloque,
  semaine,
  onOuvrir,
}: {
  date: Date;
  prevu?: PlannedEventData;
  reel?: ActualHoursData;
  isForfaitJour: boolean;
  chargement: boolean;
  erreur: boolean;
  /** Modifications non enregistrées : changer de mois les perdrait. */
  bloque: boolean;
  semaine?: number;
  onOuvrir: () => void;
}) {
  const libelleMois = date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  const moisLong = date.toLocaleDateString('fr-FR', { month: 'long' });
  const type = prevu?.type ?? null;
  return (
    <button
      type="button"
      data-testid="jour-voisin"
      onClick={onOuvrir}
      disabled={bloque}
      title={
        bloque
          ? 'Enregistrez d’abord ce mois pour ouvrir ' + moisLong + '.'
          : 'Ouvrir ' + moisLong + ' pour modifier ce jour.'
      }
      className={cn(
        'flex min-h-[7.5rem] w-full flex-col gap-1 rounded-xl border border-dashed bg-muted/40 p-2 text-left text-xs text-muted-foreground',
        bloque ? 'cursor-not-allowed' : 'hover:bg-muted',
      )}
    >
      <span className="flex items-center justify-between font-medium">
        <span>{libelleMois}</span>
        {semaine ? <span className="text-[10px]">S{semaine}</span> : null}
      </span>
      {erreur ? (
        <span>Jour illisible : ouvrez {moisLong}.</span>
      ) : chargement ? (
        <span>Chargement…</span>
      ) : prevu ? (
        <>
          <span className="flex items-center gap-1">
            <span
              className={cn('inline-block h-2 w-2 rounded-full', CALENDAR_TYPE_BAR_COLORS[type ?? ''] ?? 'bg-slate-400')}
            />
            {getCalendarTypeLabel(type)}
          </span>
          <span>Prévu : {formatCalendarValue(prevu.heures_prevues, isForfaitJour)}</span>
          <span>Fait : {formatCalendarValue(reel?.heures_faites, isForfaitJour)}</span>
        </>
      ) : (
        <span>Rien de saisi</span>
      )}
    </button>
  );
}
