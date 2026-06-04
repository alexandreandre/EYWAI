const RATE_KEY_LABELS: Record<string, string> = {
  // Catégories
  smic: 'SMIC',
  pss: 'Plafond Sécurité Sociale (PSS)',
  ij_plafonds: 'Plafonds IJSS',
  cotisations: 'Cotisations sociales',
  pas: 'Prélèvement à la source (PAS)',
  frais_pro: 'Frais professionnels',
  avantages_en_nature: 'Avantages en nature',
  heures_supp: 'Heures supplémentaires',
  heures_supplementaires: 'Heures supplémentaires',
  primes: 'Primes',
  baremes_km: 'Barème kilométrique',
  alternance: 'Alternance (apprentis / pro)',
  reduction_generale: 'Réduction générale (RGDU 2026)',

  // Réduction générale dégressive unique (RGDU)
  actif: 'Dispositif actif',
  type: 'Type de dispositif',
  point_sortie_smic: 'Point de sortie (× SMIC)',
  p: 'Exposant de dégressivité (P)',
  tmin: 'Tmin (taux plancher)',
  tdelta: 'Tdelta (amplitude)',
  fnal_moins_50: 'FNAL < 50 salariés',
  fnal_50_et_plus: 'FNAL ≥ 50 salariés',

  // Alternance
  apprenti: 'Apprenti',
  professionnalisation: 'Professionnalisation',
  regimes: 'Régimes par date',
  plafond_exoneration_pct_smic: 'Plafond exonération (% SMIC)',
  csg_crds_assujettie_au_dela_plafond: 'CSG/CRDS au-delà du plafond',
  abattement_csg_frais_pro: 'Abattement CSG frais pro',
  cotisations_exclues_exoneration: 'Cotisations toujours dues',
  exoneration_ir: 'Exonération impôt sur le revenu',
  plafond_annuel_pct_smic: 'Plafond annuel (% SMIC)',
  date_execution_min: 'Exécution à partir du',
  date_execution_max: "Exécution jusqu'au",

  // SMIC / PSS
  annee: 'Année',
  cas_general: 'Cas général',
  entre_17_et_18_ans: 'Jeune 17 ans',
  jeune_17_ans: 'Jeune 17 ans',
  moins_de_17_ans: 'Jeune moins de 17 ans',
  jeune_moins_17_ans: 'Jeune moins de 17 ans',
  smic_horaire_brut: 'SMIC horaire brut',
  smic_mensuel_brut: 'SMIC mensuel brut (35h/sem)',
  smic_horaire: 'SMIC horaire',
  date_application: 'Applicable au',
  annuel: 'Annuel',
  mensuel: 'Mensuel',
  journalier: 'Journalier',
  quinzaine: 'Quinzaine',
  trimestriel: 'Trimestriel',
  hebdomadaire: 'Hebdomadaire',

  // IJSS
  at_mp: 'AT/MP',
  at_mp_majoree: 'AT/MP majorée',
  maternite_paternite: 'Maternité / paternité',
  maladie: 'Maladie',
  plafonds_indemnites_journalieres: 'Plafonds indemnités journalières',

  // Bases de cotisation
  assiette_cet: 'Assiette CET',
  brut: 'Brut',
  autre: 'Autre',
  brut_cadre_4_plafonds: 'Brut cadre (4 plafonds)',
  brut_plafonne: 'Brut plafonné',
  tranche_2: 'Tranche 2',

  // Frais professionnels
  repas: 'Repas (indemnité journalière)',
  sur_lieu_travail: 'Repas sur le lieu de travail',
  hors_locaux_avec_restaurant: 'Repas hors locaux — restaurant d’entreprise',
  hors_locaux_sans_restaurant: 'Repas hors locaux — sans restaurant d’entreprise',
  teletravail: 'Télétravail',
  indemnite_avec_accord: 'Indemnité avec accord',
  indemnite_sans_accord: 'Indemnité sans accord',
  par_jour: 'Par jour',
  limite_mensuelle: 'Limite mensuelle',
  par_mois_pour_1_jour_semaine: 'Par mois (1 jour/semaine)',
  materiel_informatique_perso: 'Matériel informatique personnel',
  montant_mensuel: 'Montant mensuel',
  mobilite_durable: 'Mobilité durable',
  employeurs_prives: 'Employeurs privés',
  employeurs_publics: 'Employeurs publics',
  limite_base: 'Limite de base',
  limite_cumul_transport_public: 'Limite cumul transport public',
  limite_cumul_carburant_total: 'Limite cumul carburant (total)',
  limite_cumul_carburant_part_carburant: 'Limite cumul carburant (part carburant)',
  jours_utilises: 'Jours utilisés',
  montant_annuel: 'Montant annuel',
  grand_deplacement: 'Grand déplacement',
  metropole: 'Métropole',
  outre_mer_groupe1: 'Outre-mer — groupe 1',
  outre_mer_groupe2: 'Outre-mer — groupe 2',
  petit_deplacement: 'Petit déplacement',
  km_min: 'Km min.',
  km_max: 'Km max.',
  montant: 'Indemnité forfaitaire',
  periode_sejour: 'Période de séjour',
  logement_paris_banlieue: 'Logement Paris / banlieue',
  logement_province: 'Logement province',
  hebergement: 'Hébergement',
  mutation_professionnelle: 'Mutation professionnelle',
  hebergement_provisoire: 'Hébergement provisoire',
  hebergement_definitif: 'Hébergement définitif',
  montant_par_jour: 'Montant par jour',
  frais_installation: 'Frais d’installation',
  majoration_par_enfant: 'Majoration par enfant',
  plafond_total: 'Plafond total',

  // Avantages en nature
  repas_valeur_forfaitaire: 'Repas — valeur forfaitaire (1 repas)',
  repas_valeur_forfaitaire_eur: 'Repas — valeur forfaitaire (1 repas)',
  /** Clé courte URSSAF (payroll_config.avantages_en_nature.repas) — ne pas confondre avec frais pro. */
  repas_aen: 'Repas pris en charge par l\'employeur',
  titre_aen: 'Titre-restaurant',
  titre: 'Titre-restaurant — exonération max. part patronale',
  titre_restaurant: 'Titre-restaurant — exonération max. part patronale',
  titre_restaurant_exoneration_max_patronale:
    'Titre-restaurant — exonération max. part patronale',
  titre_restaurant_exoneration_max_eur:
    'Titre-restaurant — exonération max. part patronale',
  logement: 'Logement',
  valeur_1_piece_eur: 'Valeur 1 pièce (€)',
  remuneration_max_eur: 'Rémunération max. (€)',
  valeur_par_piece_suppl_eur: 'Valeur par pièce suppl. (€)',

  // Primes
  id: 'Identifiant',
  libelle: 'Libellé',
  soumise_a_impot: 'Soumise à l’impôt',
  soumise_a_cotisations: 'Soumise aux cotisations',
  prime_exceptionnelle: 'Prime exceptionnelle',
  commentaire: 'Commentaire',

  // Champs de cotisation
  patronal: 'Patronal',
  salarial: 'Salarial',
  patronal_plein: 'Patronal — taux plein',
  patronal_reduit: 'Patronal — taux réduit',
  salarial_alsace_moselle: 'Salarial — Alsace-Moselle',
};

