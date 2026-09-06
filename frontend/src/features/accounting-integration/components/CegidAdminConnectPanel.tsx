import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import type { AccountingConfigUpdate, CegidAuthMode } from '@/api/accountingIntegration';
import {
  adminBulkUpdateCegidDossiers,
  adminTestCompanyAccountingConnection,
  adminTestPlatformAccountingConnection,
  adminUpdateCompanyAccountingConfig,
  getAdminCompanyAccountingConfig,
  updatePlatformAccountingProvider,
  type PlatformProviderEntry,
} from '@/api/accountingIntegrationsAdmin';
import { CegidConnectWizard } from '@/features/accounting-integration/components/CegidConnectWizard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';

type CompanyRow = { id: string; company_name: string };

type CompanyDossierRow = {
  companyId: string;
  companyName: string;
  codeDossier: string;
  authMode: CegidAuthMode;
  connectionState: string;
  expanded: boolean;
};

type CegidAdminConnectPanelProps = {
  providerEnabled: boolean;
  platformProvider?: PlatformProviderEntry;
};

function connectionBadge(state: string) {
  if (state === 'connected') {
    return <Badge className="bg-green-600 hover:bg-green-600">Connecté</Badge>;
  }
  if (state === 'failed') {
    return <Badge variant="destructive">Échec</Badge>;
  }
  return <Badge variant="outline">Incomplet</Badge>;
}

