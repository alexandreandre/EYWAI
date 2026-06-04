import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getEmailSettings,
  updateEmailSettings,
  sendTestEmail,
  type EmailSettings,
  type EmailSettingsUpdate,
  type SmtpSecurity,
} from '@/api/emailSettings';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { useToast } from '@/hooks/use-toast';
import { AlertCircle, CheckCircle2, ChevronDown, Mail } from 'lucide-react';
import { cn } from '@/lib/utils';

type SmtpPresetId = 'gmail' | 'microsoft' | 'brevo' | 'custom';

const SMTP_PRESETS: Record<
  Exclude<SmtpPresetId, 'custom'>,
  { label: string; host: string; port: number; security: SmtpSecurity; hint: string }
> = {
  gmail: {
    label: 'Gmail / Google Workspace',
    host: 'smtp.gmail.com',
    port: 587,
    security: 'starttls',
    hint: 'Utilisez un mot de passe d’application Google (pas votre mot de passe habituel).',
  },
  microsoft: {
    label: 'Microsoft 365 / Outlook',
    host: 'smtp.office365.com',
    port: 587,
    security: 'starttls',
    hint: 'Compte Microsoft 365 avec envoi SMTP activé.',
  },
  brevo: {
    label: 'Brevo (ex-Sendinblue)',
    host: 'smtp-relay.brevo.com',
    port: 587,
    security: 'starttls',
    hint: 'Identifiant et clé SMTP depuis votre compte Brevo.',
  },
};

type FormState = {
  preset: SmtpPresetId;
  smtp_host: string;
  smtp_port: string;
  smtp_user: string;
  smtp_password: string;
  smtp_security: SmtpSecurity;
  from_email: string;
  from_name: string;
  reply_to: string;
  support_email: string;
  extra_support_emails: string;
};

function detectPreset(host: string): SmtpPresetId {
  const h = host.toLowerCase();
  if (h.includes('gmail')) return 'gmail';
  if (h.includes('office365') || h.includes('outlook')) return 'microsoft';
  if (h.includes('brevo') || h.includes('sendinblue')) return 'brevo';
  return h ? 'custom' : 'gmail';
}

function settingsToForm(s: EmailSettings): FormState {
  const host = s.smtp_host ?? '';
  const [primary, ...rest] =
    s.support_recipients.length > 0 ? s.support_recipients : ['contact@eywai.fr'];
  return {
    preset: detectPreset(host),
    smtp_host: host,
    smtp_port: String(s.smtp_port ?? 587),
    smtp_user: s.smtp_user ?? '',
    smtp_password: '',
    smtp_security: s.smtp_security,
    from_email: s.from_email ?? s.smtp_user ?? '',
    from_name: s.from_name || 'EYWAI',
    reply_to: s.reply_to ?? '',
    support_email: primary,
    extra_support_emails: rest.join('\n'),
  };
}

function formToPayload(form: FormState): EmailSettingsUpdate {
  const extra = form.extra_support_emails
    .split(/[\n,;]+/)
    .map((e) => e.trim())
    .filter(Boolean);
  const support = [form.support_email.trim(), ...extra].filter(Boolean);

  const payload: EmailSettingsUpdate = {
    is_active: true,
    smtp_host: form.smtp_host.trim() || null,
    smtp_port: parseInt(form.smtp_port, 10) || 587,
    smtp_user: form.smtp_user.trim() || null,
    smtp_security: form.smtp_security,
    from_email: form.from_email.trim() || form.smtp_user.trim() || null,
    from_name: form.from_name.trim() || 'EYWAI',
    reply_to: form.reply_to.trim() || null,
    support_recipients: support,
  };
  if (form.smtp_password.trim()) {
    payload.smtp_password = form.smtp_password.trim();
  }
  return payload;
}

function StatusBanner({
  configured,
  source,
}: {
  configured: boolean;
  source: EmailSettings['effective_source'];
}) {
  if (configured) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-success/30 bg-success/5 px-4 py-3 text-sm">
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
        <div>
          <p className="font-medium text-foreground">Envoi opérationnel</p>
          <p className="text-muted-foreground">
            Les mails automatiques (mot de passe oublié, tickets support) peuvent être envoyés.
            {source === 'environment' ? ' Configuration actuelle : serveur (.env).' : ''}
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm">
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
      <div>
        <p className="font-medium text-foreground">Configuration incomplète</p>
        <p className="text-muted-foreground">
          Renseignez le compte d’envoi et son mot de passe, puis testez avant d’enregistrer.
        </p>
      </div>
    </div>
  );
}