/** Valeurs patronales non numériques dans cotisations.json (taux gérés ailleurs). */
export const COTISATION_PATRONAL_MARKERS: Record<string, string> = {
  specifique_entreprise: 'Taux défini dans la fiche entreprise',
};

const PAS_ZONE_LABELS: Record<string, string> = {
  metropole: 'Métropole et hors de France',
  guadeloupe_reunion_martinique: 'Guadeloupe, La Réunion, Martinique',
  guyane_mayotte: 'Guyane et Mayotte',
  grm: 'Guadeloupe, La Réunion, Martinique',
  gm: 'Guyane et Mayotte',
};

const PERIODE_SEJOUR_LABELS: Record<string, string> = {
  'pour les 3 premiers mois': 'Pour les 3 premiers mois',
  '3 premiers mois': 'Pour les 3 premiers mois',
  'au-delà du 3emois et jusqu’au 24emois': 'Au-delà du 3e mois et jusqu’au 24e mois',
  'au-delà du 3 emois et jusqu’au 24 emois': 'Au-delà du 3e mois et jusqu’au 24e mois',
  'au-delà du 24emois et jusqu’au 72emois': 'Au-delà du 24e mois et jusqu’au 72e mois',
  'au-delà du 24 emois et jusqu’au 72 emois': 'Au-delà du 24e mois et jusqu’au 72e mois',
  'au-delà de 3 mois': 'Au-delà de 3 mois',
  'au-delà de 24 mois': 'Au-delà de 24 mois',
  forfait: 'Forfait',
};

