import { z } from 'zod';
import { needsContractEndDate } from '@/constants/contracts';
import { ibanFieldSchema } from '@/lib/ibanSchema';

export const employeeProfileEditSchema = z
  .object({
    first_name: z.string().min(2, { message: 'Prénom requis.' }),
    last_name: z.string().min(2, { message: 'Nom requis.' }),
    email: z.string().email({ message: 'Adresse e-mail invalide.' }),
    phone_number: z.string().optional(),
    nir: z.string().length(15, { message: 'Le NIR doit faire 15 chiffres.' }),
    date_naissance: z.string().refine((d) => d && !Number.isNaN(Date.parse(d)), {
      message: 'Date de naissance requise.',
    }),
    lieu_naissance: z.string().min(2, { message: 'Lieu de naissance requis.' }),
    nationalite: z.string().min(2, { message: 'Nationalité requise.' }),
    adresse: z.object({
      rue: z.string().min(2, { message: 'Rue requise.' }),
      code_postal: z.string().min(5, { message: 'Code postal requis.' }),
      ville: z.string().min(2, { message: 'Ville requise.' }),
    }),
    coordonnees_bancaires: z.object({
      iban: ibanFieldSchema,
      bic: z.string().min(8, { message: 'BIC invalide.' }),
    }),
    hire_date: z.string().refine((d) => d && !Number.isNaN(Date.parse(d)), {
      message: "Date d'entrée requise.",
    }),
    job_title: z.string().min(2, { message: 'Intitulé du poste requis.' }),
    contract_type: z.string().min(2, { message: 'Type de contrat requis.' }),
    statut: z.string().min(2, { message: 'Statut requis.' }),
    is_temps_partiel: z.boolean(),
    duree_hebdomadaire: z.coerce.number().positive({ message: 'Durée hebdomadaire requise.' }),
    contract_end_date: z.string().optional(),
    date_debut_execution: z.string().optional(),
    date_conclusion_contrat: z.string().optional(),
    salaire_de_base: z.object({
      valeur: z.coerce.number().positive({ message: 'Le salaire doit être positif.' }),
    }),
    collective_agreement_id: z.string().nullable().optional(),
    classification_conventionnelle: z.object({
      groupe_emploi: z.string().min(1, { message: 'Groupe requis.' }),
      classe_emploi: z.coerce.number().int(),
      coefficient: z.coerce.number().int().positive({ message: 'Coefficient requis.' }),
    }),
    team_id: z.string().optional(),
    specificites_paie: z.object({
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
      }),
      prevoyance: z.object({
        adhesion: z.boolean(),
      }),
      maintien_regime_apprenti: z.boolean().optional(),
      personnel_rd_eligible_jei: z.boolean().optional(),
    }),
    is_subject_to_residence_permit: z.boolean(),
    residence_permit_expiry_date: z.string().optional(),
    residence_permit_type: z.string().optional(),
    residence_permit_number: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    if (needsContractEndDate(data.contract_type) && !data.contract_end_date?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Date de fin de contrat requise pour un CDD ou un stage.',
        path: ['contract_end_date'],
      });
    }
    if (data.collective_agreement_id && !data.classification_conventionnelle.groupe_emploi) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Classification conventionnelle requise.',
        path: ['classification_conventionnelle', 'groupe_emploi'],
      });
    }
    if (data.statut.toLowerCase() === 'cadre' && !data.specificites_paie.prevoyance.adhesion) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Adhésion prévoyance requise pour un cadre.',
        path: ['specificites_paie', 'prevoyance', 'adhesion'],
      });
    }
    if (data.is_subject_to_residence_permit && !data.residence_permit_expiry_date?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Date d'expiration du titre de séjour requise.",
        path: ['residence_permit_expiry_date'],
      });
    }
  });

export type EmployeeProfileEditFormValues = z.infer<typeof employeeProfileEditSchema>;
