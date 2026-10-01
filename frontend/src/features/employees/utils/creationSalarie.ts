/**
 * Décision d'envoi et textes de l'écran « Nouveau collaborateur ».
 *
 * Le 30/09, la gestionnaire a rempli nom, prénom, entrée le 21/09, déposé un
 * contrat PDF, laissé le RIB vide : aucune requête n'est partie. Le formulaire
 * n'avait pas `noValidate` (`CreateEmployeeForm.tsx`) et des champs `number`
 * portaient un `step` (0,01 / 0,1) dans des onglets Radix `hidden`. Le
 * navigateur refuse alors l'envoi (stepMismatch / e-mail sans @) sans pouvoir
 * afficher la bulle — « invalid form control is not focusable ». L'extraction
 * PDF peut en plus écraser le nom par une initiale.
 *
 * Ici : peut-on envoyer, quel message, quel onglet, quel bouton. Sans React.
 */
import { createEmployeeFormSchema } from '@/features/employees/components/createEmployeeFormSchema';
import {
  erreursDansLOrdre,
  libelleDErreur,
  ongletDuChamp,
  type ErreurDeChamp,
} from '@/features/employees/utils/valeursEmbauche';

export const MENTION_RIB_A_COMPLETER = 'RIB à compléter';
export const MESSAGE_FERMETURE_SANS_ENREGISTRER =
  "Ce salarié n'est pas enregistré. Fermer sans enregistrer ?";

export const NOM_DES_ONGLETS: Record<string, string> = {
  collaborateur: 'Collaborateur',
  contrat: 'Contrat',
  remuneration: 'Rémunération',
  avantages: 'Avantages',
  specifiques: 'Spécificités',
};

const ONGLET_VIDE = { collaborateur: 0, contrat: 0, remuneration: 0, avantages: 0, specifiques: 0 };

const CLE_NOUVEAU = 'eywai-nouveau-salarie';
const DUREE_BADGE_MS = 24 * 60 * 60 * 1000;
let memoireNouveau: { id: string; at: number } | null = null;

/** Le pas HTML5 (`step="0.01"`) refuse 1990,001 ; `step="any"` l'accepte. */
export function champNumeriqueRefuseParLeNavigateur(
  valeur: number,
  pas: number | string,
  min = 0,
): boolean {
  if (pas === 'any' || pas === '' || pas === undefined) return false;
  const nPas = typeof pas === 'string' ? Number(pas) : pas;
  if (!Number.isFinite(valeur) || !Number.isFinite(nPas) || nPas <= 0) return false;
  const n = (valeur - min) / nPas;
  return Math.abs(n - Math.round(n)) > 1e-8;
}