const ACRONYMS = new Set([
  'smic',
  'pss',
  'ijss',
  'pas',
  'csg',
  'crds',
  'cet',
  'ceg',
  'apec',
  'ags',
  'fnal',
  'csa',
  'cfp',
  'apec',
  'mp',
  'at',
  'ij',
  'urssaf',
  'km',
  'id',
]);

const WORD_LABELS: Record<string, string> = {
  annee: 'année',
  general: 'général',
  maternite: 'maternité',
  paternite: 'paternité',
  periode: 'période',
  sejour: 'séjour',
  hebergement: 'hébergement',
  indemnite: 'indemnité',
  teletravail: 'télétravail',
  materiel: 'matériel',
  metropole: 'métropole',
  deplacement: 'déplacement',
  plafonne: 'plafonné',
  plafond: 'plafond',
  libelle: 'libellé',
  impot: 'impôt',
  majoree: 'majorée',
  definitif: 'définitif',
  utilises: 'utilisés',
  mobilite: 'mobilité',
  professionnelle: 'professionnelle',
  remuneration: 'rémunération',
  piece: 'pièce',
  suppl: 'suppl.',
  informatique: 'informatique',
  perso: 'personnel',
  provisoire: 'provisoire',
  installation: 'installation',
  majoration: 'majoration',
  exceptionnelle: 'exceptionnelle',
  soumise: 'soumise',
  cotisations: 'cotisations',
  supplementaires: 'supplémentaires',
  journalieres: 'journalières',
  indemnites: 'indemnités',
};

function slugifyKey(key: string): string {
  return key.trim().toLowerCase().replace(/\s+/g, '_');
}

