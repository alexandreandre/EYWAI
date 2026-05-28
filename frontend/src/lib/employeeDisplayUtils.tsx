import type { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { UserMinus } from 'lucide-react';

const CONTRACT_BADGE_CLASSES: Record<string, string> = {
  CDI: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200',
  CDD: 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200',
};

export function formatEmployeeDateFR(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = iso.includes('T') ? new Date(iso) : new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('fr-FR');
}

export function getContractTypeBadge(type: string | null | undefined): ReactNode {
  if (!type) return <span className="text-sm text-muted-foreground">—</span>;
  const className =
    CONTRACT_BADGE_CLASSES[type] ?? 'bg-muted text-muted-foreground';
  return (
    <Badge variant="default" className={className}>
      {type}
    </Badge>
  );
}

export function getStatutCadreBadge(statut: string | null | undefined): ReactNode {
  if (!statut) return <span className="text-sm text-muted-foreground">—</span>;
  return (
    <Badge variant="outline" className="font-normal">
      {statut}
    </Badge>
  );
}

export function getEmploymentStatusBadge(
  status: string | null | undefined,
): ReactNode | null {
  if (status === 'en_sortie') {
    return (
      <Badge variant="outline" className="shrink-0 text-xs">
        <UserMinus className="mr-1 h-3 w-3" />
        En départ
      </Badge>
    );
  }
  if (status === 'parti') {
    return (
      <Badge variant="secondary" className="shrink-0 text-xs">
        Parti
      </Badge>
    );
  }
  return null;
}

export function getCollectiveAgreementLabel(
  agreement: {
    agreement_details?: { name?: string | null; idcc?: string | null } | null;
  },
): string {
  const name =
    agreement.agreement_details?.name ||
    agreement.agreement_details?.idcc ||
    'Convention';
  const idcc = agreement.agreement_details?.idcc;
  return idcc ? `${name} (IDCC ${idcc})` : name;
}
