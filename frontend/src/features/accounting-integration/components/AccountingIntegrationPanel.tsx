import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  Circle,
  Download,
  ExternalLink,
  RefreshCw,
  Settings2,
} from 'lucide-react';
import { useCompany } from '@/contexts/CompanyContext';
import { useToast } from '@/hooks/use-toast';
import {
  getAccountingConfig,
  getAccountingProviders,
  getAccountingTransmissions,
  retryAccountingTransmission,
  testAccountingConnection,
  updateAccountingConfig,
  type AccountingConfig,
  type AccountingConfigUpdate,
  type ProviderDefinition,
} from '@/api/accountingIntegration';
import { ProviderLogo } from '@/components/integrations/ProviderLogo';
import { ExportCardRefreshOverlay } from '@/components/exports/ExportCardRefreshOverlay';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { TransmissionStatusBadge } from '@/features/accounting-integration/components/TransmissionStatusBadge';
import { CegidConnectWizard } from '@/features/accounting-integration/components/CegidConnectWizard';
import { getProviderMeta } from '@/features/accounting-integration/providers';
import { exportsLiveQueryOptions, refreshExportsPageQueries } from '@/lib/exportsQuery';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

function stateBadge(state: AccountingConfig['connection_state'], provider?: string) {
  if (state === 'connected' && provider === 'cegid_quadra') {
    return <Badge className="bg-green-600 hover:bg-green-600">Connecté à Cegid Loop</Badge>;
  }
  if (state === 'connected') return <Badge>Géré par API</Badge>;
  if (state === 'manual') return <Badge variant="secondary">Manuel</Badge>;
  if (state === 'stub') return <Badge variant="outline">API en préparation</Badge>;
  if (state === 'failed') return <Badge variant="destructive">Échec connexion</Badge>;
  return <Badge variant="outline">Non connecté</Badge>;
}

type Step = 'choose' | 'credentials' | 'cegid_connect' | 'done';

