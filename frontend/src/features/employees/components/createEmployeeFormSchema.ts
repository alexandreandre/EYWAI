import { z } from "zod";
import { ibanFieldSchema } from "@/lib/ibanSchema";

export const createEmployeeFormSchema = z.object({
  // --- SECTION SALARIÉ (COMPLÉTÉE) ---
  first_name: z.string().min(2, { message: "Prénom requis." }),
  last_name: z.string().min(2, { message: "Nom requis." }),
  email: z.string().email({ message: "Adresse e-mail invalide." }),
  nir: z.string().length(15, { message: "Le NIR doit faire 15 chiffres." }),
  date_naissance: z.string().refine((d) => d, { message: "Date requise." }),
  lieu_naissance: z.string().min(2, { message: "Lieu de naissance requis." }),
  nationalite: z.string().min(2, { message: "Nationalité requise." }),
  adresse: z.object({
    rue: z.string().min(2, { message: "Rue requise." }),
    code_postal: z.string().min(5, { message: "Code postal requis." }),
    ville: z.string().min(2, { message: "Ville requise." }),
  }),
  coordonnees_bancaires: z.object({
    iban: ibanFieldSchema,
    bic: z.string().min(8, { message: "BIC invalide." }),
  }),
  
  // --- SECTION TITRE DE SÉJOUR (OPTIONNEL) ---
  is_subject_to_residence_permit: z.boolean().optional(),
  residence_permit_expiry_date: z.string().optional(),
  residence_permit_type: z.string().optional(),
  residence_permit_number: z.string().optional(),

  // --- SECTION CONTRAT (COMPLÉTÉE) ---
  hire_date: z.string().refine((d) => !isNaN(Date.parse(d)), { message: "Date invalide." }),
  contract_type: z.string().min(2),
  // Dates spécifiques alternance (optionnelles)
  date_conclusion_contrat: z.string().optional(),
  date_debut_execution: z.string().optional(),
  // Fin de contrat planifiée (CDD / stage) — précarité et prorata de sortie.
  contract_end_date: z.string().optional(),
  statut: z.string().min(2),
  job_title: z.string().min(2),
  /** Équipe (optionnel, vide = aucune) — affecté à la création si supporté par l’API */
  team_id: z.string().optional(),
  has_periode_essai: z.boolean(),
  periode_essai: z
    .object({
      duree_initiale: z.coerce.number().int().positive(),
      unite: z.enum(["jours", "semaines", "mois"]),
      renouvellement_possible: z.boolean(),
    })
    .optional(),
  is_temps_partiel: z.boolean(),
  duree_hebdomadaire: z.coerce.number().positive(),
  
  // --- SECTION RÉMUNÉRATION (COMPLÉTÉE) ---
  salaire_de_base: z.object({
    valeur: z.coerce.number().positive({ message: "Le salaire doit être positif." })
  }),
  classification_conventionnelle: z.object({
    groupe_emploi: z.string().min(1, { message: "Groupe requis." }),
    classe_emploi: z.coerce.number().int(),
    coefficient: z.coerce.number().int().positive({ message: "Coeff. requis." }),
  }),
  collective_agreement_id: z.string().nullable().optional(),

  avantages_en_nature: z.object({
    repas: z.object({
      nombre_par_mois: z.coerce.number().int().min(0),
    }),
    logement: z.object({
      beneficie: z.boolean(),
    }),
    vehicule: z.object({
      beneficie: z.boolean(),
    }),
  }),
  
   // --- SECTION SPÉCIFICITÉS (DÉTAILLÉE) ---
  specificites_paie: z.object({
    is_alsace_moselle: z.boolean(),
    // Apprenti : maintien de l'ancien régime d'exonération (contrat conclu avant
    // le 01/03/2025 mais débutant après). Optionnel.
    maintien_regime_apprenti: z.boolean().optional(),
    personnel_rd_eligible_jei: z.boolean().optional(),
    mandataire_rd: z.boolean().optional(),
    prelevement_a_la_source: z.object({
      is_personnalise: z.boolean(),
      taux: z.coerce.number().min(0).max(100).optional(),
    }),
    transport: z.object({ abonnement_mensuel_total: z.coerce.number().min(0) }),
    titres_restaurant: z.object({
      beneficie: z.boolean(),
      nombre_par_mois: z.coerce.number().int().min(0),
    }),
    mutuelle: z.object({
      mutuelle_type_ids: z.array(z.string()).optional(),
      // Rétrocompatibilité : garder lignes_specifiques pour les anciens employés
      lignes_specifiques: z.array(
        z.object({
          id: z.string().min(1),
          libelle: z.string().min(2),
          montant_salarial: z.coerce.number(),
          montant_patronal: z.coerce.number(),
          part_patronale_soumise_a_csg: z.boolean(),
        })
      ).optional(),
    }),
    // Prévoyance : une adhésion simple, et une liste optionnelle pour les cadres
    prevoyance: z.object({
      adhesion: z.boolean(),
      lignes_specifiques: z.array(
        z.object({
          id: z.string(),
          libelle: z.string().min(2, { message: "Libellé requis." }),
          salarial: z.coerce.number(),
          patronal: z.coerce.number(),
          forfait_social: z.coerce.number(),
        })
      ).optional(),
    }),
  }),
}).superRefine((data, ctx) => {
  if (data.has_periode_essai && !data.periode_essai) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Renseignez la durée de la période d'essai.",
      path: ["periode_essai", "duree_initiale"],
    });
  }
  // Règle de validation personnalisée pour la prévoyance
  if (data.statut?.toLowerCase() === 'cadre' && data.specificites_paie.prevoyance.adhesion) {
    if (!data.specificites_paie.prevoyance.lignes_specifiques || data.specificites_paie.prevoyance.lignes_specifiques.length === 0) {
      // Si aucune ligne n'est ajoutée pour un cadre, on ne met pas d'erreur pour l'instant,
      // mais on pourrait en ajouter une ici si c'était obligatoire.
      return;
    }
    // On vérifie chaque ligne de prévoyance
    data.specificites_paie.prevoyance.lignes_specifiques.forEach((ligne, index) => {
      if (!ligne.libelle) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Le libellé est requis.",
          path: [`specificites_paie`, `prevoyance`, `lignes_specifiques`, index, `libelle`],
        });
      }
    });
  }
});


export type CreateEmployeeFormValues = z.infer<typeof createEmployeeFormSchema>;

export const translateFieldName = (fieldPath: string): string => {
  const translations: Record<string, string> = {
    'email': 'Email',
    'nir': 'Numéro de sécurité sociale',
    'first_name': 'Prénom',
    'last_name': 'Nom',
    'date_naissance': 'Date de naissance',
    'lieu_naissance': 'Lieu de naissance',
    'nationalite': 'Nationalité',
    'hire_date': 'Date d\'embauche',
    'job_title': 'Intitulé du poste',
    'contract_type': 'Type de contrat',
    'statut': 'Statut',
    'adresse.rue': 'Rue',
    'adresse.code_postal': 'Code postal',
    'adresse.ville': 'Ville',
    'coordonnees_bancaires.iban': 'IBAN',
    'coordonnees_bancaires.bic': 'BIC',
    'salaire_de_base.valeur': 'Salaire de base',
    'duree_hebdomadaire': 'Durée hebdomadaire',
  };
  return translations[fieldPath] || fieldPath;
};

