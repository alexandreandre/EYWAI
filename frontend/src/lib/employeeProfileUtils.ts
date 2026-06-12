/** Types et formatage pour la page profil collaborateur (lecture seule). */

export interface EmployeeAddress {
  rue?: string;
  code_postal?: string;
  ville?: string;
}

export interface EmployeeSocialLine {
  id: string;
  libelle: string;
  montant_salarial?: number;
  salarial?: number;
}

export interface EmployeeProfileData {
  id: string;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone_number?: string | null;
  adresse?: EmployeeAddress | null;
  coordonnees_bancaires?: { iban?: string } | null;
  hire_date?: string | null;
  contract_type?: string | null;
  statut?: string | null;
  job_title?: string | null;
  duree_hebdomadaire?: number | null;
  trial_period_applicable?: boolean | null;
  trial_period_status?:
    | "in_progress"
    | "ending_soon"
    | "ended"
    | "confirmed"
    | "to_complete"
    | null;
  trial_period_end_date?: string | null;
  trial_period_days_remaining?: number | null;
  salaire_de_base?: { valeur?: number } | null;
  specificites_paie?: {
    prelevement_a_la_source?: { taux?: number | null };
    mutuelle?: {
      adhesion?: boolean;
      lignes_specifiques?: EmployeeSocialLine[];
    };
    prevoyance?: {
      adhesion?: boolean;
      lignes_specifiques?: EmployeeSocialLine[];
    };
  } | null;
}

export function formatProfileDate(dateString: string | null | undefined): string {
  if (!dateString) return 'Non renseigné';
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return 'Non renseigné';
  return date.toLocaleDateString('fr-FR');
}

export function formatProfileAddress(adresse: EmployeeAddress | null | undefined): string {
  if (!adresse) return 'Non renseigné';
  const parts = [adresse.rue, adresse.code_postal, adresse.ville].filter(Boolean);
  return parts.length > 0 ? parts.join(', ') : 'Non renseigné';
}

export function formatWeeklyHours(hours: number | null | undefined): string {
  if (hours == null) return 'Non renseigné';
  return `${hours} h/semaine`;
}

export function formatTrialPeriodLabel(profile: EmployeeProfileData): string | null {
  if (!profile.trial_period_applicable) return null;
  if (profile.trial_period_status === 'confirmed') {
    return 'Confirmée';
  }
  if (profile.trial_period_end_date) {
    return `Se termine le ${formatProfileDate(profile.trial_period_end_date)}`;
  }
  if (profile.trial_period_status === 'to_complete') {
    return 'À renseigner par les RH';
  }
  return null;
}

export function maskIban(iban: string | undefined): string {
  if (!iban?.trim()) return 'Non renseigné';
  const trimmed = iban.replace(/\s/g, '').toUpperCase();
  if (trimmed.length < 8) return trimmed;
  const last4 = trimmed.slice(-4);
  if (/^[A-Z]{2}/.test(trimmed)) {
    return `${trimmed.slice(0, 4)} **** **** ${last4}`;
  }
  return `**** **** ${last4}`;
}

export function formatProfileCurrency(amount: number | undefined): string | null {
  if (amount == null) return null;
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
  }).format(amount);
}

export function getFirstSocialLine(
  profile: EmployeeProfileData,
  type: 'mutuelle' | 'prevoyance'
): EmployeeSocialLine | null {
  const lines = profile.specificites_paie?.[type]?.lignes_specifiques;
  return lines && lines.length > 0 ? lines[0] : null;
}

export function getSocialLineAmount(line: EmployeeSocialLine, type: 'mutuelle' | 'prevoyance'): number | undefined {
  if (type === 'mutuelle') return line.montant_salarial;
  return line.salarial;
}

export function isProfileNotFoundError(error: unknown): boolean {
  if (error && typeof error === 'object' && 'response' in error) {
    const status = (error as { response?: { status?: number } }).response?.status;
    return status === 404;
  }
  return false;
}
