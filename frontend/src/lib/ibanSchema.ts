import { z } from 'zod';

export const bicFieldSchema = z
  .string()
  .optional()
  .default('')
  .refine((value) => {
    const bic = value.replace(/\s/g, '').toUpperCase();
    return !bic || /^[A-Z0-9]{8}([A-Z0-9]{3})?$/.test(bic);
  }, { message: 'BIC invalide.' });
