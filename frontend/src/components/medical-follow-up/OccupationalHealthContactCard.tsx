import type { OccupationalHealthContact } from '@/api/medicalFollowUp';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  formatOccupationalHealthAddress,
  hasOccupationalHealthContact,
} from '@/lib/occupationalHealthContact';
import { Building2, Mail, Phone } from 'lucide-react';

interface OccupationalHealthContactCardProps {
  contact: OccupationalHealthContact | null | undefined;
  compact?: boolean;
}

export function OccupationalHealthContactCard({
  contact,
  compact = false,
}: OccupationalHealthContactCardProps) {
  if (!hasOccupationalHealthContact(contact) || !contact) {
    return null;
  }

  const address = formatOccupationalHealthAddress(contact);

  if (compact) {
    return (
      <div className="rounded-lg border bg-muted/30 p-4 space-y-2 text-sm">
        <p className="font-medium flex items-center gap-2">
          <Building2 className="h-4 w-4 text-muted-foreground" />
          {contact.nom ?? 'Service de santé au travail'}
        </p>
        {address ? <p className="text-muted-foreground">{address}</p> : null}
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {contact.telephone ? (
            <a href={`tel:${contact.telephone.replace(/\s/g, '')}`} className="inline-flex items-center gap-1 text-primary hover:underline">
              <Phone className="h-3.5 w-3.5" />
              {contact.telephone}
            </a>
          ) : null}
          {contact.email ? (
            <a href={`mailto:${contact.email}`} className="inline-flex items-center gap-1 text-primary hover:underline">
              <Mail className="h-3.5 w-3.5" />
              {contact.email}
            </a>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Service de santé au travail</CardTitle>
        <CardDescription>
          Coordonnées pour planifier vos visites médicales
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {contact.nom ? <p className="font-medium">{contact.nom}</p> : null}
        {address ? <p className="text-muted-foreground whitespace-pre-line">{address.replace(', ', '\n')}</p> : null}
        <div className="flex flex-col gap-2 pt-1">
          {contact.telephone ? (
            <a
              href={`tel:${contact.telephone.replace(/\s/g, '')}`}
              className="inline-flex items-center gap-2 text-primary hover:underline w-fit"
            >
              <Phone className="h-4 w-4" />
              {contact.telephone}
            </a>
          ) : null}
          {contact.email ? (
            <a
              href={`mailto:${contact.email}`}
              className="inline-flex items-center gap-2 text-primary hover:underline w-fit"
            >
              <Mail className="h-4 w-4" />
              {contact.email}
            </a>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
