import type { LucideIcon } from 'lucide-react';
import {
  Award,
  CalendarCheck,
  CalendarDays,
  Clock,
  CreditCard,
  FileWarning,
  Landmark,
  Mail,
  PiggyBank,
  Stethoscope,
  TrendingUp,
  UserPlus,
  UserRoundPlus,
} from 'lucide-react';

import { ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS } from '@/api/annualReviews';
import { RIB_ALERTS_UI_ENABLED } from '@/lib/productFeatureFlags';

export type RhPendingTaskId =
  | 'leaves'
  | 'expenses'
  | 'rib'
  | 'medical'
  | 'residence'
  | 'contracts'
  | 'annualReviews'
  | 'recruitment'
  | 'schedules'
  | 'onboardingProfiles'
  | 'pendingSignatures'
  | 'rates'
  | 'workMedals'
  | 'modulation'
  | 'cet';

export interface RhPendingTaskItem {
  id: RhPendingTaskId;
  label: string;
  count: number;
  href: string;
  icon: LucideIcon;
  hint: string;
  /** Route sidebar associée (agrégation des pastilles nav). */
  sidebarPath?: string;
}

export interface RhPendingTasksInput {
  pendingAbsences: number;
  pendingExpenses: number;
  obsoleteRates: number;
  expiringContracts: number;
  endOfTrialPeriods: number;
  residenceExpire: number;
  residenceRenew: number;
  residenceMissing: number;
  medicalEnabled: boolean;
  medicalOverdue: number;
  medicalDue30: number;
  ribTotal: number;
  annualReviewsUpcoming: number;
  recruitmentEnabled: boolean;
  recruitmentPending: number;
  schedulesDue: number;
  workMedalsAwaiting: number;
  rttClosable: number;
  modulationAlerts: number;
  cetPending: number;
  incompleteProfiles: number;
  pendingSignatures: number;
  recruitmentPreview?: string | null;
  onboardingPreview?: string | null;
  onboardingHref?: string;
}

const PRIORITY_ORDER: RhPendingTaskId[] = [
  'leaves',
  'expenses',
  'rib',
  'medical',
  'residence',
  'contracts',
  'annualReviews',
  'recruitment',
  'schedules',
  'onboardingProfiles',
  'pendingSignatures',
  'rates',
  'workMedals',
  'modulation',
  'cet',
];

function itemOrNull(
  id: RhPendingTaskId,
  count: number,
  label: string,
  href: string,
  icon: LucideIcon,
  hint: string,
  sidebarPath?: string,
): RhPendingTaskItem | null {
  if (count <= 0) return null;
  return { id, label, count, href, icon, hint, sidebarPath };
}