/** Validation native `type="email"` : une valeur sans @ bloque à côté du nom. */
export function emailHtmlInvalide(valeur: string | null | undefined): boolean {
  const v = (valeur ?? '').trim();
  if (!v) return false;
  return !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

export function pastillesParOnglet(erreurs: ErreurDeChamp[]): Record<string, number> {
  const pastilles = { ...ONGLET_VIDE };
  for (const e of erreurs) {
    const onglet = ongletDuChamp(e.chemin);
    if (onglet in pastilles) pastilles[onglet] += 1;
  }
  return pastilles;
}

export function texteDuBoutonCreation(p: { nb: number; onglet: string; envoi?: boolean }): string {
  if (p.envoi) return 'Enregistrement…';
  if (p.nb <= 0) return 'Enregistrer le salarié';
  const nom = p.onglet || 'Collaborateur';
  if (p.nb === 1) return `1 information à compléter (onglet ${nom})`;
  return `${p.nb} informations à compléter (onglet ${nom})`;
}

export function saisieNonEnregistree(formulaireModifie: boolean, fichierJoint: boolean): boolean {
  return formulaireModifie || fichierJoint;
}

export function bandeauNonEnregistre(raison: string): string {
  const propre = raison.replace(/^Salarié NON enregistré\s*:\s*/i, '').trim();
  return `Salarié NON enregistré : ${propre || 'corrigez les champs indiqués, puis réessayez.'}`;
}

export function estErreurValidationInattendue(message: string): boolean {
  return /expected|received|invalid_type|undefined is not|cannot read/i.test(message);
}

function erreursDuSchema(valeurs: unknown): ErreurDeChamp[] {
  const r = createEmployeeFormSchema.safeParse(valeurs);
  if (r.success) return [];
  return erreursDansLOrdre(
    r.error.issues.map((i) => ({ chemin: i.path.join('.'), message: i.message })),
  );
}

export type DecisionCreation = {
  envoyer: boolean;
  message: string | null;
  onglet: string | null;
  erreurs: ErreurDeChamp[];
  pastilles: Record<string, number>;
  texteBouton: string;
  resteARemplir: { chemin: string; libelle: string; onglet: string }[];
};

export function decisionCreation(
  valeurs: unknown,
  options?: { nombresHorsPas?: boolean; emailNavigateurInvalide?: boolean },
): DecisionCreation {
  const erreurs = erreursDuSchema(valeurs);
  const pastilles = pastillesParOnglet(erreurs);
  const premiere = erreurs[0];
  const onglet = premiere ? ongletDuChamp(premiere.chemin) : null;
  const resteARemplir = erreurs.map((e) => ({
    chemin: e.chemin,
    libelle: libelleDErreur(e),
    onglet: ongletDuChamp(e.chemin),
  }));

  if (options?.nombresHorsPas) {
    return {
      envoyer: false,
      message:
        'Salarié NON enregistré : un montant n’est pas un nombre simple (onglet Rémunération). Retirez les décimales en trop, ou enregistrez à nouveau : le pas du navigateur ne bloque plus l’envoi.',
      onglet: 'remuneration',
      erreurs,
      pastilles: { ...pastilles, remuneration: Math.max(pastilles.remuneration, 1) },
      texteBouton: texteDuBoutonCreation({ nb: Math.max(erreurs.length, 1), onglet: 'Rémunération' }),
      resteARemplir:
        resteARemplir.length > 0
          ? resteARemplir
          : [{ chemin: 'salaire_de_base.valeur', libelle: 'Salaire de base', onglet: 'remuneration' }],
    };
  }
  if (options?.emailNavigateurInvalide) {
    return {
      envoyer: false,
      message:
        'Salarié NON enregistré : l’e-mail n’est pas une adresse (onglet Collaborateur). Laissez-le vide, ou corrigez-le.',
      onglet: 'collaborateur',
      erreurs,
      pastilles: { ...pastilles, collaborateur: Math.max(pastilles.collaborateur, 1) },
      texteBouton: texteDuBoutonCreation({ nb: Math.max(erreurs.length, 1), onglet: 'Collaborateur' }),
      resteARemplir,
    };
  }
  if (erreurs.length > 0) {
    return {
      envoyer: false,
      message: null,
      onglet,
      erreurs,
      pastilles,
      texteBouton: texteDuBoutonCreation({
        nb: erreurs.length,
        onglet: NOM_DES_ONGLETS[onglet ?? 'collaborateur'] ?? 'Collaborateur',
      }),
      resteARemplir,
    };
  }
  return {
    envoyer: true,
    message: null,
    onglet: null,
    erreurs: [],
    pastilles,
    texteBouton: texteDuBoutonCreation({ nb: 0, onglet: 'Collaborateur' }),
    resteARemplir: [],
  };
}

export function raisonEchecCreation(error: unknown): string {
  const err = error as {
    message?: string;
    response?: { status?: number; data?: { detail?: unknown; field_errors?: Record<string, string> } };
  };
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;
  const champs = err?.response?.data?.field_errors;
  if (champs && Object.keys(champs).length > 0) {
    const liste = Object.values(champs).filter((m) => typeof m === 'string' && m.trim());
    if (liste.length) return bandeauNonEnregistre(liste.join(' ; '));
  }
  if (typeof detail === 'string' && detail.trim() && !/traceback|\.py\b|exception/i.test(detail)) {
    return bandeauNonEnregistre(detail.trim());
  }
  if (!err?.response) {
    return bandeauNonEnregistre(
      "la requête n'est pas partie. Vérifiez les champs en rouge, puis réessayez.",
    );
  }
  if (status === 401 || status === 403) {
    return bandeauNonEnregistre(
      "vous n'avez pas le droit de créer un salarié dans cette société. Vérifiez la société active.",
    );
  }
  if (status === 409) {
    return bandeauNonEnregistre('un salarié existe déjà avec ces informations. Vérifiez le nom et le n° de sécurité sociale.');
  }
  if (status !== undefined && status >= 500) {
    return bandeauNonEnregistre('le service a refusé l’enregistrement. Réessayez dans quelques instants.');
  }
  return bandeauNonEnregistre('corrigez les champs indiqués, puis réessayez.');
}

function nombreDepuisExtraction(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v !== 'string') return null;
  const n = Number(v.replace(/\s/g, '').replace(',', '.').replace(/[^\d.+-]/g, ''));
  return Number.isFinite(n) ? n : null;
}

function estIdentite(v: unknown): v is string {
  return typeof v === 'string' && v.trim().length >= 2;
}

type Dictionnaire = Record<string, unknown>;

