import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { openBadgeuseOnThisDevice } from '@/lib/badgeuseTerminalAuth';
import { apiErrorDetail } from '@/lib/badgeuseApiUtils';

type Props = {
  companyId: string;
  className?: string;
  onActivated?: () => void;
};

export function BadgeuseOpenOnDeviceButton({ companyId, className, onActivated }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isOpening, setIsOpening] = useState(false);

  const handleOpen = async () => {
    setIsOpening(true);
    try {
      const result = await openBadgeuseOnThisDevice(companyId);
      if (result.activated) {
        void queryClient.invalidateQueries({
          queryKey: ['badgeuse', 'terminal-devices', companyId],
        });
        onActivated?.();
      }
      toast({
        title: result.activated ? 'Badgeuse activée' : 'Badgeuse ouverte',
        description: result.activated
          ? 'Cet appareil est configuré. La badgeuse restera active même après déconnexion.'
          : 'La badgeuse kiosque est ouverte dans un nouvel onglet.',
      });
    } catch (error) {
      toast({
        title: 'Impossible d’ouvrir la badgeuse',
        description: apiErrorDetail(error, 'Réessayez ou contactez le support.'),
        variant: 'destructive',
      });
    } finally {
      setIsOpening(false);
    }
  };

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={className}
      disabled={isOpening}
      onClick={() => void handleOpen()}
    >
      {isOpening ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <ExternalLink className="mr-2 h-4 w-4" aria-hidden />
      )}
      Ouvrir la badgeuse sur cet appareil
    </Button>
  );
}
