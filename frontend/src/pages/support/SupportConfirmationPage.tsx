// Page de confirmation après envoi d'une demande support

import { useNavigate } from 'react-router-dom';
import { CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function SupportConfirmationPage() {
  const navigate = useNavigate();

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center py-12 text-center">
      <CheckCircle className="mb-6 h-16 w-16 text-green-600" aria-hidden />
      <h1 className="text-2xl font-semibold tracking-tight">
        Votre demande a bien été transmise
      </h1>
      <p className="text-muted-foreground mt-4 text-sm leading-relaxed">
        Vous recevrez une réponse dans un délai de 24 à 48h. Pour les demandes critiques, notre
        équipe intervient en priorité.
      </p>
      <div className="mt-8 flex w-full flex-col gap-3 sm:flex-row sm:justify-center">
        <Button type="button" onClick={() => navigate('/')}>
          Retour à l&apos;accueil
        </Button>
        <Button type="button" variant="link" className="text-primary" onClick={() => navigate('/support/tickets')}>
          Voir mes tickets
        </Button>
      </div>
    </div>
  );
}