function formatWord(word: string): string {
  const lower = word.toLowerCase();
  if (ACRONYMS.has(lower)) return lower.toUpperCase();
  if (WORD_LABELS[lower]) return WORD_LABELS[lower];
  if (/^\d+$/.test(lower)) return lower;
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function formatFallbackLabel(key: string): string {
  const normalized = key
    .trim()
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .replace('taux moins 50', 'Taux < 50')
    .replace('taux 50 et plus', 'Taux 50+')
    .replace(/^patronal\s+/i, '')
    .replace(/^salarial\s+/i, '');

  return normalized
    .split(' ')
    .filter(Boolean)
    .map(formatWord)
    .join(' ');
}

export function formatRateKey(key: string): string {
  const slug = slugifyKey(key);
  if (RATE_KEY_LABELS[slug]) return RATE_KEY_LABELS[slug];
  return formatFallbackLabel(key);
}

export function getCategoryTitle(key: string): string {
  const slug = slugifyKey(key);
  if (RATE_KEY_LABELS[slug]) return RATE_KEY_LABELS[slug];
  return formatFallbackLabel(key);
}

const COTISATION_ID_LABELS: Record<string, string> = {
  retraite_comp_t1: 'Retraite complémentaire T1',
  retraite_comp_t2: 'Retraite complémentaire T2',
  ceg_t1: 'CEG T1',
  ceg_t2: 'CEG T2',
  cet: 'CET',
  apec: 'APEC',
  retraite_secu_plafond: 'Vieillesse plafonnée',
  retraite_secu_deplafond: 'Vieillesse déplafonnée',
  securite_sociale_maladie: 'MMID (maladie)',
  taxe_apprentissage: 'Taxe d’apprentissage (part principale)',
  taxe_apprentissage_solde: 'Taxe d’apprentissage (solde)',
};

/** Libellé court pour bandeau / toast de sync ciblée sur une ligne de cotisation. */
export function getCotisationTitle(cotisationId: string): string {
  const slug = slugifyKey(cotisationId);
  if (COTISATION_ID_LABELS[slug]) return COTISATION_ID_LABELS[slug];
  return formatFallbackLabel(cotisationId);
}

export function formatPasZone(zone: string): string {
  const slug = slugifyKey(zone);
  return PAS_ZONE_LABELS[slug] ?? formatRateKey(zone);
}

const REPAS_FORFAIT_KEYS = new Set([
  'sur_lieu_travail',
  'hors_locaux_avec_restaurant',
  'hors_locaux_sans_restaurant',
]);

const EUR_PER_TITRE_KEYS = new Set([
  'titre',
  'titre_restaurant',
  'titre_restaurant_exoneration_max_patronale',
  'titre_restaurant_exoneration_max_eur',
]);

/** Suffixe affiché après le montant (ex. « / jour »). Chaîne vide = montant seul en €. */
const RATE_VALUE_SUFFIX: Record<string, string> = {
  sur_lieu_travail: '/ repas',
  hors_locaux_avec_restaurant: '/ repas',
  hors_locaux_sans_restaurant: '/ repas',
  repas_valeur_forfaitaire: '/ repas',
  repas_valeur_forfaitaire_eur: '/ repas',
  repas: '/ jour',
  par_jour: '/ jour',
  montant_par_jour: '/ jour',
  hebergement: '/ jour',
  logement_paris_banlieue: '/ jour',
  logement_province: '/ jour',
  limite_mensuelle: '/ mois',
  montant_mensuel: '/ mois',
  par_mois_pour_1_jour_semaine: '/ mois',
  montant_annuel: '/ an',
  limite_base: '/ an',
  limite_cumul_transport_public: '/ an',
  limite_cumul_carburant_total: '/ an',
  limite_cumul_carburant_part_carburant: '/ an',
  plafond_total: '',
  frais_installation: '',
  majoration_par_enfant: '/ enfant',
  montant: '/ trajet',
  valeur_1_piece_eur: '',
  remuneration_max_eur: '',
  valeur_par_piece_suppl_eur: '',
};

export function getRateValueSuffix(key: string): string | null {
  const slug = slugifyKey(key);
  if (slug === 'km_min' || slug === 'km_max') return 'km';
  if (RATE_VALUE_SUFFIX[slug] !== undefined) return RATE_VALUE_SUFFIX[slug];
  if (EUR_PER_TITRE_KEYS.has(slug)) return '/ titre';
  if (slug.includes('_eur') || slug.includes('montant') || slug.includes('limite') || slug.includes('plafond') || slug.includes('frais') || slug.includes('majoration')) {
    return '';
  }
  return null;
}

export function formatEurAmount(value: unknown): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

function fixOrdinalMonths(text: string): string {
  return text
    .replace(/(\d+)emois/gi, '$1e mois')
    .replace(/(\d+) emois/gi, '$1e mois')
    .replace(/\b(\d+)e mois\b/gi, (_, n: string) => `${n}e mois`);
}

function formatNumericRateValue(value: number, key?: string): string {
  const slugKey = key ? slugifyKey(key) : '';
  if (slugKey === 'km_min' || slugKey === 'km_max') {
    return `${value} km`;
  }
  const suffix = slugKey ? getRateValueSuffix(slugKey) : null;
  if (suffix === 'km') {
    return `${value} km`;
  }
  if (suffix !== null) {
    const amount = formatEurAmount(value);
    return suffix ? `${amount} ${suffix}` : amount;
  }
  return String(value);
}

/** Clés sans unité monétaire (ex. année du barème). */
export function isRateKeyUnitless(key: string): boolean {
  const slug = slugifyKey(key);
  return slug === 'annee' || slug === 'date_application';
}

function scalarSectionsOnly(
  sections: Record<string, unknown>,
  legacyWrapperKey: string,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(sections).filter(
      ([k, v]) =>
        k !== legacyWrapperKey && (v === null || typeof v !== 'object'),
    ),
  );
}

/** Sections SMIC à afficher : priorité au format plat post-scraping, pas au wrapper legacy. */
export function resolveSmicSections(
  configData: Record<string, unknown>,
): Record<string, unknown> {
  let base: Record<string, unknown>;
  if (
    typeof configData.cas_general === 'number' ||
    typeof configData.smic_horaire_brut === 'number'
  ) {
    base = configData;
  } else {
    const nested = configData.smic_horaire;
    if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
      base = nested as Record<string, unknown>;
    } else {
      base = configData;
    }
  }
  return scalarSectionsOnly(base, 'smic_horaire');
}

function smicRatesNearlyEqual(a: unknown, b: unknown): boolean {
  if (a == null || b == null) return false;
  const na = Number(a);
  const nb = Number(b);
  if (!Number.isFinite(na) || !Number.isFinite(nb)) return false;
  return Math.abs(na - nb) < 0.005;
}

