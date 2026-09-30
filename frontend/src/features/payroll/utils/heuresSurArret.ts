/**
 * Heures saisies un jour d'arrêt ou d'absence : la logique de l'écran, sans React.
 *
 * La règle du conflit vit dans le backend (`schedules/domain/conflits_arret.py`) :
 * ici on ne fait que lire ce qu'il renvoie et écrire les textes de l'écran.
 */

import axios from 'axios';
import type { QueryKey } from '@tanstack/react-query';

import { TAB_CALENDRIER } from '@/features/employee-detail/utils/tabs';
import { extractDetail, getApiErrorStatus, sanitizeBackendMessage } from '@/lib/errorMessages';
import { queryKeys } from '@/lib/queryKeys';

export type JourEnConflit = {
  annee: number;
  mois: number;
  jour: number;
  heures: number;
  /** Type en cause au planning (week-end d'arrêt : celui de l'arrêt). Absent d'un backend ancien. */
  type_prevu?: string;
};

/** Jours en conflit d'un salarié à l'import des pointages. */
export type ConflitsImportSalarie = {
  employee_id: string;
  jours: JourEnConflit[];
};

/** Nature du conflit, décidée d'après `type_prevu` des jours (préfixe `arret`). */
export type NatureConflit = 'arret' | 'absence' | 'mixte';

/** Info-bulle d'un jour du calendrier qui porte des heures alors que le prévu est un arrêt. */
export const TITRE_INFO_BULLE_CONFLIT = 'Heures saisies pendant l’arrêt';

const MOIS = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

const estNombre = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export function lireJoursEnConflit(brut: unknown): JourEnConflit[] {
  if (!Array.isArray(brut)) return [];
  const jours: JourEnConflit[] = [];
  for (const item of brut) {
    if (!item || typeof item !== 'object') continue;
    const { annee, mois, jour, heures, type_prevu } = item as Record<string, unknown>;
    if (!estNombre(annee) || !estNombre(mois) || !estNombre(jour)) continue;
    const lu: JourEnConflit = { annee, mois, jour, heures: estNombre(heures) ? heures : 0 };
    if (typeof type_prevu === 'string' && type_prevu) lu.type_prevu = type_prevu;
    jours.push(lu);
  }
  return jours;
}

const parDate = (a: JourEnConflit, b: JourEnConflit) =>
  a.annee - b.annee || a.mois - b.mois || a.jour - b.jour;

const nomDuJour = (jour: number) => (jour === 1 ? '1er' : String(jour));

function enumeration(elements: string[]): string {
  if (elements.length <= 1) return elements.join('');
  return `${elements.slice(0, -1).join(', ')} et ${elements[elements.length - 1]}`;
}

/** Un appel d'effacement par mois : le backend n'en accepte qu'un à la fois. */
export function groupesParMois(
  jours: JourEnConflit[]
): { annee: number; mois: number; jours: number[] }[] {
  const groupes: { annee: number; mois: number; jours: number[] }[] = [];
  for (const j of [...jours].sort(parDate)) {
    const dernier = groupes[groupes.length - 1];
    if (dernier && dernier.annee === j.annee && dernier.mois === j.mois) {
      if (!dernier.jours.includes(j.jour)) dernier.jours.push(j.jour);
    } else {
      groupes.push({ annee: j.annee, mois: j.mois, jours: [j.jour] });
    }
  }
  return groupes;
}

/** « 7, 8 et 9 septembre » ; sur deux mois : « 31 août et 1er et 2 septembre ». */
export function libelleDesJours(jours: JourEnConflit[]): string {
  const morceaux = groupesParMois(jours).map((g) => {
    const nom = MOIS[g.mois - 1] ?? String(g.mois);
    return `${enumeration(g.jours.map(nomDuJour))} ${nom}`;
  });
  return morceaux.join(' et ');
}

