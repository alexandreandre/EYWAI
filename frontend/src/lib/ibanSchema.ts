import { z } from 'zod';
import { isValidIban } from '@/lib/iban';

export const ibanFieldSchema = z
  .string()
  .min(15, { message: 'IBAN invalide.' })
  .refine(isValidIban, { message: 'IBAN invalide.' });
