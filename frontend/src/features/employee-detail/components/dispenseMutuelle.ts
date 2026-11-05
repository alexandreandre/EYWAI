/**
 * Dispense de mutuelle posée par la RH sur la fiche (05/11/2026).
 *
 * Les motifs sont ceux de la loi, lus sur Légifrance le 05/11/2026 :
 * CSS D911-2 (dispenses de droit, santé seulement) et R242-1-6 (dispenses
 * « prévues dans l'acte juridique » de l'entreprise). Dans les deux cas,
 * « l'employeur doit être en mesure de produire la demande de dispense » :
 * d'où la date de la demande signée, exigée. Le contrôle de la DSN est côté
 * serveur (backend/app/shared/domain/dispense_mutuelle.py), mêmes codes.
 */

export type BesoinDuMotif = 'justificatif' | 'fin' | null;

export interface MotifDispense {
  code: string;
  libelle: string;
  source: string;
  /** Date de plus à demander : justificatif annuel, ou fin de la dispense. */
  besoin: BesoinDuMotif;
  /** R242-1-6 seul : valable seulement si l'acte de l'entreprise le prévoit. */
  selonActe: boolean;
}

export const MOTIFS_DISPENSE_MUTUELLE: MotifDispense[] = [
  {
    code: 'couverture_collective',
    libelle: 'Couvert ailleurs par une mutuelle collective (conjoint, parent des enfants, autre employeur)',
    source: 'CSS D911-2 3° ; R242-1-6 2° f',
    besoin: 'justificatif',
    selonActe: false,
  },
  {
    code: 'css',
    libelle: 'Bénéficiaire de la complémentaire santé solidaire',
    source: 'CSS D911-2 1°',
    besoin: 'fin',
    selonActe: false,
  },
  {
    code: 'assurance_individuelle',
    libelle: "Assurance santé individuelle déjà en cours à l'embauche",
    source: 'CSS D911-2 2°',
    besoin: 'fin',
    selonActe: false,
  },
  {
    code: 'cdd_moins_12_mois',
    libelle: 'CDD ou apprenti de moins de 12 mois',
    source: 'CSS R242-1-6 2° b',
    besoin: null,
    selonActe: true,
  },
  {
    code: 'cdd_12_mois_et_plus',
    libelle: 'CDD ou apprenti de 12 mois ou plus, couvert à titre individuel',
    source: 'CSS R242-1-6 2° a',
    besoin: null,
    selonActe: true,
  },
  {
    code: 'temps_partiel_10_pourcent',
    libelle: "Temps partiel ou apprenti : cotisation d'au moins 10 % du brut",
    source: 'CSS R242-1-6 2° c',
    besoin: null,
    selonActe: true,
  },
  {
    code: 'anterieur_decision_unilaterale',
    libelle: 'Embauché avant une mutuelle mise en place par décision unilatérale',
    source: 'CSS R242-1-6 1°',
    besoin: null,
    selonActe: true,
  },
];

/** Ce que la fiche garde (`specificites_paie.mutuelle.dispense`). */
export interface DispenseFiche {
  motif: string;
  demande_recue_le: string;
  justificatif_recu_le: string | null;
  fin_le: string | null;
}

/** Ce que le formulaire manipule : des chaînes, vides quand rien n'est saisi. */
export interface DispenseFormulaire {
  active: boolean;
  motif: string;
  demande_recue_le: string;
  justificatif_recu_le: string;
  fin_le: string;
}

export const DISPENSE_VIDE: DispenseFormulaire = {
  active: false,
  motif: '',
  demande_recue_le: '',
  justificatif_recu_le: '',
  fin_le: '',
};

/**
 * Motifs en toutes lettres des dispenses posées le 25/10/2026, avant ce format
 * (CDD de Colorplast et Comitech) ; même table côté serveur.
 */
const ANCIENS_LIBELLES: Record<string, string> = {
  'CDD de moins de douze mois': 'cdd_moins_12_mois',
};

export function motifDispense(code: string): MotifDispense | undefined {
  return MOTIFS_DISPENSE_MUTUELLE.find((m) => m.code === code);
}

function jour(valeur: unknown): string {
  return typeof valeur === 'string' ? valeur.slice(0, 10) : '';
}

export function dispenseVersFormulaire(dispense: unknown): DispenseFormulaire {
  if (!dispense || typeof dispense !== 'object') return { ...DISPENSE_VIDE };
  const d = dispense as Record<string, unknown>;
  return {
    active: true,
    motif: typeof d.motif === 'string' ? (ANCIENS_LIBELLES[d.motif] ?? d.motif) : '',
    demande_recue_le: jour(d.demande_recue_le),
    justificatif_recu_le: jour(d.justificatif_recu_le),
    fin_le: jour(d.fin_le),
  };
}

/**
 * `null` efface la dispense : une formule est choisie, ou la case est décochée.
 * Les notes d'une dispense déjà sur la fiche (`existante`) sont gardées.
 */
export function dispenseVersFiche(
  saisie: Partial<DispenseFormulaire> | undefined,
  aUneFormule: boolean,
  existante?: unknown,
): DispenseFiche | null {
  const formulaire = { ...DISPENSE_VIDE, ...saisie };
  if (aUneFormule || !formulaire.active) return null;
  const besoin = motifDispense(formulaire.motif)?.besoin ?? null;
  const notes = existante && typeof existante === 'object' ? (existante as Record<string, unknown>) : {};
  return {
    ...notes,
    motif: formulaire.motif,
    demande_recue_le: formulaire.demande_recue_le,
    justificatif_recu_le:
      besoin === 'justificatif'
        ? formulaire.justificatif_recu_le || formulaire.demande_recue_le
        : null,
    fin_le: besoin === 'fin' ? formulaire.fin_le || null : null,
  };
}

export function problemesDispense(
  saisie: Partial<DispenseFormulaire> | undefined,
): { champ: keyof DispenseFormulaire; message: string }[] {
  const formulaire = { ...DISPENSE_VIDE, ...saisie };
  if (!formulaire.active) return [];
  const problemes: { champ: keyof DispenseFormulaire; message: string }[] = [];
  const motif = motifDispense(formulaire.motif);
  if (!motif) problemes.push({ champ: 'motif', message: 'Choisissez le motif de la dispense.' });
  if (!formulaire.demande_recue_le) {
    problemes.push({
      champ: 'demande_recue_le',
      message: 'Indiquez la date de la demande signée par le salarié.',
    });
  }
  if (motif?.besoin === 'fin' && !formulaire.fin_le) {
    problemes.push({ champ: 'fin_le', message: 'Indiquez la date de fin de la dispense.' });
  }
  return problemes;
}