export function messageHeuresEffacees(jours: JourEnConflit[]): string {
  return `Heures effacées : ${libelleDesJours(jours)}.`;
}

export function natureDuConflit(jours: JourEnConflit[]): NatureConflit {
  // Jamais lu dans le message : une reformulation le casserait. Sans type pour
  // tous les jours, repli neutre (« absence »).
  if (jours.length === 0 || jours.some((j) => !j.type_prevu)) return 'absence';
  const arrets = jours.filter((j) => j.type_prevu!.startsWith('arret')).length;
  if (arrets === jours.length) return 'arret';
  return arrets === 0 ? 'absence' : 'mixte';
}

/** Premier mot du nom complet ; rien s'il manque ou ressemble à un identifiant. */
export function prenomDe(nomComplet: string | null | undefined): string | null {
  const mot = (nomComplet ?? '').trim().split(/\s+/)[0] ?? '';
  if (!mot) return null;
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(mot)) return null;
  return mot;
}

/** Prénom porté par le bulletin chargé (`payslip_data.en_tete.salarie`), s'il y est. */
export function prenomDuBulletin(payslipData: unknown): string | null {
  const enTete = (payslipData as { en_tete?: { salarie?: unknown } } | null | undefined)?.en_tete;
  const salarie = enTete?.salarie;
  if (!salarie || typeof salarie !== 'object') return null;
  const { prenom, nom_complet } = salarie as Record<string, unknown>;
  if (typeof prenom === 'string' && prenom.trim()) return prenom.trim();
  return typeof nom_complet === 'string' ? prenomDe(nom_complet) : null;
}

/** Textes des deux boutons, sans genrer : le prénom, sinon « Le salarié ». */
export function textesDuChoix(
  nature: NatureConflit,
  prenom: string | null
): { effacer: string; modifier: string } {
  const sujet = prenom ?? 'Le salarié';
  if (nature === 'arret') {
    return {
      effacer: `${sujet} était en arrêt : effacer ces heures`,
      modifier: `${sujet} a travaillé : modifier l’arrêt`,
    };
  }
  return {
    effacer: `${sujet} n’a pas travaillé ces jours-là : effacer ces heures`,
    modifier: `${sujet} a travaillé : modifier l’absence`,
  };
}

/**
 * Aucun lien ne cible un arrêt précis : l'écran des absences (`/leaves`) s'ouvre
 * sur les demandes du seul salarié (`employee`, son id). `nature` sert au texte
 * du bandeau : un arrêt saisi au planning n'y figure pas, il se corrige au calendrier.
 */
export function lienModifierAbsence(employeeId: string, nature: NatureConflit): string {
  return `/leaves?employee=${encodeURIComponent(employeeId)}&nature=${nature}`;
}

export function lireNatureDuLien(valeur: string | null | undefined): NatureConflit | null {
  return valeur === 'arret' || valeur === 'absence' || valeur === 'mixte' ? valeur : null;
}

/** Onglet Calendrier de la fiche du salarié : là où se corrige ce qui a été saisi au planning. */
export function lienCalendrierDuSalarie(employeeId: string): string {
  return `/employees/${encodeURIComponent(employeeId)}?tab=${TAB_CALENDRIER}`;
}

const MOTS_DE_LA_NATURE: Record<
  NatureConflit,
  { objet: string; saisi: string; pronom: string; sujet: string }
> = {
  arret: { objet: 'l’arrêt', saisi: 'saisi', pronom: 'le', sujet: 'il' },
  absence: { objet: 'l’absence', saisi: 'saisie', pronom: 'la', sujet: 'elle' },
  mixte: { objet: 'l’arrêt ou l’absence', saisi: 'saisi', pronom: 'le', sujet: 'il' },
};

export type BandeauAbsencesDuSalarie = {
  texte: string;
  lien: { href: string; libelle: string };
};

