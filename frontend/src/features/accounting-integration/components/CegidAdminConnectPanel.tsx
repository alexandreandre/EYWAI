import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import type { AccountingConfig, AccountingConfigUpdate } from '@/api/accountingIntegration';
import {
  adminTestCompanyAccountingConnection,
  adminUpdateCompanyAccountingConfig,
  getAdminCompanyAccountingConfig,
} from '@/api/accountingIntegrationsAdmin';
import { CegidConnectWizard } from '@/features/accounting-integration/components/CegidConnectWizard';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';

type CompanyRow = { id: string; company_name: string };

type CegidAdminConnectPanelProps = {
  providerEnabled: boolean;
};

export function CegidAdminConnectPanel({ providerEnabled }: CegidAdminConnectPanelProps) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [companyId, setCompanyId] = useState('');
  const [loopApiKey, setLoopApiKey] = useState('');
  const [apimSubscriptionKey, setApimSubscriptionKey] = useState('');
  const [codeDossier, setCodeDossier] = useState('');
  const [cegidBaseUrl, setCegidBaseUrl] = useState('');

  const { data: companies = [], isLoading: companiesLoading } = useQuery({
    queryKey: ['admin', 'companies-list-accounting'],
    queryFn: async () => {
      const res = await apiClient.get<{ companies: CompanyRow[] }>('/api/super-admin/companies', {
        params: { limit: 200 },
      });
      return res.data.companies ?? [];
    },
  });

  useEffect(() => {
    if (companies.length && !companyId) {
      setCompanyId(companies[0].id);
    }
  }, [companies, companyId]);

  const { data: config, isLoading: configLoading } = useQuery({
    queryKey: ['admin-company-accounting-config', companyId],
    queryFn: () => getAdminCompanyAccountingConfig(companyId),
    enabled: Boolean(companyId) && providerEnabled,
  });

  const saveMutation = useMutation({
    mutationFn: (body: AccountingConfigUpdate) =>
      adminUpdateCompanyAccountingConfig(companyId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-company-accounting-config', companyId] });
      toast({ title: 'Configuration enregistrée' });
    },
    onError: (e: Error) => {
      toast({ title: 'Erreur', description: e.message, variant: 'destructive' });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => adminTestCompanyAccountingConnection(companyId),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['admin-company-accounting-config', companyId] });
      toast({
        title: r.success ? 'Connecté à Cegid Loop' : 'Échec de connexion',
        description: r.message,
        variant: r.success ? 'default' : 'destructive',
      });
    },
  });

  const handleFinalize = async () => {
    if (!loopApiKey || !apimSubscriptionKey || !codeDossier) return;
    try {
      await saveMutation.mutateAsync({
        enabled: true,
        provider: 'cegid_quadra',
        mode: 'api_quadra',
        default_format: 'fec',
        credentials: {
          loop_apikey: loopApiKey,
          apim_subscription_key: apimSubscriptionKey,
          code_dossier: codeDossier,
          ...(cegidBaseUrl ? { api_base_url: cegidBaseUrl } : {}),
        },
      });
      testMutation.mutate();
    } catch {
      /* toast saveMutation */
    }
  };

  if (!providerEnabled) {
    return (
      <p className="text-muted-foreground text-xs">
        Activez le connecteur ci-dessus pour configurer la connexion Cegid des entreprises.
      </p>
    );
  }

  return (
    <div className="space-y-4 border-t pt-4">
      <div className="space-y-2">
        <Label>Entreprise à connecter</Label>
        <Select value={companyId} onValueChange={setCompanyId} disabled={companiesLoading}>
          <SelectTrigger>
            <SelectValue placeholder="Choisir une entreprise…" />
          </SelectTrigger>
          <SelectContent>
            {companies.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.company_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {config && !configLoading ? (
          <div className="flex flex-wrap items-center gap-2">
            {config.connection_state === 'connected' ? (
              <Badge className="bg-green-600 hover:bg-green-600">Connecté à Cegid Loop</Badge>
            ) : (
              <Badge variant="outline">Non connecté</Badge>
            )}
            {config.last_test_at ? (
              <span className="text-muted-foreground text-xs">
                Dernier test :{' '}
                {new Date(config.last_test_at).toLocaleString('fr-FR', {
                  day: '2-digit',
                  month: '2-digit',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      {companyId ? (
        <CegidConnectWizard
          loopApiKey={loopApiKey}
          apimSubscriptionKey={apimSubscriptionKey}
          codeDossier={codeDossier}
          cegidBaseUrl={cegidBaseUrl}
          onLoopApiKeyChange={setLoopApiKey}
          onApimSubscriptionKeyChange={setApimSubscriptionKey}
          onCodeDossierChange={setCodeDossier}
          onCegidBaseUrlChange={setCegidBaseUrl}
          onBack={() => undefined}
          onFinalize={handleFinalize}
          isSaving={saveMutation.isPending}
          isTesting={testMutation.isPending}
          initialPhase={config?.connection_state === 'connected' ? 'paste' : 'intro'}
          hideBackActions
        />
      ) : null}
    </div>
  );
}
