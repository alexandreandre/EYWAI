import { z } from 'zod';

export {
  employeeProfileEditSchema,
  type EmployeeProfileEditFormValues,
} from '@/features/employee-detail/components/employeeProfileEditSchema';

import { employeeProfileEditSchema } from '@/features/employee-detail/components/employeeProfileEditSchema';

/** @deprecated Utiliser employeeProfileEditSchema */
export const onboardingCompletionSchema = employeeProfileEditSchema.pick({
  nir: true,
  date_naissance: true,
  lieu_naissance: true,
  nationalite: true,
  adresse: true,
  coordonnees_bancaires: true,
  salaire_de_base: true,
});

export type OnboardingCompletionFormValues = z.infer<typeof onboardingCompletionSchema>;
