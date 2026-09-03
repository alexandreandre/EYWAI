const MONTH_NAMES = [
  'Janvier',
  'Février',
  'Mars',
  'Avril',
  'Mai',
  'Juin',
  'Juillet',
  'Août',
  'Septembre',
  'Octobre',
  'Novembre',
  'Décembre',
];

export function monthLabel(month: number): string {
  return MONTH_NAMES[month - 1] ?? `Mois ${month}`;
}

export function monthYearLabel(month: number, year: number): string {
  return `${monthLabel(month)} ${year}`;
}

export function buildYearOptions(
  payslipYears: number[],
  selectedYear: number
): number[] {
  const currentYear = new Date().getFullYear();
  const years = new Set<number>(payslipYears);
  years.add(selectedYear);
  for (let y = currentYear - 3; y <= currentYear + 2; y += 1) {
    years.add(y);
  }
  return Array.from(years).sort((a, b) => b - a);
}

export const PAYROLL_MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

export const PAYROLL_DURATION_STORAGE_KEY = 'eywai.payroll.avgGenerationMs';
export const DEFAULT_GENERATION_MS = 8000;
export const MAX_DURATION_SAMPLES = 20;

export function readAverageGenerationMs(): number {
  try {
    const raw = localStorage.getItem(PAYROLL_DURATION_STORAGE_KEY);
    if (!raw) return DEFAULT_GENERATION_MS;
    const parsed = JSON.parse(raw) as number;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_GENERATION_MS;
  } catch {
    return DEFAULT_GENERATION_MS;
  }
}

export function recordGenerationDuration(ms: number): void {
  if (!Number.isFinite(ms) || ms <= 0) return;
  try {
    const key = `${PAYROLL_DURATION_STORAGE_KEY}.samples`;
    const raw = localStorage.getItem(key);
    const samples: number[] = raw ? (JSON.parse(raw) as number[]) : [];
    samples.push(ms);
    const trimmed = samples.slice(-MAX_DURATION_SAMPLES);
    localStorage.setItem(key, JSON.stringify(trimmed));
    const avg = trimmed.reduce((a, b) => a + b, 0) / trimmed.length;
    localStorage.setItem(PAYROLL_DURATION_STORAGE_KEY, String(Math.round(avg)));
  } catch {
    // ignore storage errors
  }
}

/** Mois de paie « par défaut » pour les garde-fous du lancement : jusqu'au 15
 * du mois on prépare encore la paie du mois PRÉCÉDENT (pratique paie), ensuite
 * celle du mois courant. Évite qu'un début de mois aux calendriers vierges
 * bloque la paie du mois passé (retour Gaëlle 03/09). */
export function moisDePaieParDefaut(ref: Date): { year: number; month: number } {
  const d = new Date(ref.getFullYear(), ref.getMonth(), 1);
  if (ref.getDate() <= 15) {
    d.setMonth(d.getMonth() - 1);
  }
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}
