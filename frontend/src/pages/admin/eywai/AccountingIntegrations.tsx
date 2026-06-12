import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import {
  TRANSMISSION_STATUS_LABELS,
  type TransmissionStatus,
} from '@/api/accountingIntegration';
import {
  adminRetryAccountingTransmission,
  getAdminAccountingTransmissions,
  getPlatformAccountingCatalog,
  updatePlatformAccountingProvider,
  type PlatformCatalogResponse,
} from '@/api/accountingIntegrationsAdmin';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import { TransmissionStatusBadge } from '@/features/accounting-integration/components/TransmissionStatusBadge';
import { CegidAdminConnectPanel } from '@/features/accounting-integration/components/CegidAdminConnectPanel';
import { PlatformProviderCard } from '@/features/accounting-integration/components/PlatformProviderCard';
import { ProviderLogo } from '@/components/integrations/ProviderLogo';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';

const RETRYABLE_STATUSES: TransmissionStatus[] = ['failed', 'rejected', 'generated', 'queued'];

const STATUS_FILTERS: TransmissionStatus[] = [
  'generated',
  'queued',
  'sent',
  'transmitted',
  'acknowledged',
  'rejected',
  'manual',
  'failed',
];

const PROVIDER_DISPLAY_ORDER: Record<string, number> = {
  cegid_quadra: 0,
  manual: 1,
};

