export function formatSecondsToHoursMinutes(totalSeconds: number | undefined): string {
  if (!totalSeconds || totalSeconds <= 0) return "0h00";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  return `${hours}h${minutes.toString().padStart(2, "0")}`;
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
