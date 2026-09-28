import { z } from "zod";
import { bicFieldSchema, ibanFieldSchema } from "@/lib/ibanSchema";
import { isEmployeeCadre } from "@/lib/mutuelleUtils";

export const createEmployeeFormSchema = z.object({
  // --- SECTION SALARIÉ ---
  // Le jour de l'embauche, seuls nom, prénom, poste, date d'entrée et salaire
  // sont connus à coup sûr. Le reste peut attendre : la fiche est créée « à
  // compléter » et sa paie reste bloquée tant que manquent NIR, naissance,
  // adresse et RIB. Un champ rempli doit en revanche être juste.
  first_name: z.string().trim().min(2, { message: "Prénom requis." }),
  last_name: z.string().trim().min(2, { message: "Nom requis." }),
  email: z
    .string()
    .trim()
    .optional()
    .default("")
    .refine((v) => !v || z.string().email().safeParse(v).success, { message: "Adresse e-mail invalide." }),
  nir: z
    .string()
    .optional()
    .default("")
    .refine((v) => !v.replace(/\s/g, "") || /^[0-9]{13}[0-9]{2}$|^[12][0-9]{4}2[AB][0-9]{8}$/i.test(v.replace(/\s/g, "")), {
      message: "Le numéro de sécurité sociale fait 15 caractères.",
    }),
  date_naissance: z.string().optional().default(""),
  lieu_naissance: z.string().optional().default(""),
  nationalite: z.string().optional().default(""),
  adresse: z.object({
    rue: z.string().optional().default(""),
    code_postal: z
      .string()
      .optional()
      .default("")
      .refine((v) => !v.trim() || /^[0-9]{5}$/.test(v.trim()), { message: "Code postal à 5 chiffres." }),
    ville: z.string().optional().default(""),
  }),
  coordonnees_bancaires: z.object({
    iban: z
      .string()
      .optional()
      .default("")
      .refine((v) => !v.replace(/\s/g, "") || ibanFieldSchema.safeParse(v).success, { message: "IBAN invalide." }),
    bic: bicFieldSchema,
  }),

  // --- SECTION TITRE DE SÉJOUR (OPTIONNEL) ---
  is_subject_to_residence_permit: z.boolean().optional(),
  residence_permit_expiry_date: z.string().optional(),
  residence_permit_type: z.string().optional(),
  residence_permit_number: z.string().optional(),

  // --- SECTION CONTRAT (COMPLÉTÉE) ---
  hire_date: z.string().refine((d) => !!d && !isNaN(Date.parse(d)), { message: "Date d'entrée requise." }),
  contract_type: z.string().min(2),
  // Dates spécifiques alternance (optionnelles)
  date_conclusion_contrat: z.string().optional(),
  date_debut_execution: z.string().optional(),
  // Fin de contrat planifiée (CDD / stage) — précarité et prorata de sortie.
  contract_end_date: z.string().optional(),
  statut: z.string().min(2),
  is_forfait_jour: z.boolean().default(false),
  job_title: z.string().trim().min(2, { message: "Poste requis." }),
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
    valeur: z.coerce.number({ invalid_type_error: "Salaire requis." }).positive({ message: "Salaire requis." })
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
    transport: z.object({
      abonnement_mensuel_total: z.coerce.number().min(0),
      indemnite_mensuelle_nette: z.coerce.number().min(0).optional().default(0),
    }),
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
  const { rue, code_postal, ville } = data.adresse;
  const remplis = [rue, code_postal, ville].filter((v) => v?.trim()).length;
  if (remplis > 0 && remplis < 3) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Adresse incomplète : rue, code postal et ville, ou rien.",
      path: ["adresse", !rue?.trim() ? "rue" : !code_postal?.trim() ? "code_postal" : "ville"],
    });
  }
  if (data.has_periode_essai && !data.periode_essai) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Renseignez la durée de la période d'essai.",
      path: ["periode_essai", "duree_initiale"],
    });
  }
  if (data.specificites_paie.prevoyance.adhesion) {
    const lignes = data.specificites_paie.prevoyance.lignes_specifiques ?? [];
    lignes.forEach((ligne, index) => {
      if (!ligne.libelle?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Le libellé est requis.",
          path: ["specificites_paie", "prevoyance", "lignes_specifiques", index, "libelle"],
        });
      }
    });
  }
  if (isEmployeeCadre(data.statut) && !data.specificites_paie.prevoyance.adhesion) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Adhésion prévoyance requise pour un cadre.",
      path: ["specificites_paie", "prevoyance", "adhesion"],
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
