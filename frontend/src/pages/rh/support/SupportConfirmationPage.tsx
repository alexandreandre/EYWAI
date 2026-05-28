// Page de confirmation après envoi d'une demande support

import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle } from 'lucide-react';
import { EmployeePageHeader } from '@/components/employee/EmployeePageHeader';
import { Button } from '@/components/ui/button';
import {
  clearSupportConfirmationTicket,
  readSupportConfirmationTicket,
  type SupportConfirmationLocationState,
} from '@/lib/supportConfirmation';

function formatTicketReference(ticketId: string): string {
  if (ticketId.length <= 8) return ticketId;
  return `${ticketId.slice(0, 8)}…`;
}

export default function SupportConfirmationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as SupportConfirmationLocationState | null;
  const ticketId = state?.ticketId ?? readSupportConfirmationTicket();

  if (!ticketId) {
    return <Navigate to="/support" replace />;
  }

  const leaveConfirmation = (to: string) => {
    clearSupportConfirmationTicket();
    navigate(to);
  };

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center py-12 text-center">
      <CheckCircle className="mb-6 h-16 w-16 text-green-600" aria-hidden />
      <EmployeePageHeader
        centered
        title="Votre demande a bien été transmise"
        description="Vous recevrez une réponse dans un délai de 24 à 48h. Pour les demandes critiques, notre équipe intervient en priorité."
        className="w-full"
      />
      <p className="mt-4 text-sm text-muted-foreground">
        Référence :{' '}
        <span className="font-mono font-medium text-foreground" title={ticketId}>
          {formatTicketReference(ticketId)}
        </span>
      </p>
      <div className="mt-8 flex w-full flex-col gap-3 sm:flex-row sm:justify-center">
        <Button type="button" onClick={() => leaveConfirmation('/')}>
          Retour à l&apos;accueil
        </Button>
        <Button
          type="button"
          variant="link"
          className="text-primary"
          onClick={() => leaveConfirmation('/support/tickets')}
        >
          Voir mes tickets
        </Button>
      </div>
    </div>
  );
}