function fusionnerObjet(actuel: Dictionnaire, extrait: Dictionnaire): Dictionnaire {
  const result: Dictionnaire = { ...actuel };
  for (const [cle, val] of Object.entries(extrait)) {
    if (val === undefined || val === null || val === '') continue;
    if (cle === 'first_name' || cle === 'last_name' || cle === 'job_title') {
      if (estIdentite(val)) result[cle] = val;
      continue;
    }
    if (cle === 'email') {
      if (typeof val === 'string' && !emailHtmlInvalide(val)) result[cle] = val.trim();
      continue;
    }
    if (cle === 'salaire_de_base' && typeof val === 'object' && !Array.isArray(val)) {
      const actuelSalaire = (actuel.salaire_de_base as Dictionnaire) ?? {};
      const extraitSalaire = val as Dictionnaire;
      const valeur = nombreDepuisExtraction(extraitSalaire.valeur);
      result[cle] = {
        ...actuelSalaire,
        ...extraitSalaire,
        valeur: valeur ?? actuelSalaire.valeur,
      };
      continue;
    }
    if (
      typeof val === 'object' &&
      !Array.isArray(val) &&
      actuel[cle] &&
      typeof actuel[cle] === 'object' &&
      !Array.isArray(actuel[cle])
    ) {
      result[cle] = fusionnerObjet(actuel[cle] as Dictionnaire, val as Dictionnaire);
      continue;
    }
    result[cle] = val;
  }
  return result;
}

export function fusionnerExtractionContrat<T>(actuel: T, extrait: unknown): T {
  if (!extrait || typeof extrait !== 'object' || Array.isArray(extrait)) return actuel;
  return fusionnerObjet(actuel as Dictionnaire, extrait as Dictionnaire) as T;
}

export function mentionsListeSalarie(manquants: string[] | null | undefined): string[] {
  return (manquants ?? []).map((m) =>
    /rib|coordonn[eé]es bancaires/i.test(m) ? MENTION_RIB_A_COMPLETER : m,
  );
}

export function estNouveauSalarie(id: string, maintenant = Date.now()): boolean {
  return lireNouveauSalarie(maintenant) === id;
}

export function memoriserNouveauSalarie(id: string, maintenant = Date.now()): void {
  memoireNouveau = { id, at: maintenant };
  try {
    sessionStorage.setItem(CLE_NOUVEAU, JSON.stringify(memoireNouveau));
  } catch {
    /* node / navigation privée */
  }
}

export function lireNouveauSalarie(maintenant = Date.now()): string | null {
  let v = memoireNouveau;
  try {
    const brut = sessionStorage.getItem(CLE_NOUVEAU);
    if (brut) v = JSON.parse(brut) as { id: string; at: number };
  } catch {
    /* ignore */
  }
  if (!v?.id) return null;
  if (maintenant - v.at > DUREE_BADGE_MS) return null;
  return v.id;
}

export function mettreEnTeteDeListe<T extends { id: string }>(liste: T[], idNouveau: string | null): T[] {
  if (!idNouveau) return liste;
  const idx = liste.findIndex((e) => e.id === idNouveau);
  if (idx <= 0) return liste;
  const copie = [...liste];
  const [nouveau] = copie.splice(idx, 1);
  return [nouveau, ...copie];
}

export function salariesAvecNouveauEnTete<T extends { id: string }>(
  liste: T[],
  maintenant = Date.now(),
): T[] {
  return mettreEnTeteDeListe(liste, lireNouveauSalarie(maintenant));
}

/** Mémoriser avant d’invalider : sinon le refetch rend une liste sans badge ni tête. */
export async function apresCreation(
  id: string,
  memoriser: (id: string) => void,
  recharger: () => void | Promise<void>,
): Promise<void> {
  memoriser(id);
  await recharger();
}

const IBAN = /\bFR\d{2}[\s\d]{10,}\b/gi;
const EMAIL = /\b[\w.+-]+@[\w.-]+\.\w+\b/gi;
const NIR = /\b[12]\s?\d{2}[\s\d]{10,}\b/g;
const PDF = /\b[\w.-]+\.pdf\b/gi;

function sansDonneesPersonnelles(texte: string): string {
  return texte
    .replace(IBAN, '[iban]')
    .replace(EMAIL, '[email]')
    .replace(NIR, '[nir]')
    .replace(PDF, '[fichier]')
    .replace(/\b[A-ZÉÈÊÀ][a-zàâäéèêëïîôùûüç]+(?:[-\s][A-ZÉÈÊÀ][a-zàâäéèêëïîôùûüç]+)+\b/g, '[nom]')
    .slice(0, 300);
}

export function payloadJournalEcran(brut: {
  ecran: string;
  action: string;
  message: string;
  pile?: string;
  extra?: unknown;
}): { ecran: string; action: string; message: string; pile: string } {
  const pile = (brut.pile ?? '')
    .split('\n')
    .slice(0, 20)
    .join('\n')
    .slice(0, 2000);
  return {
    ecran: String(brut.ecran ?? '').slice(0, 80),
    action: String(brut.action ?? '').slice(0, 80),
    message: sansDonneesPersonnelles(String(brut.message ?? '')),
    pile: sansDonneesPersonnelles(pile),
  };
}