/**
 * Bandeau de l'écran des absences ouvert sur un seul salarié. Seuls les congés
 * payés et RTT posés au planning créent une demande : un arrêt maladie ou une
 * absence non rémunérée saisi au planning n'apparaît pas ici. Le bandeau ne
 * promet donc jamais que l'arrêt y est, et renvoie au calendrier.
 */
export function bandeauAbsencesDuSalarie({
  employeeId,
  nature,
  chargement,
  erreur,
  nombreDeDemandes,
}: {
  employeeId: string;
  nature: NatureConflit | null;
  chargement: boolean;
  erreur: boolean;
  nombreDeDemandes: number;
}): BandeauAbsencesDuSalarie {
  const { objet, saisi, pronom, sujet } = MOTS_DE_LA_NATURE[nature ?? 'mixte'];
  const lien = {
    href: lienCalendrierDuSalarie(employeeId),
    libelle: 'Ouvrir le calendrier du salarié',
  };
  const auCalendrier = `-${pronom} dans le calendrier du salarié.`;
  if (erreur) {
    return {
      texte: `Les demandes d’absence de ce salarié n’ont pas pu être chargées : rechargez la page. Si ${objet} a été ${saisi} au planning, corrigez${auCalendrier}`,
      lien,
    };
  }
  if (chargement) {
    return { texte: 'Recherche des demandes d’absence de ce salarié…', lien };
  }
  if (nombreDeDemandes === 0) {
    return {
      texte: `Aucune demande d’absence enregistrée pour ce salarié : ${objet} a été ${saisi} au planning. Corrigez${auCalendrier}`,
      lien,
    };
  }
  return {
    texte: `Demandes d’absence de ce salarié. Si ${objet} à corriger n’apparaît pas ici, ${sujet} a été ${saisi} au planning : corrigez${auCalendrier}`,
    lien,
  };
}

/**
 * Requêtes TanStack à invalider après un effacement : les heures réelles de la
 * semaine (`useEmployeeWeekPayrollCalendar`), le planning et le préflight de la
 * paie, tous mois. Le calendrier mensuel (`useCalendar`) n'est pas une requête
 * TanStack : il relit le backend à son prochain chargement.
 */
export function clesAInvaliderApresEffacement(
  companyId: string | undefined,
  employeeId: string
): QueryKey[] {
  return [
    ['employee-week-payroll', employeeId],
    queryKeys.planning(companyId),
    queryKeys.payrollPreflightTousMois(companyId),
  ];
}

/** Des jours lisibles à effacer ? Sans jour, « effacer » n'est pas proposé. */
export function aDesJoursAEffacer(
  jours: readonly JourEnConflit[] | null | undefined
): jours is JourEnConflit[] {
  return Array.isArray(jours) && jours.length > 0;
}

/** Refus d'heures sur un arrêt dont les jours n'ont pas pu être lus. */
export const TEXTE_HEURES_SANS_JOURS =
  'Les jours en cause n’ont pas pu être lus. Ouvrez le calendrier du salarié : effacez-y ces heures, ou corrigez l’arrêt ou l’absence.';

/** Effacement réussi, régénération du bulletin en échec (écran de correction). */
export type SuiteEffacement = { effaces: JourEnConflit[]; echecGeneration: string };

export type EtatDialogueHeures =
  | { kind: 'choix'; jours: JourEnConflit[] }
  | { kind: 'sans_jours' }
  | {
      kind: 'generation_en_echec';
      titre: string;
      confirmation: string;
      echec: string;
      actionRelancer: string;
    };

/**
 * Ce que montre le dialogue d'un refus d'heures sur un arrêt. Une fois les
 * heures effacées, il ne les présente plus comme en conflit, même si le refus
 * affiché (venu d'une correction de bulletin) les porte encore.
 */
