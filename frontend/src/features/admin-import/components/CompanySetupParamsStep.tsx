import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Sparkles } from 'lucide-react';
import { applyCcnSetupPreset } from '@/api/adminImport';
import {
  useCompanySetupStatus,
  useRefreshCompanySetupStatus,
} from '@/features/admin-import/hooks/useCompanySetupStatus';
import LeaveSettingsCard from '@/features/company/components/LeaveSettingsCard';
import PublicHolidaysSettingsCard from '@/features/company/components/PublicHolidaysSettingsCard';
import JeiSettingsCard from '@/features/company/components/JeiSettingsCard';
import OethSettingsCard from '@/features/company/components/OethSettingsCard';
import { SetupCompanyScope } from '@/features/admin-import/components/SetupCompanyScope';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';

export function CompanySetupParamsStep({
  companyId,
  idcc,
}: {
  companyId: string;
  idcc?: string | null;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: status } = useCompanySetupStatus(companyId);
  const refreshStatus = useRefreshCompanySetupStatus();

  const presetMutation = useMutation({
    mutationFn: () => applyCcnSetupPreset(companyId),
    onSuccess: () => {
      toast({ title: 'Preset CCN appliqué', description: 'Congés et modulation mis à jour.' });
      void refreshStatus(companyId);
      void queryClient.invalidateQueries({ queryKey: ['leave-settings'] });
    },
    onError: (e: Error) => {
      toast({ title: 'Erreur', description: e.message, variant: 'destructive' });
    },
  });

  if (!companyId) {
    return <p className="text-sm text-muted-foreground">Sélectionnez une entreprise.</p>;
  }

  return (
    <SetupCompanyScope companyId={companyId}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground max-w-2xl">
            Paramètres critiques pour la paie et les absences. Appliquez le preset CCN
            {idcc ? ` (IDCC ${idcc})` : ''} puis ajustez si besoin.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={presetMutation.isPending}
            onClick={() => presetMutation.mutate()}
          >
            {presetMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            Appliquer preset CCN
          </Button>
        </div>
        <LeaveSettingsCard />
        <PublicHolidaysSettingsCard />
        {status?.blocks.payroll_params ? (
          <p className="text-xs text-muted-foreground rounded-md border p-3">
            Paramètres paie : AT/MP {status.blocks.payroll_params.taux_at_mp ?? '—'}, fin période
            jour {status.blocks.payroll_params.paie_jour_de_fin ?? '—'}. VM/FNAL : compléter sur la
            fiche entreprise si besoin.
          </p>
        ) : null}
        <JeiSettingsCard />
        <OethSettingsCard />
      </div>
    </SetupCompanyScope>
  );
}