export function CegidAdminConnectPanel({
  providerEnabled,
  platformProvider,
}: CegidAdminConnectPanelProps) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [loopApiKey, setLoopApiKey] = useState('');
  const [apimSubscriptionKey, setApimSubscriptionKey] = useState('');
  const [cegidBaseUrl, setCegidBaseUrl] = useState('');
  const [dossierRows, setDossierRows] = useState<CompanyDossierRow[]>([]);
  const [dedicatedCompanyId, setDedicatedCompanyId] = useState<string | null>(null);
  const [dedicatedLoopApiKey, setDedicatedLoopApiKey] = useState('');
  const [dedicatedApimKey, setDedicatedApimKey] = useState('');
  const [dedicatedCodeDossier, setDedicatedCodeDossier] = useState('');
  const [dedicatedBaseUrl, setDedicatedBaseUrl] = useState('');

  const { data: companies = [], isLoading: companiesLoading } = useQuery({
    queryKey: ['admin', 'companies-list-accounting'],
    queryFn: async () => {
      const res = await apiClient.get<{ companies: CompanyRow[] }>('/api/super-admin/companies', {
        params: { limit: 200 },
      });
      return res.data.companies ?? [];
    },
    enabled: providerEnabled,
  });

  const { data: companyConfigs = [] } = useQuery({
    queryKey: ['admin-cegid-company-configs', companies.map((c) => c.id).join(',')],
    queryFn: async () =>
      Promise.all(companies.map((c) => getAdminCompanyAccountingConfig(c.id))),
    enabled: providerEnabled && companies.length > 0,
  });

  useEffect(() => {
    if (!companies.length || !companyConfigs.length) return;
    setDossierRows(
      companies.map((c, i) => {
        const cfg = companyConfigs[i];
        return {
          companyId: c.id,
          companyName: c.company_name,
          codeDossier: cfg?.code_dossier_cegid ?? '',
          authMode: cfg?.cegid_auth_mode ?? 'shared',
          connectionState: cfg?.connection_state ?? 'not_configured',
          expanded: false,
        };
      }),
    );
  }, [companies, companyConfigs]);

  const invalidateAll = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['admin-cegid-company-configs'] });
    qc.invalidateQueries({ queryKey: ['admin-company-accounting-config'] });
    qc.invalidateQueries({ queryKey: ['platform-accounting-catalog'] });
  }, [qc]);

  const saveCabinetMutation = useMutation({
    mutationFn: () =>
      updatePlatformAccountingProvider('cegid_quadra', {
        platform_credentials: {
          loop_apikey: loopApiKey,
          apim_subscription_key: apimSubscriptionKey,
          ...(cegidBaseUrl ? { api_base_url: cegidBaseUrl } : {}),
        },
      }),
    onSuccess: () => {
      invalidateAll();
      toast({ title: 'Clés comptables enregistrées' });
    },
    onError: (e: Error) => {
      toast({ title: 'Erreur', description: e.message, variant: 'destructive' });
    },
  });

  const testCabinetMutation = useMutation({
    mutationFn: () => adminTestPlatformAccountingConnection('cegid_quadra'),
    onSuccess: (r) => {
      invalidateAll();
      toast({
        title: r.success ? 'Comptabilité connectée' : 'Échec de connexion à la comptabilité',
        description: r.message,
        variant: r.success ? 'default' : 'destructive',
      });
    },
  });

  const bulkSaveMutation = useMutation({
    mutationFn: () =>
      adminBulkUpdateCegidDossiers(
        dossierRows
          .filter((r) => r.codeDossier.trim())
          .map((r) => ({
            company_id: r.companyId,
            code_dossier_cegid: r.codeDossier.trim(),
            enabled: true,
            cegid_auth_mode: r.authMode,
          })),
      ),
    onSuccess: (r) => {
      invalidateAll();
      toast({
        title: 'Dossiers enregistrés',
        description: `${r.updated} filiale(s) mise(s) à jour${r.failed.length ? `, ${r.failed.length} échec(s)` : ''}.`,
        variant: r.failed.length ? 'destructive' : 'default',
      });
    },
  });

  const saveDedicatedMutation = useMutation({
    mutationFn: ({
      companyId,
      body,
    }: {
      companyId: string;
      body: AccountingConfigUpdate;
    }) => adminUpdateCompanyAccountingConfig(companyId, body),
    onSuccess: () => {
      invalidateAll();
      setDedicatedCompanyId(null);
      toast({ title: 'Connexion dédiée enregistrée' });
    },
  });

  const testCompanyMutation = useMutation({
    mutationFn: (companyId: string) => adminTestCompanyAccountingConnection(companyId),
    onSuccess: (r, companyId) => {
      invalidateAll();
      setDossierRows((prev) =>
        prev.map((row) =>
          row.companyId === companyId
            ? { ...row, connectionState: r.success ? 'connected' : 'failed' }
            : row,
        ),
      );
      toast({
        title: r.success ? 'Filiale connectée' : 'Échec de connexion',
        description: r.message,
        variant: r.success ? 'default' : 'destructive',
      });
    },
  });

  const handleSaveCabinet = async () => {
    if (!loopApiKey || !apimSubscriptionKey) return;
    await saveCabinetMutation.mutateAsync();
    testCabinetMutation.mutate();
  };

  const handleSaveRow = async (row: CompanyDossierRow) => {
    if (!row.codeDossier.trim()) return;
    await adminUpdateCompanyAccountingConfig(row.companyId, {
      enabled: true,
      provider: 'cegid_quadra',
      mode: 'api_quadra',
      default_format: 'fec',
      code_dossier_cegid: row.codeDossier.trim(),
      cegid_auth_mode: row.authMode,
      ...(row.authMode === 'shared' ? { clear_company_credentials: true } : {}),
    });
    invalidateAll();
    toast({ title: `${row.companyName} — dossier enregistré` });
  };

  const handleDedicatedFinalize = async () => {
    if (!dedicatedCompanyId || !dedicatedLoopApiKey || !dedicatedApimKey || !dedicatedCodeDossier) {
      return;
    }
    await saveDedicatedMutation.mutateAsync({
      companyId: dedicatedCompanyId,
      body: {
        enabled: true,
        provider: 'cegid_quadra',
        mode: 'api_quadra',
        default_format: 'fec',
        cegid_auth_mode: 'dedicated',
        code_dossier_cegid: dedicatedCodeDossier,
        credentials: {
          loop_apikey: dedicatedLoopApiKey,
          apim_subscription_key: dedicatedApimKey,
          code_dossier: dedicatedCodeDossier,
          ...(dedicatedBaseUrl ? { api_base_url: dedicatedBaseUrl } : {}),
        },
      },
    });
    testCompanyMutation.mutate(dedicatedCompanyId);
  };

  const cabinetConnected = platformProvider?.last_test_status === 'connected';
  const hasCabinetKeys = platformProvider?.has_platform_cegid_credentials ?? false;

  const sharedRowsCount = useMemo(
    () => dossierRows.filter((r) => r.authMode === 'shared' && r.codeDossier.trim()).length,
    [dossierRows],
  );

  if (!providerEnabled) {
    return (
      <p className="text-muted-foreground text-xs">
        Activez le connecteur ci-dessus pour configurer la connexion Cegid des entreprises.
      </p>
    );
  }

  return (
    <div className="space-y-6 border-t pt-4">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Label className="text-sm font-medium">Clés comptables du groupe</Label>
          {hasCabinetKeys ? (
            cabinetConnected ? (
              <Badge className="bg-green-600 hover:bg-green-600">Comptabilité connectée</Badge>
            ) : (
              <Badge variant="outline">Clés enregistrées — test requis</Badge>
            )
          ) : (
            <Badge variant="outline">Non configuré</Badge>
          )}
        </div>
        <p className="text-muted-foreground text-xs">
          Une seule paire de clés pour toutes les filiales en mode partagé. Les filiales en mode
          dédié utilisent leurs propres clés.
        </p>
        <CegidConnectWizard
          loopApiKey={loopApiKey}
          apimSubscriptionKey={apimSubscriptionKey}
          codeDossier=""
          cegidBaseUrl={cegidBaseUrl}
          onLoopApiKeyChange={setLoopApiKey}
          onApimSubscriptionKeyChange={setApimSubscriptionKey}
          onCodeDossierChange={() => undefined}
          onCegidBaseUrlChange={setCegidBaseUrl}
          onBack={() => undefined}
          onFinalize={handleSaveCabinet}
          isSaving={saveCabinetMutation.isPending}
          isTesting={testCabinetMutation.isPending}
          wizardMode="cabinet"
          initialPhase="paste"
          hideBackActions
        />
        {hasCabinetKeys ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={testCabinetMutation.isPending}
            onClick={() => testCabinetMutation.mutate()}
          >
            Tester la connexion comptable
          </Button>
        ) : null}
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label className="text-sm font-medium">Dossiers par filiale</Label>
          <Button
            type="button"
            size="sm"
            disabled={bulkSaveMutation.isPending || sharedRowsCount === 0}
            onClick={() => bulkSaveMutation.mutate()}
          >
            Enregistrer tout ({sharedRowsCount})
          </Button>
        </div>

        {companiesLoading ? (
          <p className="text-muted-foreground text-xs">Chargement des entreprises…</p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entreprise</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Code IBS</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dossierRows.map((row) => (
                  <Fragment key={row.companyId}>
                    <TableRow>
                      <TableCell className="font-medium">{row.companyName}</TableCell>
                      <TableCell>
                        <Select
                          value={row.authMode}
                          onValueChange={(v: CegidAuthMode) =>
                            setDossierRows((prev) =>
                              prev.map((r) =>
                                r.companyId === row.companyId
                                  ? { ...r, authMode: v, expanded: v === 'dedicated' }
                                  : r,
                              ),
                            )
                          }
                        >
                          <SelectTrigger className="h-8 w-[130px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="shared">Partagé</SelectItem>
                            <SelectItem value="dedicated">Dédié</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        {row.authMode === 'shared' ? (
                          <Input
                            className="h-8 max-w-[180px]"
                            value={row.codeDossier}
                            onChange={(e) =>
                              setDossierRows((prev) =>
                                prev.map((r) =>
                                  r.companyId === row.companyId
                                    ? { ...r, codeDossier: e.target.value }
                                    : r,
                                ),
                              )
                            }
                            placeholder="Code IBS"
                          />
                        ) : (
                          <span className="text-muted-foreground text-xs">Clés propres</span>
                        )}
                      </TableCell>
                      <TableCell>{connectionBadge(row.connectionState)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {row.authMode === 'shared' ? (
                            <>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => handleSaveRow(row)}
                              >
                                Enregistrer
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                disabled={testCompanyMutation.isPending}
                                onClick={() => testCompanyMutation.mutate(row.companyId)}
                              >
                                Tester
                              </Button>
                            </>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setDedicatedCompanyId(row.companyId);
                                setDedicatedCodeDossier(row.codeDossier);
                              }}
                            >
                              Configurer
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                    {dedicatedCompanyId === row.companyId ? (
                      <TableRow key={`${row.companyId}-dedicated`}>
                        <TableCell colSpan={5} className="bg-muted/20 p-4">
                          <CegidConnectWizard
                            loopApiKey={dedicatedLoopApiKey}
                            apimSubscriptionKey={dedicatedApimKey}
                            codeDossier={dedicatedCodeDossier}
                            cegidBaseUrl={dedicatedBaseUrl}
                            onLoopApiKeyChange={setDedicatedLoopApiKey}
                            onApimSubscriptionKeyChange={setDedicatedApimKey}
                            onCodeDossierChange={setDedicatedCodeDossier}
                            onCegidBaseUrlChange={setDedicatedBaseUrl}
                            onBack={() => setDedicatedCompanyId(null)}
                            onFinalize={handleDedicatedFinalize}
                            isSaving={saveDedicatedMutation.isPending}
                            isTesting={testCompanyMutation.isPending}
                            wizardMode="dedicated"
                            initialPhase="paste"
                          />
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}