export function etatDialogueHeuresSurArret(
  jours: readonly JourEnConflit[] | null | undefined,
  suite: SuiteEffacement | null
): EtatDialogueHeures {
  if (suite && suite.effaces.length > 0) {
    return {
      kind: 'generation_en_echec',
      titre: 'Heures effacées, bulletin non régénéré',
      confirmation: messageHeuresEffacees(suite.effaces),
      echec: `Le bulletin n’a pas été régénéré. ${suite.echecGeneration}`,
      actionRelancer: 'Relancer la génération',
    };
  }
  if (aDesJoursAEffacer(jours)) return { kind: 'choix', jours: [...jours] };
  return { kind: 'sans_jours' };
}

/** Refus structuré `recalcul_refus` des réponses de correction et de restauration. */
export type RefusApresCorrection = {
  code: string;
  message: string;
  jours: JourEnConflit[];
};

export function lireRefusApresCorrection(brut: unknown): RefusApresCorrection | null {
  if (!brut || typeof brut !== 'object') return null;
  const { code, message, jours } = brut as Record<string, unknown>;
  if (typeof code !== 'string' || !code) return null;
  return {
    code,
    message: typeof message === 'string' ? message : '',
    jours: lireJoursEnConflit(jours),
  };
}

export type SuiteDeCorrection =
  | { kind: 'aucun' }
  | { kind: 'regenerer'; message: string }
  | { kind: 'choix'; refus: RefusApresCorrection };

/**
 * Que propose l'écran quand le recalcul d'après une correction n'a pas abouti ?
 * Un refus « heures sur jour d'arrêt » ne se règle pas en régénérant (le refus
 * reviendrait) : on propose le même choix que le dialogue de génération.
 */
export function choixApresCorrection(reponse: {
  recalcul_erreur?: string | null;
  recalcul_refus?: unknown;
}): SuiteDeCorrection {
  const refus = lireRefusApresCorrection(reponse.recalcul_refus);
  if (refus?.code === 'heures_sur_jour_d_arret' && refus.jours.length > 0) {
    return { kind: 'choix', refus };
  }
  const erreur = reponse.recalcul_erreur?.trim();
  if (erreur) return { kind: 'regenerer', message: erreur };
  if (refus?.message) return { kind: 'regenerer', message: refus.message };
  return { kind: 'aucun' };
}

/** Le jour est-il en conflit selon la liste `jours_en_conflit` du backend ? */
export function estJourEnConflit(
  jour: number,
  joursEnConflit: readonly number[] | null | undefined
): boolean {
  return !!joursEnConflit && joursEnConflit.includes(jour);
}

/**
 * Fusionne les deux sources de l'import : la réponse immédiate (chemin direct) et
 * `summary.commit_jours_en_conflit` (import par lot, lu au GET du lot). Une ligne
 * par salarié, ses jours réunis sans doublon.
 */
export function fusionnerJoursEnConflitImport(
  reponse: unknown,
  resumeDuLot: unknown
): ConflitsImportSalarie[] {
  const parSalarie = new Map<string, JourEnConflit[]>();
  for (const source of [reponse, resumeDuLot]) {
    if (!Array.isArray(source)) continue;
    for (const item of source) {
      if (!item || typeof item !== 'object') continue;
      const { employee_id, jours } = item as Record<string, unknown>;
      if (typeof employee_id !== 'string' || !employee_id) continue;
      const liste = parSalarie.get(employee_id) ?? [];
      for (const j of lireJoursEnConflit(jours)) {
        if (!liste.some((x) => parDate(x, j) === 0)) liste.push(j);
      }
      parSalarie.set(employee_id, liste);
    }
  }
  return [...parSalarie.entries()]
    .map(([employee_id, jours]) => ({ employee_id, jours: jours.sort(parDate) }))
    .filter((c) => c.jours.length > 0);
}

export type ResultatEffacement =
  | { ok: true; effaces: JourEnConflit[] }
  | { ok: false; effaces: JourEnConflit[]; restants: JourEnConflit[]; erreur: unknown };

