import type { OccupationalHealthContact } from '@/api/medicalFollowUp';

export function hasOccupationalHealthContact(
  contact: OccupationalHealthContact | null | undefined
): boolean {
  if (!contact) return false;
  return Boolean(
    contact.nom ||
      contact.adresse_rue ||
      contact.adresse_code_postal ||
      contact.adresse_ville ||
      contact.telephone ||
      contact.email
  );
}

export function formatOccupationalHealthAddress(
  contact: OccupationalHealthContact
): string | null {
  const parts: string[] = [];
  if (contact.adresse_rue) parts.push(contact.adresse_rue);
  const cityLine = [contact.adresse_code_postal, contact.adresse_ville].filter(Boolean).join(' ');
  if (cityLine) parts.push(cityLine);
  return parts.length > 0 ? parts.join(', ') : null;
}