/**
 * Lignes SMIC pour la carte Suivi des taux — sans doublons (cas général = SMIC horaire brut).
 */
export function buildSmicDisplaySections(
  configData: Record<string, unknown>,
): Record<string, unknown> {
  const base = resolveSmicSections(configData);
  const out: Record<string, unknown> = {};

  const casGeneral =
    base.cas_general ?? base.smic_horaire_brut ?? base.smic_horaire;
  if (casGeneral != null) {
    out.smic_horaire_brut = casGeneral;
  }

  const effectiveFrom = base.effective_from;
  if (typeof effectiveFrom === 'string' && effectiveFrom.trim()) {
    out.date_application = formatIsoDateFr(effectiveFrom);
  }

  const jeune17 = base.jeune_17_ans ?? base.entre_17_et_18_ans;
  if (jeune17 != null && !smicRatesNearlyEqual(jeune17, casGeneral)) {
    out.jeune_17_ans = jeune17;
  }

  const jeuneMoins17 = base.jeune_moins_17_ans ?? base.moins_de_17_ans;
  if (
    jeuneMoins17 != null &&
    !smicRatesNearlyEqual(jeuneMoins17, casGeneral) &&
    !smicRatesNearlyEqual(jeuneMoins17, jeune17)
  ) {
    out.jeune_moins_17_ans = jeuneMoins17;
  }

  if (base.smic_mensuel_brut != null) {
    out.smic_mensuel_brut = base.smic_mensuel_brut;
  }

  return out;
}

const IJ_PLAFONDS_DISPLAY_KEYS = [
  'at_mp',
  'maladie',
  'at_mp_majoree',
  'maternite_paternite',
] as const;

/** Sections IJSS : priorité au sous-bloc plafonds_indemnites_journalieres. */
export function resolveIjPlafondsSections(
  configData: Record<string, unknown>,
): Record<string, unknown> {
  const nested = configData.plafonds_indemnites_journalieres;
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    return nested as Record<string, unknown>;
  }
  if (
    typeof configData.maladie === 'number' ||
    typeof configData.at_mp === 'number'
  ) {
    return configData;
  }
  return configData;
}

/** Lignes plafonds IJSS pour la carte Suivi des taux — sans métadonnées (unite, etc.). */
export function buildIjPlafondsDisplaySections(
  configData: Record<string, unknown>,
): Record<string, unknown> {
  const base = resolveIjPlafondsSections(configData);
  const out: Record<string, unknown> = {};
  for (const key of IJ_PLAFONDS_DISPLAY_KEYS) {
    const value = base[key];
    if (value != null && typeof value === 'number') {
      out[key] = value;
    }
  }
  return out;
}

/** Sections PSS : priorité au format plat (annuel, mensuel, …). */
export function resolvePssSections(
  configData: Record<string, unknown>,
): Record<string, unknown> {
  let base: Record<string, unknown>;
  if (
    typeof configData.annuel === 'number' ||
    typeof configData.mensuel === 'number' ||
    typeof configData.horaire === 'number'
  ) {
    base = configData;
  } else {
    const nested = configData.pss;
    if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
      base = nested as Record<string, unknown>;
    } else {
      base = configData;
    }
  }
  return scalarSectionsOnly(base, 'pss');
}

export function formatRateDisplayValue(value: unknown, key?: string): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Oui' : 'Non';
  if (typeof value === 'number') {
    if (key && isRateKeyUnitless(key)) {
      return String(Math.round(value));
    }
    return formatNumericRateValue(value, key);
  }

  const text = String(value).trim();
  if (!text) return '—';

  const slugKey = key ? slugifyKey(key) : '';
  if (slugKey === 'periode_sejour' || slugKey === 'jours_utilises') {
    const normalized = text.toLowerCase();
    if (PERIODE_SEJOUR_LABELS[normalized]) return PERIODE_SEJOUR_LABELS[normalized];
    return fixOrdinalMonths(text.charAt(0).toUpperCase() + text.slice(1));
  }

  if (slugKey === 'libelle') return text;

  return text;
}

export function getRateValueUnit(key: string, defaultUnit?: string): string | undefined {
  const suffix = getRateValueSuffix(key);
  if (suffix === 'km') return 'km';
  if (suffix === null) return defaultUnit;
  if (suffix === '') return '€';
  return `€ ${suffix}`;
}