export default function EmailSettingsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);
  const [testEmail, setTestEmail] = useState('');
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-email-settings'],
    queryFn: getEmailSettings,
  });

  useEffect(() => {
    if (data) {
      setForm(settingsToForm(data));
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (payload: EmailSettingsUpdate) => updateEmailSettings(payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(['admin-email-settings'], updated);
      setForm(settingsToForm(updated));
      toast({
        title: 'Enregistré',
        description: 'Les mails automatiques utiliseront cette configuration.',
      });
    },
    onError: (err: Error) => {
      toast({
        title: 'Erreur',
        description: err.message || 'Impossible d’enregistrer.',
        variant: 'destructive',
      });
    },
  });

  const testMutation = useMutation({
    mutationFn: (email: string) => sendTestEmail({ to_email: email }),
    onSuccess: (result) => {
      toast({
        title: result.success ? 'Test réussi' : 'Test échoué',
        description: result.message,
        variant: result.success ? 'default' : 'destructive',
      });
    },
    onError: (err: Error) => {
      toast({
        title: 'Erreur',
        description: err.message || 'Impossible d’envoyer le test.',
        variant: 'destructive',
      });
    },
  });

  const applyPreset = (presetId: SmtpPresetId) => {
    if (!form || presetId === 'custom') {
      if (form) setForm({ ...form, preset: 'custom' });
      return;
    }
    const p = SMTP_PRESETS[presetId];
    setForm({
      ...form,
      preset: presetId,
      smtp_host: p.host,
      smtp_port: String(p.port),
      smtp_security: p.security,
    });
  };

  const handleSmtpUserChange = (value: string) => {
    if (!form) return;
    const next = { ...form, smtp_user: value };
    if (!form.from_email.trim() || form.from_email === form.smtp_user) {
      next.from_email = value;
    }
    setForm(next);
  };

  const handleSave = () => {
    if (!form) return;
    if (!form.support_email.trim()) {
      toast({
        title: 'Adresse support requise',
        description: 'Indiquez l’e-mail qui reçoit les tickets support.',
        variant: 'destructive',
      });
      return;
    }
    if (!form.smtp_user.trim()) {
      toast({
        title: 'Compte d’envoi requis',
        description: 'Indiquez l’e-mail ou l’identifiant SMTP.',
        variant: 'destructive',
      });
      return;
    }
    saveMutation.mutate(formToPayload(form));
  };

  const handleTest = () => {
    const email = testEmail.trim() || form?.smtp_user.trim() || '';
    if (!email) {
      toast({
        title: 'Adresse requise',
        description: 'Saisissez une adresse pour recevoir le test.',
        variant: 'destructive',
      });
      return;
    }
    testMutation.mutate(email);
  };

  if (isLoading || !form) {
    return (
      <div className="mx-auto max-w-2xl space-y-6 p-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  const presetHint =
    form.preset !== 'custom' ? SMTP_PRESETS[form.preset].hint : null;

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <AdminPageHeader
        title="Mails automatiques"
        description="Adresses d’envoi et de réception pour les e-mails envoyés par EYWAI (mot de passe oublié, support)."
      />

      <StatusBanner
        configured={data?.is_configured ?? false}
        source={data?.effective_source ?? 'none'}
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Mail className="h-5 w-5 text-muted-foreground" />
            Paramètres principaux
          </CardTitle>
          <CardDescription>
            Ce que vos utilisateurs voient et où arrivent les demandes support.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="from-email">Adresse d’envoi visible</Label>
              <Input
                id="from-email"
                type="email"
                value={form.from_email}
                onChange={(e) => setForm({ ...form, from_email: e.target.value })}
                placeholder="noreply@eywai.fr"
              />
              <p className="text-xs text-muted-foreground">
                Adresse affichée comme expéditeur des mails automatiques.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="from-name">Nom affiché</Label>
              <Input
                id="from-name"
                value={form.from_name}
                onChange={(e) => setForm({ ...form, from_name: e.target.value })}
                placeholder="EYWAI"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="support-email">Tickets support reçus sur</Label>
              <Input
                id="support-email"
                type="email"
                value={form.support_email}
                onChange={(e) => setForm({ ...form, support_email: e.target.value })}
                placeholder="contact@eywai.fr"
              />
            </div>
          </div>

          <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
            <p className="text-sm font-medium">Compte d’envoi (SMTP)</p>
            <div className="space-y-2">
              <Label htmlFor="smtp-preset">Fournisseur</Label>
              <Select
                value={form.preset}
                onValueChange={(v) => applyPreset(v as SmtpPresetId)}
              >
                <SelectTrigger id="smtp-preset">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gmail">{SMTP_PRESETS.gmail.label}</SelectItem>
                  <SelectItem value="microsoft">{SMTP_PRESETS.microsoft.label}</SelectItem>
                  <SelectItem value="brevo">{SMTP_PRESETS.brevo.label}</SelectItem>
                  <SelectItem value="custom">Autre / personnalisé</SelectItem>
                </SelectContent>
              </Select>
              {presetHint ? (
                <p className="text-xs text-muted-foreground">{presetHint}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="smtp-user">Identifiant (souvent votre e-mail)</Label>
              <Input
                id="smtp-user"
                type="email"
                value={form.smtp_user}
                onChange={(e) => handleSmtpUserChange(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="smtp-password">Mot de passe SMTP</Label>
              <Input
                id="smtp-password"
                type="password"
                value={form.smtp_password}
                onChange={(e) => setForm({ ...form, smtp_password: e.target.value })}
                placeholder={
                  data?.has_smtp_password
                    ? 'Laisser vide pour ne pas modifier'
                    : 'Mot de passe ou clé SMTP'
                }
                autoComplete="new-password"
              />
            </div>
          </div>

          <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" className="w-full justify-between px-0 hover:bg-transparent">
                <span className="text-sm text-muted-foreground">
                  Paramètres techniques (optionnel)
                </span>
                <ChevronDown
                  className={cn(
                    'h-4 w-4 transition-transform',
                    advancedOpen && 'rotate-180',
                  )}
                />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 space-y-4 rounded-lg border border-dashed p-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="smtp-host">Serveur SMTP</Label>
                  <Input
                    id="smtp-host"
                    value={form.smtp_host}
                    onChange={(e) =>
                      setForm({ ...form, smtp_host: e.target.value, preset: 'custom' })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="smtp-port">Port</Label>
                  <Input
                    id="smtp-port"
                    type="number"
                    value={form.smtp_port}
                    onChange={(e) => setForm({ ...form, smtp_port: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="smtp-security">Sécurité</Label>
                  <Select
                    value={form.smtp_security}
                    onValueChange={(v) =>
                      setForm({ ...form, smtp_security: v as SmtpSecurity, preset: 'custom' })
                    }
                  >
                    <SelectTrigger id="smtp-security">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="starttls">STARTTLS (587)</SelectItem>
                      <SelectItem value="ssl">SSL (465)</SelectItem>
                      <SelectItem value="none">Aucune</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="reply-to">Réponse à (Reply-To)</Label>
                  <Input
                    id="reply-to"
                    type="email"
                    value={form.reply_to}
                    onChange={(e) => setForm({ ...form, reply_to: e.target.value })}
                    placeholder="Optionnel"
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="extra-support">Autres destinataires support</Label>
                  <textarea
                    id="extra-support"
                    className="flex min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    value={form.extra_support_emails}
                    onChange={(e) =>
                      setForm({ ...form, extra_support_emails: e.target.value })
                    }
                    placeholder="Une adresse par ligne (optionnel)"
                  />
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </CardContent>

        <CardFooter className="flex flex-col gap-4 border-t bg-muted/20 sm:flex-row sm:items-end sm:justify-between">
          <div className="w-full space-y-2 sm:max-w-xs">
            <Label htmlFor="test-email" className="text-xs text-muted-foreground">
              Vérifier avant d’enregistrer
            </Label>
            <div className="flex gap-2">
              <Input
                id="test-email"
                type="email"
                placeholder={form.smtp_user || 'votre@email.fr'}
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
              />
              <Button
                type="button"
                variant="secondary"
                onClick={handleTest}
                disabled={testMutation.isPending}
              >
                {testMutation.isPending ? '…' : 'Tester'}
              </Button>
            </div>
          </div>
          <Button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="w-full sm:w-auto"
          >
            {saveMutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