function sortPlatformProviders<T extends { provider_key: string; name: string }>(
  providers: T[],
): T[] {
  return [...providers].sort((a, b) => {
    const rankA = PROVIDER_DISPLAY_ORDER[a.provider_key] ?? 100;
    const rankB = PROVIDER_DISPLAY_ORDER[b.provider_key] ?? 100;
    if (rankA !== rankB) return rankA - rankB;
    return a.name.localeCompare(b.name, 'fr');
  });
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

export default function AccountingIntegrations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [period, setPeriod] = useState('');
  const [providerFilter, setProviderFilter] = useState('all');
  const [credInputs, setCredInputs] = useState<Record<string, string>>({});

  const { data: catalog, isLoading: catalogLoading } = useQuery({
    queryKey: ['admin-accounting-catalog'],
    queryFn: getPlatformAccountingCatalog,
  });

  const { data: txData, isLoading: txLoading } = useQuery({
    queryKey: ['admin-accounting-transmissions', statusFilter, period, providerFilter],
    queryFn: () =>
      getAdminAccountingTransmissions({
        status: statusFilter === 'all' ? undefined : (statusFilter as TransmissionStatus),
        period: period || undefined,
        provider: providerFilter === 'all' ? undefined : providerFilter,
        limit: 50,
      }),
  });

  const updateProvider = useMutation({
    mutationFn: ({
      key,
      body,
    }: {
      key: string;
      body: Parameters<typeof updatePlatformAccountingProvider>[1];
    }) => updatePlatformAccountingProvider(key, body),
    onMutate: async ({ key, body }) => {
      await qc.cancelQueries({ queryKey: ['admin-accounting-catalog'] });
      const previous = qc.getQueryData<PlatformCatalogResponse>(['admin-accounting-catalog']);
      if (previous && body.enabled !== undefined) {
        qc.setQueryData<PlatformCatalogResponse>(['admin-accounting-catalog'], (old) => {
          if (!old) return old;
          const providers = old.providers.map((p) =>
            p.provider_key === key ? { ...p, enabled: body.enabled! } : p,
          );
          const enabledCount = providers.filter((p) => p.enabled).length;
          return {
            ...old,
            providers,
            stats: {
              ...old.stats,
              providers_enabled: enabledCount,
              enabled_providers: enabledCount,
            },
          };
        });
      }
      return { previous };
    },
    onSuccess: (updated, { key, body }) => {
      qc.setQueryData<PlatformCatalogResponse>(['admin-accounting-catalog'], (old) => {
        if (!old) return old;
        const providers = old.providers.map((p) =>
          p.provider_key === key ? { ...p, ...updated } : p,
        );
        const enabledCount = providers.filter((p) => p.enabled).length;
        return {
          ...old,
          providers,
          stats: {
            ...old.stats,
            providers_enabled: enabledCount,
            enabled_providers: enabledCount,
          },
        };
      });
      if (body.platform_credentials) {
        toast({ title: 'Credentials enregistrés' });
      }
    },
    onError: (e: Error, _vars, context) => {
      if (context?.previous) {
        qc.setQueryData(['admin-accounting-catalog'], context.previous);
      }
      toast({ title: 'Erreur', description: e.message, variant: 'destructive' });
    },
  });

  const retryTx = useMutation({
    mutationFn: ({ id, companyId }: { id: string; companyId: string }) =>
      adminRetryAccountingTransmission(id, companyId),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['admin-accounting-transmissions'] });
      toast({
        title: r.success ? 'Nouvelle tentative' : 'Échec',
        description: r.message,
        variant: r.success ? 'default' : 'destructive',
      });
    },
  });

  const counts = txData?.counts_by_status ?? {};
  const stats = catalog?.stats ?? {};
  const total = useMemo(
    () => Object.values(counts).reduce((a, b) => a + b, 0),
    [counts],
  );

  const sortedProviders = useMemo(
    () => sortPlatformProviders(catalog?.providers ?? []),
    [catalog?.providers],
  );

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Intégrations comptables"
        description="Catalogue des connecteurs, activation plateforme et monitoring des transmissions."
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Fournisseurs actifs</p>
            {catalogLoading ? (
              <Skeleton className="mt-1 h-8 w-12" />
            ) : (
              <p className="mt-1 text-2xl font-bold">{stats.enabled_providers ?? 0}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Transmissions (échantillon)</p>
            {txLoading ? (
              <Skeleton className="mt-1 h-8 w-12" />
            ) : (
              <p className="mt-1 text-2xl font-bold">{total}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Succès (sent/ack)</p>
            {txLoading ? (
              <Skeleton className="mt-1 h-8 w-12" />
            ) : (
              <p className="mt-1 text-2xl font-bold">
                {(counts.sent ?? 0) + (counts.acknowledged ?? 0)}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Échecs</p>
            {txLoading ? (
              <Skeleton className="mt-1 h-8 w-12" />
            ) : (
              <p className="mt-1 text-2xl font-bold text-destructive">{counts.failed ?? 0}</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Catalogue fournisseurs</CardTitle>
          <CardDescription>
            Activez les connecteurs pour les entreprises. La connexion Cegid se configure par
            entreprise (clés du cabinet comptable).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {catalogLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:items-start">
              {sortedProviders.map((p) => (
                <PlatformProviderCard
                  key={p.provider_key}
                  providerKey={p.provider_key}
                  name={p.name}
                  description={p.description}
                  enabled={p.enabled}
                  connectorReady={p.connector_ready}
                  hasPlatformCredentials={p.has_platform_credentials}
                  toggleDisabled={
                    updateProvider.isPending && updateProvider.variables?.key === p.provider_key
                  }
                  onEnabledChange={(v) =>
                    updateProvider.mutate({ key: p.provider_key, body: { enabled: v } })
                  }
                  footer={p.last_test_message ?? undefined}
                >
                  {p.provider_key === 'cegid_quadra' ? (
                    <CegidAdminConnectPanel providerEnabled={p.enabled} />
                  ) : p.provider_key !== 'manual' ? (
                    <div className="space-y-2">
                      <Label className="text-xs">Clé API plateforme (optionnel)</Label>
                      <Input
                        type="password"
                        placeholder="••••••••"
                        value={credInputs[p.provider_key] ?? ''}
                        onChange={(e) =>
                          setCredInputs((prev) => ({
                            ...prev,
                            [p.provider_key]: e.target.value,
                          }))
                        }
                      />
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!credInputs[p.provider_key] || updateProvider.isPending}
                        onClick={() =>
                          updateProvider.mutate({
                            key: p.provider_key,
                            body: {
                              platform_credentials: { api_key: credInputs[p.provider_key] },
                            },
                          })
                        }
                      >
                        Enregistrer credentials
                      </Button>
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-xs">
                      Mode manuel — toujours disponible pour les entreprises, sans configuration
                      plateforme.
                    </p>
                  )}
                </PlatformProviderCard>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base">Monitoring transmissions</CardTitle>
          <div className="flex flex-wrap items-center gap-3">
            <Input
              placeholder="Période (AAAA-MM)"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="w-36"
            />
            <Select value={providerFilter} onValueChange={setProviderFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Fournisseur" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous fournisseurs</SelectItem>
                {(catalog?.providers ?? []).map((p) => (
                  <SelectItem key={p.provider_key} value={p.provider_key}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Statut" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous statuts</SelectItem>
                {STATUS_FILTERS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {TRANSMISSION_STATUS_LABELS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {txLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entreprise</TableHead>
                  <TableHead>Période</TableHead>
                  <TableHead>Fournisseur</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(txData?.transmissions ?? []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-muted-foreground text-center">
                      Aucune transmission.
                    </TableCell>
                  </TableRow>
                ) : (
                  txData?.transmissions.map((tx) => (
                    <TableRow key={tx.id}>
                      <TableCell>{tx.company_name?.trim() || '—'}</TableCell>
                      <TableCell>{tx.period}</TableCell>
                      <TableCell>
                        <ProviderLogo providerKey={tx.provider} size="sm" />
                      </TableCell>
                      <TableCell>
                        <TransmissionStatusBadge status={tx.status} />
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {formatDate(tx.submitted_at ?? tx.created_at)}
                        {tx.error_message ? (
                          <p className="text-destructive mt-1">{tx.error_message}</p>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-right">
                        {RETRYABLE_STATUSES.includes(tx.status) ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={retryTx.isPending}
                            onClick={() =>
                              retryTx.mutate({ id: tx.id, companyId: tx.company_id })
                            }
                          >
                            <RefreshCw className="h-4 w-4" />
                            Relancer
                          </Button>
                        ) : (
                          <span className="text-muted-foreground text-sm">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
