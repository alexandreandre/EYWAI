import { z } from 'zod';

/**
 * Titres-restaurant d'une fiche ([B5], 12/10/2026).
 *
 * Le moteur retient du net à payer (valeur du titre − part patronale) × nombre
 * (`calcul_net.py`). Sans ces deux montants à l'écran, la case n'avait aucun
 * effet sur le bulletin.
 */
export const titresRestaurantSchema = z
  .object({
    beneficie: z.boolean(),
    nombre_par_mois: z.coerce.number().int().min(0),
    valeur_faciale: z.coerce.number().min(0).optional().default(0),
    part_patronale: z.coerce.number().min(0).optional().default(0),
  })
  .superRefine((tr, ctx) => {
    if (!tr.beneficie || tr.nombre_par_mois <= 0) return;
    if (!(tr.valeur_faciale > 0)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['valeur_faciale'],
        message: 'Indiquez la valeur d’un titre (en euros).',
      });
    }
    if (tr.part_patronale > tr.valeur_faciale) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['part_patronale'],
        message: 'La part patronale ne peut pas dépasser la valeur du titre.',
      });
    }
  });

type Titres = z.infer<typeof titresRestaurantSchema>;

/**
 * Ce que la fiche envoie : la valeur du titre et la part patronale seulement si
 * la fiche les portait déjà ou si elles sont saisies. Les ajouter à zéro sur
 * toutes les fiches changerait leur empreinte et ferait passer leurs brouillons
 * « À recalculer » au premier enregistrement.
 */
export function titresPourEnvoi(
  saisie: Titres,
  existant: Record<string, unknown> | null | undefined,
): Record<string, unknown> {
  const envoi: Record<string, unknown> = {
    beneficie: saisie.beneficie,
    nombre_par_mois: saisie.nombre_par_mois,
  };
  for (const cle of ['valeur_faciale', 'part_patronale'] as const) {
    if ((existant && cle in existant) || (saisie[cle] ?? 0) > 0) envoi[cle] = saisie[cle] ?? 0;
  }
  return envoi;
}