/** Construit la file des actions RH à traiter (alignée sur les pastilles sidebar). */
export function buildRhPendingTasks(input: RhPendingTasksInput): RhPendingTaskItem[] {
  const leavesCount = input.pendingAbsences + input.rttClosable;
  const residenceTotal =
    input.residenceExpire + input.residenceRenew + input.residenceMissing;
  const medicalTotal = input.medicalEnabled
    ? input.medicalOverdue + input.medicalDue30
    : 0;
  const contractsTotal = input.expiringContracts + input.endOfTrialPeriods;

  const byId: Record<RhPendingTaskId, RhPendingTaskItem | null> = {
    leaves: itemOrNull(
      'leaves',
      leavesCount,
      "Demandes d'absences",
      '/leaves',
      CalendarCheck,
      input.rttClosable > 0 && input.pendingAbsences > 0
        ? 'Validations et clôtures RTT en attente'
        : input.rttClosable > 0
          ? 'Clôtures RTT fin de période'
          : "À valider aujourd'hui",
      '/leaves',
    ),
    expenses: itemOrNull(
      'expenses',
      input.pendingExpenses,
      'Notes de frais',
      '/expenses',
      CreditCard,
      'En attente de traitement',
      '/expenses',
    ),
    rib:
      RIB_ALERTS_UI_ENABLED && input.ribTotal > 0
        ? itemOrNull(
            'rib',
            input.ribTotal,
            'Alertes RIB',
            '/employees',
            Landmark,
            'Modification ou doublon à examiner',
          )
        : null,
    medical: itemOrNull(
      'medical',
      medicalTotal,
      'Suivi médical',
      '/medical-follow-up',
      Stethoscope,
      'Visites à planifier ou en retard',
      '/medical-follow-up',
    ),
    residence: itemOrNull(
      'residence',
      residenceTotal,
      'Titres de séjour',
      '/residence-permits',
      FileWarning,
      'Échéances à surveiller',
      '/residence-permits',
    ),
    contracts: itemOrNull(
      'contracts',
      contractsTotal,
      "Contrats & périodes d'essai",
      '/employees?alert=deadlines',
      UserPlus,
      "Fin de CDD ou période d'essai sous 15 jours",
      '/employees',
    ),
    annualReviews: itemOrNull(
      'annualReviews',
      input.annualReviewsUpcoming,
      'Entretiens planifiés',
      '/annual-reviews?focus=upcoming',
      CalendarCheck,
      `Planifiés dans ${ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS} jours`,
      '/annual-reviews',
    ),
    recruitment:
      input.recruitmentEnabled && input.recruitmentPending > 0
        ? itemOrNull(
            'recruitment',
            input.recruitmentPending,
            'Recrutement',
            '/recruitment',
            UserPlus,
            input.recruitmentPreview
              ? `Candidats : ${input.recruitmentPreview}`
              : 'Candidatures en cours',
            '/recruitment',
          )
        : null,
    schedules: itemOrNull(
      'schedules',
      input.schedulesDue,
      'Plannings du mois',
      '/schedules',
      CalendarDays,
      'Horaires à saisir ou valider',
      '/schedules',
    ),
    onboardingProfiles: itemOrNull(
      'onboardingProfiles',
      input.incompleteProfiles,
      'Nouveaux salariés à compléter',
      input.onboardingHref ?? '/onboarding',
      UserRoundPlus,
      input.onboardingPreview
        ? `Fiches paie : ${input.onboardingPreview}`
        : 'Fiches paie à finaliser',
    ),
    pendingSignatures: itemOrNull(
      'pendingSignatures',
      input.pendingSignatures,
      'Signatures en attente',
      '/annual-reviews?signature_status=pending',
      Mail,
      'Procédures à relancer',
    ),
    rates: itemOrNull(
      'rates',
      input.obsoleteRates,
      'Taux de cotisations',
      '/rates',
      TrendingUp,
      'Mises à jour nécessaires',
      '/rates',
    ),
    workMedals: itemOrNull(
      'workMedals',
      input.workMedalsAwaiting,
      'Médailles du travail',
      '/company',
      Award,
      'Demandes à valider côté RH',
      '/company',
    ),
    modulation: itemOrNull(
      'modulation',
      input.modulationAlerts,
      'Modulation du temps',
      '/suivi-temps-travail',
      Clock,
      'Alertes de suivi à traiter',
      '/suivi-temps-travail',
    ),
    cet: itemOrNull(
      'cet',
      input.cetPending,
      'Compte épargne temps',
      '/suivi-cet',
      PiggyBank,
      'Demandes CET en attente',
      '/suivi-cet',
    ),
  };

  return PRIORITY_ORDER.map((id) => byId[id]).filter((t): t is RhPendingTaskItem => t != null);
}

export function sumRhPendingActions(items: RhPendingTaskItem[]): number {
  return items.reduce((acc, item) => acc + item.count, 0);
}

/** Mappe les items vers les compteurs sidebar (par route). */
export function rhPendingTasksToSidebarCounts(
  items: RhPendingTaskItem[],
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const item of items) {
    if (!item.sidebarPath) continue;
    out[item.sidebarPath] = (out[item.sidebarPath] ?? 0) + item.count;
  }
  return out;
}