export function AccountingIntegrationPanel() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const { toast } = useToast();
  const qc = useQueryClient();

  const [step, setStep] = useState<Step>('choose');
  const [enabled, setEnabled] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>('manual');
  const [apiKey, setApiKey] = useState('');
  const [apiBaseUrl, setApiBaseUrl] = useState('');
  const [loopApiKey, setLoopApiKey] = useState('');
  const [apimSubscriptionKey, setApimSubscriptionKey] = useState('');
  const [codeDossier, setCodeDossier] = useState('');
  const [cegidBaseUrl, setCegidBaseUrl] = useState('');
  const [recipients, setRecipients] = useState('');
  const [defaultFormat, setDefaultFormat] = useState('csv');
  const [forceManual, setForceManual] = useState(false);
  const [cegidWizardMode, setCegidWizardMode] = useState<'new' | 'edit'>('new');
  const [cegidAuthMode, setCegidAuthMode] = useState<'shared' | 'dedicated'>('shared');

  const { data: config, isLoading, isFetching } = useQuery({
    queryKey: ['accounting-integration-config', companyId],
    queryFn: () => getAccountingConfig(companyId),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const useSharedCabinetKeys =
    Boolean(config?.has_platform_cegid_credentials) && cegidAuthMode === 'shared';

  const { data: providers = [] } = useQuery({
    queryKey: ['accounting-integration-providers', companyId],
    queryFn: () => getAccountingProviders(companyId),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const { data: transmissionsData } = useQuery({
    queryKey: ['accounting-integration-transmissions', companyId],
    queryFn: () => getAccountingTransmissions(companyId, { limit: 5 }),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const availableProviders = useMemo(
    () => providers.filter((p) => p.platform_enabled),
    [providers],
  );

  const syncForm = (c: AccountingConfig) => {
    setEnabled(c.enabled);
    setSelectedProvider(c.provider || 'manual');
    setRecipients((c.recipients_compta ?? []).join(', '));
    setDefaultFormat(c.default_format || 'csv');
    setForceManual(c.force_manual);
    setCodeDossier(c.code_dossier_cegid ?? '');
    setCegidAuthMode(c.cegid_auth_mode ?? 'shared');
    if (c.enabled && c.provider !== 'manual') {
      if (c.provider === 'cegid_quadra' && c.connection_state !== 'connected') {
        setStep('cegid_connect');
      } else {
        setStep('done');
      }
    } else {
      setStep('choose');
    }
  };

  useEffect(() => {
    if (config) syncForm(config);
  }, [config]);

  const saveMutation = useMutation({
    mutationFn: (body: AccountingConfigUpdate) =>
      updateAccountingConfig(companyId, body),
    onSuccess: (c) => {
      syncForm(c);
      refreshExportsPageQueries(qc, companyId);
      toast({ title: 'Configuration comptable enregistrée' });
    },
    onError: (e: Error) => {
      toast({ title: 'Erreur', description: e.message, variant: 'destructive' });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => testAccountingConnection(companyId),
    onSuccess: (r) => {
      refreshExportsPageQueries(qc, companyId);
      if (r.success) {
        setStep('done');
      }
      toast({
        title: r.success ? 'Connecté à Cegid Loop' : 'Test de connexion',
        description: r.message,
        variant: r.success ? 'default' : 'destructive',
      });
    },
  });

  const handleTestAndActivateCegid = async () => {
    const p = providers.find((x) => x.key === 'cegid_quadra');
    if (!p) return;

    if (useSharedCabinetKeys) {
      if (!codeDossier.trim()) {
        toast({
          title: 'Champs requis',
          description: 'Renseignez le code dossier (codeIbs) de cette filiale.',
          variant: 'destructive',
        });
        return;
      }
      try {
        await saveMutation.mutateAsync({
          enabled: true,
          provider: 'cegid_quadra',
          mode: p.mode as AccountingConfigUpdate['mode'],
          code_dossier_cegid: codeDossier.trim(),
          cegid_auth_mode: 'shared',
          clear_company_credentials: true,
          default_format: 'fec',
        });
        testMutation.mutate();
      } catch {
        /* toast géré par saveMutation */
      }
      return;
    }

    if (!loopApiKey || !apimSubscriptionKey || !codeDossier) {
      toast({
        title: 'Champs requis',
        description: 'Renseignez APIKey, subscription key et code dossier.',
        variant: 'destructive',
      });
      return;
    }
    try {
      await saveMutation.mutateAsync({
        enabled: true,
        provider: 'cegid_quadra',
        mode: p.mode as AccountingConfigUpdate['mode'],
        cegid_auth_mode: 'dedicated',
        code_dossier_cegid: codeDossier,
        credentials: {
          loop_apikey: loopApiKey,
          apim_subscription_key: apimSubscriptionKey,
          code_dossier: codeDossier,
          ...(cegidBaseUrl ? { api_base_url: cegidBaseUrl } : {}),
        },
        default_format: 'fec',
      });
      testMutation.mutate();
    } catch {
      /* toast géré par saveMutation */
    }
  };

  const retryMutation = useMutation({
    mutationFn: (id: string) => retryAccountingTransmission(companyId, id),
    onSuccess: (r) => {
      refreshExportsPageQueries(qc, companyId);
      toast({
        title: r.success ? 'Nouvelle tentative envoyée' : 'Échec',
        description: r.message,
        variant: r.success ? 'default' : 'destructive',
      });
    },
  });

  const handleSelectProvider = (key: string) => {
    setSelectedProvider(key);
    const p = providers.find((x) => x.key === key);
    if (key === 'manual') {
      saveMutation.mutate({
        enabled: true,
        provider: 'manual',
        mode: 'manual',
        force_manual: false,
      });
      setStep('done');
    } else if (p?.connector_ready) {
      if (key === 'cegid_quadra') {
        setCegidWizardMode('new');
        setStep('cegid_connect');
      } else {
        setStep('credentials');
      }
    } else {
      toast({
        title: 'Bientôt disponible',
        description: 'Ce connecteur sera activé par la plateforme EYWAI.',
      });
    }
  };

  const handleSaveCredentials = () => {
    const p = providers.find((x) => x.key === selectedProvider);
    if (!p) return;
    saveMutation.mutate({
      enabled: true,
      provider: selectedProvider,
      mode: p.mode as AccountingConfigUpdate['mode'],
      credentials: {
        api_key: apiKey,
        ...(apiBaseUrl ? { api_base_url: apiBaseUrl } : {}),
      },
      recipients_compta: recipients
        .split(/[\s,;]+/)
        .map((s) => s.trim())
        .filter(Boolean),
      default_format: defaultFormat,
      force_manual: forceManual,
    });
    setStep('done');
  };

  if (!companyId) return null;

  return (
    <Card className="relative border-primary/20">
      <ExportCardRefreshOverlay
        visible={isFetching && !isLoading}
        label="Actualisation de l'intégration…"
      />
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-lg">
          <Settings2 className="h-5 w-5" />
          Intégration comptable
          {config ? stateBadge(config.connection_state, config.provider) : null}
        </CardTitle>
        <CardDescription>
          Choisissez comment transmettre vos exports comptables. Le mode manuel reste
          toujours disponible, même avec une API active.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isLoading ? (
          <SharkFinLoader className="min-h-[160px]" label="Chargement…" />
        ) : (
          <>
            {step === 'choose' && (
              <div className="grid gap-3 sm:grid-cols-2">
                {availableProviders.map((p: ProviderDefinition) => (
                  <div
                    key={p.key}
                    className={cn(
                      'flex flex-col rounded-lg border p-4 transition-colors',
                      selectedProvider === p.key && 'border-primary bg-primary/5',
                      !p.connector_ready && p.key !== 'manual' && 'opacity-70',
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => p.key !== 'cegid_quadra' && handleSelectProvider(p.key)}
                      className={cn(
                        'flex items-start gap-3 text-left',
                        p.key === 'cegid_quadra' ? 'cursor-default' : 'hover:opacity-90',
                      )}
                    >
                      <ProviderLogo providerKey={p.key} size="lg" />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{p.name}</p>
                        <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
                          {p.description}
                        </p>
                        {p.key !== 'manual' && !p.connector_ready && (
                          <Badge variant="outline" className="mt-2 text-[10px]">
                            Bientôt
                          </Badge>
                        )}
                      </div>
                    </button>
                    {p.key === 'cegid_quadra' && p.connector_ready && (
                      <Button
                        type="button"
                        className="mt-4 w-full"
                        onClick={() => handleSelectProvider('cegid_quadra')}
                      >
                        Connecter Cegid Loop
                        <ExternalLink className="ml-2 h-4 w-4 opacity-70" />
                      </Button>
                    )}
                    {p.key === 'manual' && (
                      <Button
                        type="button"
                        variant="outline"
                        className="mt-4 w-full"
                        onClick={() => handleSelectProvider('manual')}
                      >
                        Utiliser le mode manuel
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {step === 'cegid_connect' && (
              <div className="space-y-4">
                {config?.has_platform_cegid_credentials ? (
                  <div className="space-y-2 rounded-lg border bg-muted/20 p-3">
                    <Label>Mode de connexion Cegid</Label>
                    <Select
                      value={cegidAuthMode}
                      onValueChange={(v: 'shared' | 'dedicated') => setCegidAuthMode(v)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="shared">
                          Clés cabinet du groupe (code dossier uniquement)
                        </SelectItem>
                        <SelectItem value="dedicated">
                          Clés dédiées à cette filiale
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    {useSharedCabinetKeys ? (
                      <p className="text-muted-foreground text-xs">
                        Les clés cabinet sont configurées par l&apos;administrateur. Indiquez
                        seulement le code dossier de cette entreprise.
                      </p>
                    ) : null}
                  </div>
                ) : null}
                <CegidConnectWizard
                  loopApiKey={loopApiKey}
                  apimSubscriptionKey={apimSubscriptionKey}
                  codeDossier={codeDossier}
                  cegidBaseUrl={cegidBaseUrl}
                  onLoopApiKeyChange={setLoopApiKey}
                  onApimSubscriptionKeyChange={setApimSubscriptionKey}
                  onCodeDossierChange={setCodeDossier}
                  onCegidBaseUrlChange={setCegidBaseUrl}
                  onBack={() => setStep('choose')}
                  onFinalize={handleTestAndActivateCegid}
                  isSaving={saveMutation.isPending}
                  isTesting={testMutation.isPending}
                  wizardMode={
                    useSharedCabinetKeys
                      ? 'dossier'
                      : cegidAuthMode === 'dedicated'
                        ? 'dedicated'
                        : 'full'
                  }
                  initialPhase={cegidWizardMode === 'edit' ? 'paste' : 'intro'}
                />
              </div>
            )}

            {step === 'credentials' && (
              <div className="space-y-4 rounded-lg border bg-muted/20 p-4">
                <div className="flex items-center gap-3">
                  <ProviderLogo providerKey={selectedProvider} size="lg" />
                  <div>
                    <p className="font-medium">{getProviderMeta(selectedProvider).name}</p>
                    <p className="text-muted-foreground text-xs">
                      Saisissez les identifiants fournis par votre éditeur.
                    </p>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Clé API</Label>
                  <Input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="••••••••"
                  />
                </div>
                <div className="space-y-1">
                  <Label>URL API (optionnel)</Label>
                  <Input
                    value={apiBaseUrl}
                    onChange={(e) => setApiBaseUrl(e.target.value)}
                    placeholder="https://api…"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" onClick={handleSaveCredentials} disabled={saveMutation.isPending}>
                    Enregistrer et activer
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setStep('choose')}>
                    Retour
                  </Button>
                </div>
              </div>
            )}

            {step === 'done' && config && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
                  <div className="flex items-center gap-3">
                    <ProviderLogo providerKey={config.provider} size="lg" />
                    <div>
                      <p className="font-medium">{getProviderMeta(config.provider).name}</p>
                      <p className="text-muted-foreground text-xs">
                        {config.force_manual
                          ? 'Envoi forcé en manuel'
                          : config.provider === 'manual'
                            ? 'Téléchargement et import manuel'
                            : config.provider === 'cegid_quadra' && config.connection_state === 'connected'
                            ? 'Écritures FEC transmises automatiquement vers Cegid Loop'
                            : config.provider === 'cegid_quadra'
                              ? 'Connexion Cegid Loop à finaliser'
                              : 'Transmission automatique si API active'}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {config.provider === 'cegid_quadra' && config.connection_state !== 'connected' && (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => {
                          setCegidWizardMode('new');
                          setStep('cegid_connect');
                        }}
                      >
                        Reprendre la connexion
                      </Button>
                    )}
                    <Button type="button" variant="outline" size="sm" onClick={() => setStep('choose')}>
                      Changer
                    </Button>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex items-center justify-between gap-4">
                    <Label htmlFor="acc-enabled">Intégration active</Label>
                    <Switch
                      id="acc-enabled"
                      checked={enabled}
                      onCheckedChange={(v) => {
                        setEnabled(v);
                        saveMutation.mutate({ enabled: v });
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <Label htmlFor="force-manual">Forcer le mode manuel</Label>
                      <p className="text-muted-foreground text-xs">
                        Même avec une API, ne pas transmettre automatiquement
                      </p>
                    </div>
                    <Switch
                      id="force-manual"
                      checked={forceManual}
                      onCheckedChange={(v) => {
                        setForceManual(v);
                        saveMutation.mutate({ force_manual: v });
                      }}
                    />
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label>Format par défaut</Label>
                    <Select value={defaultFormat} onValueChange={setDefaultFormat}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="csv">CSV</SelectItem>
                        <SelectItem value="xlsx">Excel (XLSX)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label>Destinataires compta (e-mail)</Label>
                    <Input
                      value={recipients}
                      onChange={(e) => setRecipients(e.target.value)}
                      placeholder="compta@cabinet.fr"
                    />
                  </div>
                </div>

                {config.last_test_at && config.provider === 'cegid_quadra' && (
                  <p className="text-muted-foreground text-xs">
                    Dernier test :{' '}
                    {new Date(config.last_test_at).toLocaleString('fr-FR', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                )}

                {config.last_test_message && (
                  <p className="text-muted-foreground flex items-start gap-2 text-sm">
                    {config.last_test_status === 'connected' ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
                    ) : (
                      <Circle className="mt-0.5 h-4 w-4 shrink-0" />
                    )}
                    {config.last_test_message}
                  </p>
                )}

                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={saveMutation.isPending}
                    onClick={() =>
                      saveMutation.mutate({
                        recipients_compta: recipients
                          .split(/[\s,;]+/)
                          .map((s) => s.trim())
                          .filter(Boolean),
                        default_format: defaultFormat,
                      })
                    }
                  >
                    Enregistrer
                  </Button>
                  {config.provider === 'cegid_quadra' ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={testMutation.isPending}
                      onClick={() => {
                        setCegidWizardMode('edit');
                        setStep('cegid_connect');
                      }}
                    >
                      Modifier la connexion Cegid
                    </Button>
                  ) : (
                    config.provider !== 'manual' && (
                      <Button
                        type="button"
                        variant="outline"
                        disabled={testMutation.isPending || !enabled}
                        onClick={() => testMutation.mutate()}
                      >
                        Tester la connexion
                      </Button>
                    )
                  )}
                  {getProviderMeta(config.provider).docUrl && (
                    <Button type="button" variant="ghost" asChild>
                      <a
                        href={getProviderMeta(config.provider).docUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Documentation
                        <ExternalLink className="ml-1 h-3.5 w-3.5" />
                      </a>
                    </Button>
                  )}
                </div>
              </div>
            )}

            <Separator />

            <div>
              <div className="mb-3 flex items-center justify-between">
                <h4 className="text-sm font-semibold">Derniers envois compta</h4>
                <Download className="text-muted-foreground h-4 w-4" />
              </div>
              {(transmissionsData?.transmissions ?? []).length === 0 ? (
                <p className="text-muted-foreground text-sm">Aucun envoi enregistré.</p>
              ) : (
                <ul className="space-y-2">
                  {transmissionsData?.transmissions.map((tx) => (
                    <li
                      key={tx.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                    >
                      <div>
                        <span className="font-medium">{tx.period}</span>
                        <span className="text-muted-foreground mx-2">·</span>
                        <ProviderLogo providerKey={tx.provider} size="sm" className="inline-block align-middle" />
                      </div>
                      <div className="flex items-center gap-2">
                        <TransmissionStatusBadge status={tx.status} />
                        {['failed', 'sent'].includes(tx.status) && (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2"
                            disabled={retryMutation.isPending}
                            onClick={() => retryMutation.mutate(tx.id)}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                      {tx.error_message && (
                        <p className="text-destructive w-full text-xs">{tx.error_message}</p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
