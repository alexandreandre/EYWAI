import type { BadgeuseStatusToday } from "@/api/badgeuse";
import { formatSecondsToHoursMinutes, formatTimeFr, sourceLabel, eventTypeLabel } from "@/lib/badgeuseFormat";
import { cn } from "@/lib/utils";

type Props = {
  data: BadgeuseStatusToday;
};

export function BadgeuseDayTimeline({ data }: Props) {
  const events = data.events ?? [];
  const sequences = data.sequences ?? [];
  const totalLabel = formatSecondsToHoursMinutes(data.total_seconds);
  const dayStart = data.date
    ? new Date(`${data.date}T06:00:00`)
    : new Date();
  const dayEnd = data.date
    ? new Date(`${data.date}T20:00:00`)
    : new Date();
  const spanMs = Math.max(dayEnd.getTime() - dayStart.getTime(), 1);

  return (
    <div className="space-y-4">
      {sequences.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Créneaux de présence
          </p>
          <div className="relative h-3 w-full rounded-full bg-muted overflow-hidden">
            {sequences.map((seq, i) => {
              const start = new Date(seq.start).getTime();
              const end = new Date(seq.end).getTime();
              const left = ((start - dayStart.getTime()) / spanMs) * 100;
              const width = Math.max(((end - start) / spanMs) * 100, 2);
              return (
                <div
                  key={`${seq.start}-${i}`}
                  className="absolute top-0 h-full rounded-full bg-primary/80"
                  style={{ left: `${Math.min(left, 98)}%`, width: `${width}%` }}
                  title={`${formatTimeFr(seq.start)} – ${formatTimeFr(seq.end)}`}
                />
              );
            })}
          </div>
        </div>
      )}

      <div>
        <div className="flex items-baseline justify-between mb-2">
          <h2 className="text-sm font-semibold">Historique</h2>
          <span className="text-sm tabular-nums text-muted-foreground">{totalLabel}</span>
        </div>
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucun pointage enregistré pour cette journée.
          </p>
        ) : (
          <ul className="space-y-2">
            {events.map((e) => (
              <li
                key={e.id ?? e.timestamp}
                className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm"
              >
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      e.event_type === "ENTREE" ? "bg-emerald-500" : "bg-slate-400"
                    )}
                  />
                  {eventTypeLabel(e.event_type)} — {formatTimeFr(e.timestamp)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {sourceLabel(e.source)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