/** Titre lisible pour une ligne de barème (petit / grand déplacement, mobilité publique). */
export function formatFraisProArrayItemTitle(
  item: Record<string, unknown>,
  index: number,
): string {
  if (typeof item.km_min === 'number' && typeof item.km_max === 'number') {
    return `De ${item.km_min} à ${item.km_max} km`;
  }
  if (item.periode_sejour != null && item.periode_sejour !== '') {
    const label = formatRateDisplayValue(item.periode_sejour, 'periode_sejour');
    if (label !== '—') return label;
  }
  if (item.jours_utilises != null && item.jours_utilises !== '') {
    const label = formatRateDisplayValue(item.jours_utilises, 'jours_utilises');
    if (label !== '—') return label;
  }
  return `Élément ${index + 1}`;
}

/** Indemnités repas URSSAF (frais pro) : 3 situations forfaitaires. */
export const REPAS_FORFAIT_SITUATION_KEYS = [
  'sur_lieu_travail',
  'hors_locaux_avec_restaurant',
  'hors_locaux_sans_restaurant',
] as const;

/** Lignes forfaitaires avantages en nature (repas, titre-restaurant). */
export const AVANTAGES_EN_NATURE_FORFAIT_ROWS = [
  {
    keys: ['repas', 'repas_valeur_forfaitaire_eur', 'repas_valeur_forfaitaire'],
    label: 'Repas pris en charge par l\'employeur',
    hint: 'Valeur forfaitaire URSSAF pour 1 repas (base d\'évaluation de l\'avantage)',
    unit: '/ repas',
  },
  {
    keys: [
      'titre',
      'titre_restaurant',
      'titre_restaurant_exoneration_max_eur',
      'titre_restaurant_exoneration_max_patronale',
    ],
    label: 'Titre-restaurant',
    hint: 'Plafond d\'exonération sociale et fiscale — part patronale par titre',
    unit: '/ titre',
  },
] as const;

export function pickAvantagesEnNatureValue(
  data: Record<string, unknown>,
  keys: readonly string[],
): unknown {
  for (const key of keys) {
    const value = data[key];
    if (value !== null && value !== undefined) return value;
  }
  return undefined;
}

export function formatAvantagesEnNatureAmount(value: unknown, unit: string): string {
  const amount = formatEurAmount(value);
  return unit ? `${amount} ${unit}` : amount;
}

/** Taux décimal paie (0,25 → 25 % ; 0,1131 → 11,31 %). */
export function formatPayrollPercent(value: unknown): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  const pct = num <= 1 && num >= 0 ? num * 100 : num;
  return `${pct.toFixed(2).replace('.', ',')} %`;
}

/** Date ISO (AAAA-MM-JJ) → affichage français court. */
export function formatIsoDateFr(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  const text = String(value).trim();
  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) {
    const d = new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString('fr-FR', { dateStyle: 'medium' });
    }
  }
  return text;
}

export function formatEffectifRange(min: unknown, max: unknown): string {
  const minN = Number(min);
  const maxN = Number(max);
  if (Number.isFinite(minN) && Number.isFinite(maxN)) {
    return `${minN} à ${maxN} salariés`;
  }
  if (Number.isFinite(minN)) return `À partir de ${minN} salariés`;
  if (Number.isFinite(maxN)) return `Jusqu'à ${maxN} salariés`;
  return '—';
}

export function formatHeuresSupPlage(deHeure: unknown, aHeure: unknown): string {
  const de = Number(deHeure);
  const a = aHeure === null || aHeure === undefined ? null : Number(aHeure);
  if (Number.isFinite(de) && a !== null && Number.isFinite(a)) {
    if (de === a) return `${de}${de === 1 ? 're' : 'e'} heure supplémentaire`;
    return `Heures ${de} à ${a}`;
  }
  if (Number.isFinite(de)) {
    return `À partir de la ${de}${de === 1 ? 're' : 'e'} heure supplémentaire`;
  }
  return '—';
}

export function isRepasForfaitRecord(obj: unknown): obj is Record<string, number> {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return false;
  const keys = Object.keys(obj as Record<string, unknown>);
  if (keys.length === 0) return false;
  return keys.every(
    (k) => REPAS_FORFAIT_KEYS.has(k) && typeof (obj as Record<string, unknown>)[k] === 'number',
  );
}
