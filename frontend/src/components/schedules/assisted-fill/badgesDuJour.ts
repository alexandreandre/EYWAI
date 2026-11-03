/**
 * Badges bruts d'un jour (relevé avec entrées et sorties), montrés à côté des
 * heures retenues : la RH voit d'où vient le retraitement (arrondi à
 * l'horaire, heures en plus à valider, pointage incomplet).
 */

function minutes(raw: string | null | undefined): number | null {
  const s = String(raw ?? '').trim();
  if (!s || /^0+$/.test(s)) return null;
  const m = /^(\d{1,2})[:hH](\d{2})$/.exec(s);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  if (/^\d{1,4}$/.test(s)) {
    const n = Number(s);
    const h = Math.floor(n / 100);
    const mm = n % 100;
    if (h <= 23 && mm <= 59) return h * 60 + mm;
  }
  return null;
}

const heure = (m: number) => `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`;

export function libelleBadges(
  entree: string | null | undefined,
  sortie: string | null | undefined
): string | null {
  const e = minutes(entree);
  const s = minutes(sortie);
  if (e == null && s == null) return null;
  return `badges ${e != null ? heure(e) : 'pas d’entrée'} → ${s != null ? heure(s) : 'pas de sortie'}`;
}
