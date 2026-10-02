/**
 * Appliquer au formulaire de création les valeurs de la société.
 *
 * La fenêtre proposait des valeurs génériques (salaire 2 365,66 €, coefficient
 * 240, titres-restaurant cochés, aucune mutuelle) ; on part de ce que portent les
 * salariés actifs de la société. Le salaire n'est jamais proposé : il est propre à
 * chaque embauche, et un montant prérempli passerait inaperçu.
 */
import type { ValeursEmbauche } from '@/api/employees';
import type { CreateEmployeeFormValues } from '@/features/employees/components/createEmployeeFormSchema';

export function mutuellesPourStatut(valeurs: ValeursEmbauche | null | undefined, statut: string): string[] {
  if (!valeurs) return [];
  const cle = statut?.toLowerCase() === 'cadre' ? 'Cadre' : 'Non-Cadre';
  return [...(valeurs.mutuelle_type_ids_par_statut?.[cle] ?? [])];
}

export function avecValeursDeLaSociete(
  base: CreateEmployeeFormValues,
  valeurs: ValeursEmbauche | null | undefined
): CreateEmployeeFormValues {
  if (!valeurs) return base;
  const statut = valeurs.statut || base.statut;
  const classification = valeurs.classification_conventionnelle;
  return {
    ...base,
    statut,
    contract_type: valeurs.contract_type || base.contract_type,
    duree_hebdomadaire: valeurs.duree_hebdomadaire ?? base.duree_hebdomadaire,
    collective_agreement_id: valeurs.collective_agreement_id ?? base.collective_agreement_id,
    classification_conventionnelle: classification
      ? {
          groupe_emploi: classification.groupe_emploi || base.classification_conventionnelle.groupe_emploi,
          classe_emploi: classification.classe_emploi ?? classification.coefficient,
          coefficient: classification.coefficient,
        }
      : base.classification_conventionnelle,
    specificites_paie: {
      ...base.specificites_paie,
      salaire_hors_hs_structurelles: valeurs.salaire_hors_hs_structurelles ?? false,
      titres_restaurant: {
        ...base.specificites_paie.titres_restaurant,
        beneficie: valeurs.titres_restaurant_beneficie,
      },
      mutuelle: {
        ...base.specificites_paie.mutuelle,
        mutuelle_type_ids: mutuellesPourStatut(valeurs, statut),
      },
      prevoyance: {
        ...base.specificites_paie.prevoyance,
        adhesion: valeurs.prevoyance_adhesion,
      },
    },
  };
}

/** Le planning posé, en clair : « septembre à décembre 2026 ». */
export function moisEnClair(mois: string[] | undefined): string | null {
  if (!mois?.length) return null;
  const nom = (m: string) => {
    const [annee, numero] = m.split('-').map(Number);
    return new Date(annee, numero - 1, 1).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
  };
  const tries = [...mois].sort();
  if (tries.length === 1) return nom(tries[0]);
  return `${nom(tries[0]).split(' ')[0]} à ${nom(tries[tries.length - 1])}`;
}

type Classification = { groupe_emploi: string; classe_emploi: number; coefficient: number };

const cleClassification = (c: Partial<Classification>) => `${c.groupe_emploi}-${c.classe_emploi}-${c.coefficient}`;

/**
 * La grille de la convention, plus la classification que portent déjà les
 * salariés de la société si elle n'y figure pas (Colorplast : « C / 710 » alors
 * que la grille de test ne connaît que « Non précisé / 700, 710, 720 »).
 */
export function grilleAvecClassificationHabituelle<T extends Classification>(
  grille: T[],
  habituelle: Classification | null | undefined
): Classification[] {
  if (!habituelle || grille.some((c) => cleClassification(c) === cleClassification(habituelle))) return grille;
  return [habituelle, ...grille];
}

export { cleClassification };

/** L'onglet du formulaire qui porte un champ, pour y conduire en cas d'erreur. */
export function ongletDuChamp(chemin: string): string {
  const racine = chemin.split('.')[0];
  if (['salaire_de_base', 'collective_agreement_id', 'classification_conventionnelle'].includes(racine)) return 'remuneration';
  if (racine === 'avantages_en_nature') return 'avantages';
  if (racine === 'specificites_paie') return 'specifiques';
  if (
    [
      'hire_date', 'job_title', 'contract_type', 'statut', 'is_forfait_jour', 'has_periode_essai', 'periode_essai',
      'date_conclusion_contrat', 'date_debut_execution', 'contract_end_date', 'is_temps_partiel', 'duree_hebdomadaire',
    ].includes(racine)
  )
    return 'contrat';
  return 'collaborateur';
}

