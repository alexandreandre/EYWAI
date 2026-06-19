import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { useCompany } from '@/contexts/CompanyContext';
import {
  getTimesheetImportProfiles,
  saveTimesheetImportProfile,
  type TimesheetImportProfile,
} from '@/api/calendar';

export default function TimesheetImportSettingsCard() {
  const { activeCompany } = useCompany();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const activeCompanyId = activeCompany?.id;

  const canEdit = useMemo(() => {
    const role = activeCompany?.role;
    return role === 'admin' || role === 'rh' || role === 'collaborateur_rh';
  }, [activeCompany?.role]);

  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ['timesheet-import-profiles', activeCompanyId],
    queryFn: async () => {
      const { data } = await getTimesheetImportProfiles();
      return data;
    },
    enabled: !!activeCompanyId,
  });

  const defaultProfile = profiles.find(
    (p) => p.profile_name === 'default' && p.source_type === 'csv',
  );

  const saveMut = useMutation({
    mutationFn: (profile: Omit<TimesheetImportProfile, 'id'>) =>
      saveTimesheetImportProfile(profile),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timesheet-import-profiles', activeCompanyId] });
      toast({ title: 'Profil import enregistré' });
    },
    onError: () => {
      toast({
        title: 'Erreur',
        description: 'Impossible de sauvegarder le profil.',
        variant: 'destructive',
      });
    },
  });

  const handleSave = () => {
    saveMut.mutate({
      profile_name: 'default',
      source_type: 'csv',
      parser_key: 'tabular_generic',
      column_mapping: defaultProfile?.column_mapping ?? {},
      options: defaultProfile?.options ?? { decimal_separator: ',', skip_rows: 0 },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Upload className="h-4 w-4" />
          Import pointages
        </CardTitle>
        <CardDescription>
          Profils de mapping pour les exports CSV/Excel des filiales.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              {profiles.length === 0
                ? 'Aucun profil — créé automatiquement au premier import CSV.'
                : `${profiles.length} profil(s) enregistré(s).`}
            </p>
            <div className="grid max-w-xs gap-2">
              <Label htmlFor="skip-rows">Lignes d&apos;en-tête à ignorer (CSV)</Label>
              <Input
                id="skip-rows"
                type="number"
                min={0}
                defaultValue={String((defaultProfile?.options?.skip_rows as number) ?? 0)}
                disabled={!canEdit}
                onBlur={(e) => {
                  if (!canEdit) return;
                  saveMut.mutate({
                    profile_name: 'default',
                    source_type: 'csv',
                    parser_key: 'tabular_generic',
                    column_mapping: defaultProfile?.column_mapping ?? {},
                    options: {
                      ...(defaultProfile?.options ?? {}),
                      skip_rows: Number(e.target.value) || 0,
                      decimal_separator: ',',
                    },
                  });
                }}
              />
            </div>
            {canEdit && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSave}
                disabled={saveMut.isPending}
              >
                {saveMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Réinitialiser profil CSV par défaut
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
