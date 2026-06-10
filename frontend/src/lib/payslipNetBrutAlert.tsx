export const NET_SUPERIEUR_BRUT_LABEL = 'Net > Brut';

export function isNetSuperieurBrutWarning(warning: string): boolean {
  const w = warning.trim().toLowerCase();
  if (w === 'net > brut') return true;
  if (w.includes('supérieur') && w.includes('brut')) return true;
  if (w.includes('net exceptionnellement élevé')) return true;
  return false;
}

export function hasNetSuperieurBrutWarning(warnings?: string[]): boolean {
  return (warnings ?? []).some(isNetSuperieurBrutWarning);
}

export function normalizePayslipWarning(warning: string): string {
  return isNetSuperieurBrutWarning(warning) ? NET_SUPERIEUR_BRUT_LABEL : warning;
}

export function PayslipNetBrutInlineLabel() {
  return (
    <span className="text-xs font-normal text-amber-700 dark:text-amber-400">
      {NET_SUPERIEUR_BRUT_LABEL}
    </span>
  );
}
