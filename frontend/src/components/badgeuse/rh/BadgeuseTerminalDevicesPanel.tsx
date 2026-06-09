import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Trash2 } from 'lucide-react';
import { listTerminalDevices, revokeTerminalDevice } from '@/api/badgeuseTerminal';
import { BadgeuseOpenOnDeviceButton } from '@/components/badgeuse/rh/BadgeuseOpenOnDeviceButton';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useToast } from '@/components/ui/use-toast';
import { formatTimeFr } from '@/lib/badgeuseFormat';

type Props = {
  companyId: string;
};

function revokeErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
  }
  return "Impossible de révoquer cet appareil. Réessayez.";
}

export function BadgeuseTerminalDevicesPanel({ companyId }: Props) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const {
    data: devices = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['badgeuse', 'terminal-devices', companyId],
    queryFn: () => listTerminalDevices(companyId),
    enabled: Boolean(companyId),
  });

  const revokeMutation = useMutation({
    mutationFn: (deviceId: string) => revokeTerminalDevice(companyId, deviceId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['badgeuse', 'terminal-devices', companyId],
      });
      toast({ title: 'Appareil révoqué', description: 'Le terminal ne peut plus pointer.' });
    },
    onError: (error: unknown) => {
      toast({
        variant: 'destructive',
        title: 'Échec de la révocation',
        description: revokeErrorMessage(error),
      });
    },
  });

  const activeDevices = devices.filter((device) => device.is_active);

  return (
    <Card className="p-6 space-y-4">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold">Appareils activés</h3>
        <p className="text-xs text-muted-foreground">
          Tablettes et postes configurés pour pointer sans session RH. Utilisez le
          bouton ci-dessous pour activer un nouvel appareil (une seule fois par
          tablette).
        </p>
      </div>

      <BadgeuseOpenOnDeviceButton companyId={companyId} />

      <div className="rounded-lg border bg-muted/20 p-4 text-xs text-muted-foreground space-y-2">
        <p className="font-medium text-foreground">Conseil iPad</p>
        <ul className="list-disc pl-4 space-y-1">
          <li>Connectez-vous une fois, puis cliquez sur le bouton d&apos;activation</li>
          <li>Ajoutez la page à l&apos;écran d&apos;accueil ou verrouillez l&apos;app (Guided Access)</li>
          <li>Ne videz pas les données Safari sur cette tablette</li>
        </ul>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Chargement des appareils…</p>
      ) : isError ? (
        <p className="text-sm text-destructive">
          Impossible de charger les appareils. Rechargez la page.
        </p>
      ) : activeDevices.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun appareil activé pour le moment.</p>
      ) : (
        <ul className="space-y-2">
          {activeDevices.map((device) => (
            <li
              key={device.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="font-medium truncate">{device.label}</p>
                <p className="text-xs text-muted-foreground">
                  Actif · préfixe {device.token_prefix}
                  {device.last_used_at
                    ? ` · dernier usage ${formatTimeFr(device.last_used_at)}`
                    : ''}
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-2"
                disabled={revokeMutation.isPending}
                onClick={() => revokeMutation.mutate(device.id)}
              >
                <Trash2 className="h-4 w-4" />
                Révoquer
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
