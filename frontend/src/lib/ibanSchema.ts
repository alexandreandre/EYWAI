import { z } from 'zod';
import { ibanProblem } from '@/lib/iban';

export const ibanFieldSchema = z.string().superRefine((value, ctx) => {
  const problem = ibanProblem(value);
  if (problem) ctx.addIssue({ code: 'custom', message: problem });
});

export const bicFieldSchema = z
  .string()
  .optional()
  .default('')
  .refine((value) => {
    const bic = value.replace(/\s/g, '').toUpperCase();
    return !bic || /^[A-Z0-9]{8}([A-Z0-9]{3})?$/.test(bic);
  }, { message: 'BIC invalide.' });
