import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getNetEntreprisesConfig,
  updateNetEntreprisesConfig,
  testNetEntreprisesConnection,
  getAdminNetEntreprisesConfig,
  updateAdminNetEntreprisesConfig,
  type NetEntreprisesConfig,
  type NetEntreprisesConfigUpdate,
  type TransmissionMode,
} from '@/api/netEntreprises';
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
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { CheckCircle2, Circle, ExternalLink, ShieldCheck } from 'lucide-react';
import NetEntreprisesLogo from './NetEntreprisesLogo';

const NET_ENTREPRISES_URL = 'https://www.net-entreprises.fr';
const NET_ENTREPRISES_DSN_URL =
  'https://www.net-entreprises.fr/declaration/dsn-tableau-de-bord/';

const MODE_OPTIONS: { value: TransmissionMode; label: string; hint: string }[] = [
  {
    value: 'manual',
    label: 'Dépôt manuel',
    hint: 'Le fichier DSN est généré puis déposé à la main sur net-entreprises.fr.',
  },
  {
    value: 'api_certificat',
    label: 'API — certificat',
    hint: 'Envoi automatique via certificat électronique (à activer une fois branché).',
  },
  {
    value: 'api_declarant',
    label: 'API — déclarant',
    hint: 'Envoi automatique via identifiants déclarant (à activer une fois branché).',
  },
];

type FormState = {
  enabled: boolean;
  mode: TransmissionMode;
  siret_declarant: string;
  raison_sociale_declarant: string;
  identifiant: string;
  contact_email: string;
  certificat_label: string;
  certificat_expires_at: string;
  secret: string;
};

function configToForm(c: NetEntreprisesConfig): FormState {
  return {
    enabled: c.enabled,
    mode: c.mode,
    siret_declarant: c.siret_declarant ?? '',
    raison_sociale_declarant: c.raison_sociale_declarant ?? '',
    identifiant: c.identifiant ?? '',
    contact_email: c.contact_email ?? '',
    certificat_label: c.certificat_label ?? '',
    certificat_expires_at: c.certificat_expires_at ?? '',
    secret: '',
  };
}

function formToPayload(form: FormState): NetEntreprisesConfigUpdate {
  const payload: NetEntreprisesConfigUpdate = {
    enabled: form.enabled,
    mode: form.mode,
    siret_declarant: form.siret_declarant.trim() || null,
    raison_sociale_declarant: form.raison_sociale_declarant.trim() || null,
    identifiant: form.identifiant.trim() || null,
    contact_email: form.contact_email.trim() || null,
    certificat_label: form.certificat_label.trim() || null,
    certificat_expires_at: form.certificat_expires_at.trim() || null,
  };
  if (form.secret.trim()) {
    payload.secret = form.secret.trim();
  }
  return payload;
}

function StateBadge({ state }: { state: NetEntreprisesConfig['connection_state'] }) {
  if (state === 'connected') {
    return <Badge variant="success">Connecté (API)</Badge>;
  }
  if (state === 'manual') {
    return <Badge variant="warning">Mode manuel</Badge>;
  }
  return <Badge variant="secondary">Non configuré</Badge>;
}

function OnboardingStep({ done, children }: { done: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      {done ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
      ) : (
        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      )}
      <span className={done ? 'text-muted-foreground line-through' : ''}>{children}</span>
    </li>
  );
}

export interface NetEntreprisesConfigCardProps {
  /** Si fourni, mode pilotage super-admin (override) ; sinon mode RH (entreprise active). */
  companyId?: string;
  /** Désactive l'édition (lecture seule). */
  readOnly?: boolean;
}

