import { z } from 'zod';
import { isValidIban } from '@/lib/iban';

export const ibanFieldSchema = z
  .string()
  .min(15, { message: 'IBAN invalide.' })
  .refine(isValidIban, { message: 'IBAN invalide.' });

export const bicFieldSchema = z
  .string()
  .optional()
  .default('')
  .refine((value) => {
    const bic = value.replace(/\s/g, '').toUpperCase();
    return !bic || /^[A-Z0-9]{8}([A-Z0-9]{3})?$/.test(bic);
  }, { message: 'BIC invalide.' });
