import { z } from 'zod';

import { TAUX_PREVOYANCE_INVALIDE } from '@/features/employees/utils/prevoyance';

/**
 * Une ligne de prévoyance de la fiche, taux en fraction. Les clés que le
 * formulaire ne montre pas passent telles quelles : `base` surtout (tranche B,
 * reprise de la DSN ou formule de la société), que le moteur lit — le
 * schéma la retirait jusqu'au 02/11/2026.
 */
export const lignePrevoyanceSchema = z
  .object({
    id: z.string(),
    libelle: z.string().min(2, { message: 'Libellé requis.' }),
    salarial: z.coerce.number({ invalid_type_error: TAUX_PREVOYANCE_INVALIDE }),
    patronal: z.coerce.number({ invalid_type_error: TAUX_PREVOYANCE_INVALIDE }),
    // Plus saisi : le forfait social suit la loi (8 % à partir de 11 salariés).
    forfait_social: z.coerce.number({ invalid_type_error: TAUX_PREVOYANCE_INVALIDE }).optional(),
  })
  .passthrough();

/** La formule de la société d'où viennent les lignes (aucun calcul ne la lit). */
export const formulePrevoyanceIdSchema = z.string().nullable().optional();

/** La prévoyance de la fiche, telle que la modification de fiche la valide. */
export const prevoyanceFicheSchema = z.object({
  adhesion: z.boolean(),
  formule_id: formulePrevoyanceIdSchema,
  lignes_specifiques: z.array(lignePrevoyanceSchema).optional().default([]),
});
