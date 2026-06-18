export function formatSecondsToHoursMinutes(totalSeconds: number | undefined): string {
  if (!totalSeconds || totalSeconds <= 0) return "0h00";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  return `${hours}h${minutes.toString().padStart(2, "0")}`;
}

/** Valeur pour input type="time" (HH:MM). */
export function secondsToHoursMinutesInput(totalSeconds: number | undefined): string {
  if (totalSeconds == null || totalSeconds < 0) return "00:00";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;
}

/** Parse "HH:MM" ou "H:MM" en secondes. */
export function parseHoursMinutesToSeconds(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const match = /^(\d{1,2}):(\d{2})$/.exec(trimmed);
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (minutes < 0 || minutes > 59 || hours < 0 || hours > 24) return null;
  if (hours === 24 && minutes > 0) return null;
  return hours * 3600 + minutes * 60;
}

/** Affiche l'écart entre brut et effectif (ex. −30 min). */
export function formatSecondsDelta(
  computedSeconds: number,
  effectiveSeconds: number
): string | null {
  const delta = effectiveSeconds - computedSeconds;
  if (delta === 0) return null;
  const sign = delta > 0 ? "+" : "−";
  const abs = Math.abs(delta);
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  if (h > 0 && m > 0) return `${sign}${h}h${m.toString().padStart(2, "0")}`;
  if (h > 0) return `${sign}${h}h`;
  return `${sign}${m} min`;
}

export function formatTimeFr(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function sourceLabel(source: string): string {
  switch (source) {
    case "QR_SCAN":
      return "Scan QR";
    case "RH":
      return "RH";
    default:
      return "Employé";
  }
}

export function eventTypeLabel(type: string): string {
  return type === "ENTREE" ? "Entrée" : "Sortie";
}