/**
 * Efface les jours, un appel par mois, dans l'ordre. Au premier refus on s'arrête :
 * la suite (relancer la génération) ne doit jamais partir sur un effacement raté.
 */
export async function effacerLesJours(
  jours: JourEnConflit[],
  appeler: (annee: number, mois: number, jours: number[]) => Promise<unknown>
): Promise<ResultatEffacement> {
  const effaces: JourEnConflit[] = [];
  const tries = [...jours].sort(parDate);
  for (const groupe of groupesParMois(tries)) {
    const duGroupe = tries.filter((j) => j.annee === groupe.annee && j.mois === groupe.mois);
    try {
      await appeler(groupe.annee, groupe.mois, groupe.jours);
    } catch (erreur) {
      const faits = new Set(effaces);
      return {
        ok: false,
        effaces,
        restants: tries.filter((j) => !faits.has(j)),
        erreur,
      };
    }
    effaces.push(...duGroupe);
  }
  return { ok: true, effaces };
}

const A_LA_MAIN = 'effacez les heures à la main dans le calendrier du salarié.';

const estCoupureReseau = (erreur: unknown) => axios.isAxiosError(erreur) && !erreur.response;

const finDePhrase = (texte: string) => (/[.!?…]$/.test(texte) ? texte : `${texte}.`);

/**
 * Pourquoi l'appel d'effacement a échoué, et quoi faire. Propre à l'effacement :
 * jamais les replis de la génération (le bulletin n'est pas en cause ici).
 */
export function raisonEchecEffacement(erreur: unknown): string {
  if (estCoupureReseau(erreur)) {
    return 'La connexion au serveur a été coupée. Vérifiez votre connexion internet, puis réessayez.';
  }
  const statut = getApiErrorStatus(erreur);
  const motif = sanitizeBackendMessage(extractDetail(erreur));
  if (statut === 401) return 'Votre session a expiré. Reconnectez-vous, puis réessayez.';
  if (statut === 403) return 'Vous n’avez pas le droit de modifier le calendrier de ce salarié.';
  if (statut === 404) return 'Salarié introuvable. Rechargez la page, puis réessayez.';
  if (statut !== undefined && statut >= 500) {
    // 503 : le backend dit pourquoi (arrêts illisibles) ; une 500 peut porter un texte technique.
    if (statut === 503 && motif) return `${finDePhrase(motif)} Si le problème persiste, ${A_LA_MAIN}`;
    return `Le serveur n’a pas répondu. Réessayez dans un instant ; si le problème persiste, ${A_LA_MAIN}`;
  }
  if (statut !== undefined && statut >= 400) {
    return motif
      ? finDePhrase(motif)
      : 'La demande a été refusée. Effacez ces heures à la main dans le calendrier du salarié.';
  }
  return `L’effacement n’a pas abouti. Réessayez ; si le problème persiste, ${A_LA_MAIN}`;
}

/**
 * Message d'échec de l'effacement. Sur une coupure réseau, on ne sait pas si le
 * serveur a écrit : « pas confirmé », pas « pas effacé » (réessayer est sans risque,
 * l'effacement d'un jour déjà à 0 h ne change rien).
 */
export function messageEchecEffacement(effaces: JourEnConflit[], erreur: unknown): string {
  const incertain = estCoupureReseau(erreur);
  const raison = raisonEchecEffacement(erreur);
  const fin = 'La génération n’a pas été relancée.';
  if (effaces.length === 0) {
    const tete = incertain
      ? 'L’effacement n’a pas pu être confirmé.'
      : 'Les heures n’ont pas été effacées.';
    return `${tete} ${raison} ${fin}`;
  }
  const article = effaces.length === 1 ? 'le' : 'les';
  const reste = incertain ? 'Le reste n’a pas pu être confirmé.' : 'Le reste n’a pas pu l’être.';
  return `Heures effacées seulement ${article} ${libelleDesJours(effaces)}. ${reste} ${raison} ${fin}`;
}
