import type { EmployeSimule } from "@/api/augmentations";
import { formatEuroAmount } from "@/lib/careerFormat";

/** Déduit les IDs réellement mis à jour à partir des lignes d'erreur retournées par l'API. */
export function computeAppliedEmployeeIds(
  requestedIds: string[],
  erreurs: string[],
): string[] {
  const failed = new Set<string>();
  for (const line of erreurs) {
    for (const id of requestedIds) {
      if (line.startsWith(`${id}:`)) {
        failed.add(id);
        break;
      }
    }
  }
  return requestedIds.filter((id) => !failed.has(id));
}

export function ligneAugmentation(e: EmployeSimule) {
  const pct =
    e.ancien_salaire_brut > 0
      ? ((e.nouveau_salaire_brut - e.ancien_salaire_brut) / e.ancien_salaire_brut) * 100
      : 0;
  return `+${formatEuroAmount(e.difference_brut)} (+${pct.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}%)`;
}

export function parseOptionalFloat(s: string): number | null {
  const t = s.trim();
  if (!t) return null;
  const n = parseFloat(t.replace(",", "."));
  return Number.isNaN(n) ? null : n;
}

export function parseOptionalInt(s: string): number | null {
  const t = s.trim();
  if (!t) return null;
  const n = parseInt(t, 10);
  return Number.isNaN(n) ? null : n;
}