export function NetEntreprisesConfigCard({
  companyId,
  readOnly = false,
}: NetEntreprisesConfigCardProps) {
  const isAdmin = Boolean(companyId);
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const queryKey = ['net-entreprises-config', companyId ?? 'active'];

  const { data, isLoading, isError } = useQuery({
    queryKey,
    queryFn: () =>
      isAdmin ? getAdminNetEntreprisesConfig(companyId as string) : getNetEntreprisesConfig(),
  });

  const [form, setForm] = useState<FormState | null>(null);

  useEffect(() => {
    if (data) setForm(configToForm(data));
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (payload: NetEntreprisesConfigUpdate) =>
      isAdmin
        ? updateAdminNetEntreprisesConfig(companyId as string, payload)
        : updateNetEntreprisesConfig(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKey, saved);
      setForm(configToForm(saved));
      toast({
        title: 'Enregistré',
        description: 'Configuration Net-entreprises mise à jour.',
      });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Enregistrement impossible.',
        variant: 'destructive',
      });
    },
  });

  const testMutation = useMutation({
    mutationFn: testNetEntreprisesConnection,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey });
      toast({
        title: res.success ? 'Connexion OK' : 'Connexion non disponible',
        description: res.message,
        variant: res.success ? 'default' : 'destructive',
      });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Test impossible.',
        variant: 'destructive',
      });
    },
  });

  if (isError) {
    return (
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Télétransmission Net-entreprises</CardTitle>
          <CardDescription className="text-destructive">
            Chargement de la configuration impossible.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (isLoading || !form || !data) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-64" />
          <Skeleton className="mt-2 h-4 w-full max-w-md" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  const isApiMode = form.mode === 'api_certificat' || form.mode === 'api_declarant';
  const disabled = readOnly || saveMutation.isPending;

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((p) => (p ? { ...p, [key]: value } : p));

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-5 w-5 text-primary" />
              Télétransmission DSN — Net-entreprises
            </CardTitle>
            <CardDescription>
              Renseignez les informations de connexion de l'entreprise. Tant que la
              connexion API n'est pas activée, la DSN reste à déposer manuellement.
            </CardDescription>
          </div>
          <div className="flex flex-col items-end gap-2">
            <NetEntreprisesLogo />
            <StateBadge state={data.connection_state} />
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Onboarding */}
        <div className="rounded-lg border bg-muted/30 p-4">
          <p className="mb-2 text-sm font-medium">Activer la télétransmission en 3 étapes</p>
          <ul className="space-y-1.5">
            <OnboardingStep done={Boolean(form.siret_declarant && form.raison_sociale_declarant)}>
              Renseigner le SIRET et la raison sociale du déclarant
            </OnboardingStep>
            <OnboardingStep done={data.has_secret || Boolean(form.identifiant)}>
              Ajouter l'identifiant / certificat Net-entreprises
            </OnboardingStep>
            <OnboardingStep done={data.connection_state === 'connected'}>
              Activer le mode API et tester la connexion
            </OnboardingStep>
          </ul>
          <div className="mt-3 flex flex-wrap gap-3">
            <a
              href={NET_ENTREPRISES_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              net-entreprises.fr <ExternalLink className="h-3.5 w-3.5" />
            </a>
            <a
              href={NET_ENTREPRISES_DSN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              Tableau de bord DSN <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>

        {/* Mode + activation */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <Label>Mode de dépôt</Label>
            <Select
              value={form.mode}
              onValueChange={(v: TransmissionMode) => set('mode', v)}
              disabled={disabled}
            >
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
            <p className="text-xs text-muted-foreground">
              {MODE_OPTIONS.find((o) => o.value === form.mode)?.hint}
            </p>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
            <div>
              <Label htmlFor="ne-enabled">Activer la télétransmission</Label>
              <p className="text-sm text-muted-foreground">
                En mode API, autorise l'envoi automatique (sinon dépôt manuel).
              </p>
            </div>
            <Switch
              id="ne-enabled"
              checked={form.enabled}
              onCheckedChange={(v) => set('enabled', v)}
              disabled={disabled}
            />
          </div>
        </div>

        <Separator />

        {/* Identité déclarant */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="ne-siret">SIRET déclarant</Label>
            <Input
              id="ne-siret"
              value={form.siret_declarant}
              onChange={(e) => set('siret_declarant', e.target.value)}
              placeholder="14 chiffres"
              disabled={disabled}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ne-raison">Raison sociale du déclarant</Label>
            <Input
              id="ne-raison"
              value={form.raison_sociale_declarant}
              onChange={(e) => set('raison_sociale_declarant', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ne-contact">Email de contact</Label>
            <Input
              id="ne-contact"
              type="email"
              value={form.contact_email}
              onChange={(e) => set('contact_email', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ne-identifiant">Identifiant Net-entreprises</Label>
            <Input
              id="ne-identifiant"
              value={form.identifiant}
              onChange={(e) => set('identifiant', e.target.value)}
              autoComplete="off"
              disabled={disabled}
            />
          </div>
        </div>

        {/* Bloc API (certificat / secret) */}
        {isApiMode && (
          <div className="grid gap-4 rounded-lg border border-dashed p-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="ne-cert-label">Libellé du certificat</Label>
              <Input
                id="ne-cert-label"
                value={form.certificat_label}
                onChange={(e) => set('certificat_label', e.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="ne-cert-exp">Échéance du certificat</Label>
              <Input
                id="ne-cert-exp"
                type="date"
                value={form.certificat_expires_at}
                onChange={(e) => set('certificat_expires_at', e.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="grid gap-2 md:col-span-2">
              <Label htmlFor="ne-secret">
                Secret / mot de passe {data.has_secret && '(déjà enregistré)'}
              </Label>
              <Input
                id="ne-secret"
                type="password"
                value={form.secret}
                onChange={(e) => set('secret', e.target.value)}
                placeholder={data.has_secret ? '•••••••• (laisser vide pour conserver)' : ''}
                autoComplete="new-password"
                disabled={disabled}
              />
              <p className="text-xs text-muted-foreground">
                Le secret est stocké côté serveur et n'est jamais réaffiché.
              </p>
            </div>
          </div>
        )}

        {data.last_test_message && (
          <p className="text-xs text-muted-foreground">
            Dernier test : {data.last_test_status} — {data.last_test_message}
          </p>
        )}

        {!readOnly && (
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => form && saveMutation.mutate(formToPayload(form))} disabled={disabled}>
              {saveMutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
            {!isAdmin && (
              <Button
                variant="outline"
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
              >
                {testMutation.isPending ? 'Test en cours…' : 'Tester la connexion'}
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default NetEntreprisesConfigCard;
