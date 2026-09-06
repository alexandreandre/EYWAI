import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Calculator, CheckCircle2, Circle } from 'lucide-react';
import { useCompany } from '@/contexts/CompanyContext';
import { useToast } from '@/hooks/use-toast';
import {
  getAccountingConfig,
  testAccountingConnection,
  updateAccountingConfig,
  type AccountingConfig,
  type AccountingConfigUpdate,
  type AccountingMode,
} from '@/api/accountingIntegration';
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
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { ExportCardRefreshOverlay } from '@/components/exports/ExportCardRefreshOverlay';
import { exportsLiveQueryOptions, refreshExportsPageQueries } from '@/lib/exportsQuery';
import { Switch } from '@/components/ui/switch';

const MODE_OPTIONS: { value: AccountingMode; label: string; hint: string }[] = [
  {
    value: 'manual',
    label: 'Manuel',
    hint: 'Téléchargez les fichiers et importez-les dans votre logiciel comptable.',
  },
  {
    value: 'api_quadra',
    label: 'API Quadra',
    hint: 'Connexion API (bientôt disponible — stub).',
  },
  {
    value: 'api_sage',
    label: 'API Sage',
    hint: 'Connexion API (bientôt disponible — stub).',
  },
  {
    value: 'api_pennylane',
    label: 'API Pennylane',
    hint: 'Connexion API (bientôt disponible — stub).',
  },
];

function stateBadge(state: AccountingConfig['connection_state']) {
  if (state === 'manual') return <Badge variant="secondary">Manuel</Badge>;
  if (state === 'stub') return <Badge variant="outline">API en préparation</Badge>;
  if (state === 'connected') return <Badge>Géré par API</Badge>;
  return <Badge variant="outline">Non configuré</Badge>;
}

export function AccountingIntegrationCard() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const { toast } = useToast();
  const qc = useQueryClient();

  const { data: config, isLoading, isFetching } = useQuery({
    queryKey: ['accounting-integration-config', companyId],
    queryFn: () => getAccountingConfig(companyId),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const [enabled, setEnabled] = useState(false);
  const [mode, setMode] = useState<AccountingMode>('manual');
  const [recipients, setRecipients] = useState('');

  const syncForm = (c: AccountingConfig) => {
    setEnabled(c.enabled);
    setMode(c.mode);
    setRecipients((c.recipients_compta ?? []).join(', '));
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
      toast({
        title: r.success ? 'Connexion OK' : 'Test de connexion',
        description: r.message,
        variant: r.success ? 'default' : 'destructive',
      });
    },
    onError: (e: Error) => {
      toast({ title: 'Erreur', description: e.message, variant: 'destructive' });
    },
  });

  if (!companyId) return null;

  return (
    <Card className="relative">
      <ExportCardRefreshOverlay
        visible={isFetching && !isLoading}
        label="Actualisation de l'intégration…"
      />
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Calculator className="h-5 w-5" />
          Intégration comptable
          {config ? stateBadge(config.connection_state) : null}
        </CardTitle>
        <CardDescription>
          Choisissez comment transmettre vos exports comptables (manuel ou API logiciel).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <SharkFinLoader className="min-h-[120px]" label="Chargement de l'intégration comptable…" />
        ) : (
          <>
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="accounting-enabled">Activer l&apos;intégration</Label>
              <Switch
                id="accounting-enabled"
                checked={enabled}
                onCheckedChange={setEnabled}
              />
            </div>
            <div className="space-y-1">
              <Label>Mode de transmission</Label>
              <Select value={mode} onValueChange={(v) => setMode(v as AccountingMode)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODE_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-muted-foreground text-xs">
                {MODE_OPTIONS.find((o) => o.value === mode)?.hint}
              </p>
            </div>
            <div className="space-y-1">
              <Label>Destinataires compta (e-mail)</Label>
              <Input
                value={recipients}
                onChange={(e) => setRecipients(e.target.value)}
                placeholder="compta@votre-entreprise.fr"
              />
            </div>
            {config?.last_test_message ? (
              <p className="text-muted-foreground flex items-start gap-2 text-sm">
                {config.last_test_status === 'manual' || config.last_test_status === 'stub' ? (
                  <Circle className="mt-0.5 h-4 w-4 shrink-0" />
                ) : (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
                )}
                {config.last_test_message}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={saveMutation.isPending}
                onClick={() =>
                  saveMutation.mutate({
                    enabled,
                    mode,
                    recipients_compta: recipients
                      .split(/[\s,;]+/)
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
              >
                Enregistrer
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={testMutation.isPending || !enabled}
                onClick={() => testMutation.mutate()}
              >
                Tester la connexion
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