const NOMS_DES_CHAMPS: Record<string, string> = {
  first_name: 'Prénom',
  last_name: 'Nom',
  email: 'E-mail',
  nir: 'N° de sécurité sociale',
  date_naissance: 'Date de naissance',
  lieu_naissance: 'Lieu de naissance',
  nationalite: 'Nationalité',
  'adresse.rue': 'Rue',
  'adresse.code_postal': 'Code postal',
  'adresse.ville': 'Ville',
  'coordonnees_bancaires.iban': 'IBAN',
  'coordonnees_bancaires.bic': 'BIC',
  hire_date: "Date d'entrée",
  job_title: 'Intitulé du poste',
  contract_end_date: 'Date de fin de contrat',
  duree_hebdomadaire: 'Durée hebdomadaire',
  'salaire_de_base.valeur': 'Salaire de base',
  'classification_conventionnelle.coefficient': 'Coefficient',
  'classification_conventionnelle.groupe_emploi': 'Groupe',
  'periode_essai.duree_initiale': "Durée de la période d'essai",
  residence_permit_expiry_date: "Date d'expiration du titre de séjour",
  'specificites_paie.prevoyance.adhesion': 'Prévoyance',
};

export type ErreurDeChamp = { chemin: string; message: string };

/** Les erreurs de validation à plat, dans l'ordre du formulaire. */
export function erreursAPlat(erreurs: unknown, chemin = ''): ErreurDeChamp[] {
  if (!erreurs || typeof erreurs !== 'object') return [];
  const e = erreurs as Record<string, unknown>;
  if (typeof e.message === 'string' && e.message) return [{ chemin, message: e.message }];
  return Object.keys(e)
    .filter((k) => k !== 'ref' && k !== 'type')
    .flatMap((k) => erreursAPlat(e[k], chemin ? `${chemin}.${k}` : k));
}

const ORDRE_DES_ONGLETS = ['collaborateur', 'contrat', 'remuneration', 'avantages', 'specifiques'];

/** Dans l'ordre du formulaire : onglet après onglet. */
export function erreursDansLOrdre(erreurs: ErreurDeChamp[]): ErreurDeChamp[] {
  const rang = (e: ErreurDeChamp) => ORDRE_DES_ONGLETS.indexOf(ongletDuChamp(e.chemin));
  return [...erreurs].sort((a, b) => rang(a) - rang(b));
}

export function libelleDErreur({ chemin, message }: ErreurDeChamp): string {
  const nom = NOMS_DES_CHAMPS[chemin];
  return nom ? `${nom} : ${message}` : message;
}

type Envoi = Record<string, unknown> & {
  adresse?: { rue?: string; code_postal?: string; ville?: string } | null;
  coordonnees_bancaires?: { iban?: string; bic?: string } | null;
};

/** Ce qui n'est pas renseigné part vide (null), jamais en chaîne vide. */
export function champsFacultatifsPourEnvoi<T extends Envoi>(valeurs: T): T {
  const texte = (v: unknown) => (typeof v === 'string' && v.trim() ? v.trim() : null);
  const adresse = valeurs.adresse;
  const adresseRemplie = adresse && [adresse.rue, adresse.code_postal, adresse.ville].every((v) => v?.trim());
  const iban = valeurs.coordonnees_bancaires?.iban?.replace(/\s/g, '').toUpperCase();
  const nir = typeof valeurs.nir === 'string' ? valeurs.nir.replace(/\s/g, '').toUpperCase() : '';
  return {
    ...valeurs,
    email: texte(valeurs.email)?.toLowerCase() ?? null,
    nir: nir || null,
    date_naissance: texte(valeurs.date_naissance),
    lieu_naissance: texte(valeurs.lieu_naissance),
    nationalite: texte(valeurs.nationalite),
    adresse: adresseRemplie
      ? { rue: adresse!.rue!.trim(), code_postal: adresse!.code_postal!.trim(), ville: adresse!.ville!.trim() }
      : null,
    coordonnees_bancaires: iban
      ? { iban, bic: valeurs.coordonnees_bancaires?.bic?.replace(/\s/g, '').toUpperCase() ?? '' }
      : null,
  };
}
