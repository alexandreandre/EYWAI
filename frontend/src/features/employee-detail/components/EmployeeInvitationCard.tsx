// Carte « Accès à l'espace salarié » sur la fiche RH : état d'invitation
// (jamais invité / invité le X / activé) et bouton Inviter / Renvoyer.
// Le bouton est désactivé, avec info-bulle, tant que la fiche n'a pas
// d'adresse e-mail réelle (jamais d'adresse fabriquée).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getInvitationStatus, inviteEmployee } from '@/api/activation';
import {
  getInvitationDisabledReason,
  isEmployeeInvitable,
} from '@/lib/activationUtils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { toast } from '@/components/ui/use-toast';
import { CheckCircle2, Loader2, Mail } from 'lucide-react';

interface EmployeeInvitationCardProps {
  employeeId: string;
  email: string | null | undefined;
  employmentStatus?: string | null;
}

const invitationQueryKey = (employeeId: string) => [
  'employee-invitation',
  employeeId,
];

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export function EmployeeInvitationCard({
  employeeId,
  email,
  employmentStatus,
}: EmployeeInvitationCardProps) {
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: invitationQueryKey(employeeId),
    queryFn: () => getInvitationStatus(employeeId),
  });

  const inviteMutation = useMutation({
    mutationFn: () => inviteEmployee(employeeId),
    onSuccess: (sent) => {
      queryClient.invalidateQueries({
        queryKey: invitationQueryKey(employeeId),
      });
      toast({
        title: 'Invitation envoyée',
        description: `Un e-mail d'activation a été adressé à ${sent.email}.`,
      });
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      const message =
        typeof detail === 'object' && detail !== null && 'message' in detail
          ? String((detail as { message?: unknown }).message ?? '')
          : "L'invitation n'a pas pu être envoyée. Réessayez plus tard.";
      toast({
        title: 'Invitation impossible',
        description: message,
        variant: 'destructive',
      });
    },
  });

  const status = statusQuery.data;
  const isActive = status?.status === 'active';
  const isInvited = status?.status === 'invite';
  const invitedAtLabel = formatDate(status?.invited_at);

  const inactiveEmployee = Boolean(
    employmentStatus && employmentStatus !== 'actif',
  );
  const emailReason = getInvitationDisabledReason(email);
  const disabledReason = inactiveEmployee
    ? "Ce salarié n'est plus actif : il n'est pas invitable."
    : emailReason;
  const canInvite =
    !isActive && !disabledReason && isEmployeeInvitable(email);

  let statusNode: React.ReactNode = null;
  if (statusQuery.isLoading) {
    statusNode = (
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Chargement de l&apos;état…
      </span>
    );
  } else if (statusQuery.isError) {
    statusNode = (
      <span className="text-sm text-muted-foreground">
        État d&apos;invitation indisponible.
      </span>
    );
  } else if (isActive) {
    statusNode = (
      <Badge className="bg-green-100 text-green-800 hover:bg-green-100">
        <CheckCircle2 className="mr-1 h-3.5 w-3.5" aria-hidden />
        Compte activé
      </Badge>
    );
  } else if (isInvited) {
    statusNode = (
      <span className="text-sm text-muted-foreground">
        Invité{invitedAtLabel ? ` le ${invitedAtLabel}` : ''}
        {status?.expired ? (
          <Badge variant="outline" className="ml-2 text-amber-700">
            Lien expiré
          </Badge>
        ) : null}
      </span>
    );
  } else {
    statusNode = (
      <span className="text-sm text-muted-foreground">Jamais invité</span>
    );
  }

  const inviteButton = (
    <Button
      type="button"
      variant="outline"
      size="sm"
      disabled={!canInvite || inviteMutation.isPending}
      onClick={() => inviteMutation.mutate()}
    >
      {inviteMutation.isPending ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <Mail className="mr-2 h-4 w-4" aria-hidden />
      )}
      {isInvited ? "Renvoyer l'invitation" : 'Inviter'}
    </Button>
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Accès à l&apos;espace salarié</CardTitle>
        <CardDescription>
          Le salarié reçoit un e-mail avec un lien d&apos;activation (valide 7
          jours) pour choisir son mot de passe.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-3">
        {statusNode}
        {isActive ? null : disabledReason ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0}>{inviteButton}</span>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              {disabledReason}
            </TooltipContent>
          </Tooltip>
        ) : (
          inviteButton
        )}
      </CardContent>
    </Card>
  );
}
