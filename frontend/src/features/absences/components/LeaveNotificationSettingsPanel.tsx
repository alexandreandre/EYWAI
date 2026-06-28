import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, Mail } from 'lucide-react';
import {
  getLeaveNotificationSettings,
  updateLeaveNotificationSettings,
  type LeaveNotificationRole,
  type LeaveNotificationSettings,
} from '@/api/leaveSettings';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';

const ROLE_LABELS: Record<LeaveNotificationRole, string> = {
  admin: 'Admin',
  rh: 'RH',
  collaborateur_rh: 'Collaborateur RH',
};

const ROLES: LeaveNotificationRole[] = ['admin', 'rh', 'collaborateur_rh'];

type FormState = {
  enabled: boolean;
  notify_on_employee_request: boolean;
  notify_after_manager_approval: boolean;
  recipient_roles: LeaveNotificationRole[];
  extra_recipient_emails: string;
};

function toForm(settings: LeaveNotificationSettings): FormState {
  return {
    enabled: settings.enabled,
    notify_on_employee_request: settings.notify_on_employee_request,
    notify_after_manager_approval: settings.notify_after_manager_approval,
    recipient_roles: settings.recipient_roles,
    extra_recipient_emails: settings.extra_recipient_emails.join('\n'),
  };
}

function parseEmails(value: string): string[] {
  return value
    .split(/[\n,;]+/)
    .map((email) => email.trim().toLowerCase())
    .filter(Boolean);
}

export function LeaveNotificationSettingsPanel() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);

  const canView = useMemo(() => {
    const role = user?.role;
    return role === 'admin' || role === 'rh' || role === 'collaborateur_rh';
  }, [user?.role]);

  const canEdit = useMemo(() => {
    const role = user?.role;
    return role === 'admin' || role === 'rh';
  }, [user?.role]);

  const query = useQuery({
    queryKey: ['leave-notification-settings', companyId],
    queryFn: getLeaveNotificationSettings,
    enabled: Boolean(companyId && canView),
  });

  useEffect(() => {
    if (query.data) setForm(toForm(query.data));
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!form) throw new Error('Formulaire incomplet');
      return updateLeaveNotificationSettings({
        enabled: form.enabled,
        notify_on_employee_request: form.notify_on_employee_request,
        notify_after_manager_approval: form.notify_after_manager_approval,
        recipient_roles: form.recipient_roles,
        extra_recipient_emails: parseEmails(form.extra_recipient_emails),
      });
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(['leave-notification-settings', companyId], updated);
      setForm(toForm(updated));
      toast({ title: 'Notifications enregistrées' });
    },
    onError: (err: Error) => {
      toast({
        title: 'Enregistrement impossible',
        description: err.message || 'Vérifiez les paramètres.',
        variant: 'destructive',
      });
    },
  });

  if (!canView) return null;

  if (query.isLoading || !form) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-56" />
          <Skeleton className="h-4 w-80" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  const toggleRole = (role: LeaveNotificationRole, checked: boolean) => {
    setForm((current) => {
      if (!current) return current;
      const next = checked
        ? Array.from(new Set([...current.recipient_roles, role]))
        : current.recipient_roles.filter((r) => r !== role);
      return { ...current, recipient_roles: next };
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Mail className="h-5 w-5 text-muted-foreground" />
          Notifications email des demandes
        </CardTitle>
        <CardDescription>
          Destinataires avertis lorsqu’un salarié dépose une demande d’absence.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center justify-between gap-4 rounded-lg border p-3">
          <div className="space-y-1">
            <Label htmlFor="leave-email-enabled" className="font-medium">
              Envoyer des emails
            </Label>
            <p className="text-xs text-muted-foreground">
              L’envoi reste non bloquant si SMTP est indisponible.
            </p>
          </div>
          <Switch
            id="leave-email-enabled"
            checked={form.enabled}
            disabled={!canEdit}
            onCheckedChange={(enabled) => setForm({ ...form, enabled })}
          />
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex items-start gap-3 rounded-lg border p-3 text-sm">
            <Checkbox
              checked={form.notify_on_employee_request}
              disabled={!canEdit}
              onCheckedChange={(value) =>
                setForm({ ...form, notify_on_employee_request: value === true })
              }
            />
            <span>
              <span className="block font-medium">Dès la demande salarié</span>
              <span className="text-xs text-muted-foreground">
                Inclut les demandes encore en attente manager.
              </span>
            </span>
          </label>
          <label className="flex items-start gap-3 rounded-lg border p-3 text-sm">
            <Checkbox
              checked={form.notify_after_manager_approval}
              disabled={!canEdit}
              onCheckedChange={(value) =>
                setForm({ ...form, notify_after_manager_approval: value === true })
              }
            />
            <span>
              <span className="block font-medium">Après validation manager</span>
              <span className="text-xs text-muted-foreground">
                Alerte la RH quand la demande arrive à son niveau.
              </span>
            </span>
          </label>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">Rôles destinataires</p>
          <div className="flex flex-wrap gap-3">
            {ROLES.map((role) => (
              <label key={role} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                <Checkbox
                  checked={form.recipient_roles.includes(role)}
                  disabled={!canEdit}
                  onCheckedChange={(value) => toggleRole(role, value === true)}
                />
                {ROLE_LABELS[role]}
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="leave-extra-emails">Emails additionnels</Label>
          <Textarea
            id="leave-extra-emails"
            value={form.extra_recipient_emails}
            disabled={!canEdit}
            onChange={(event) =>
              setForm({ ...form, extra_recipient_emails: event.target.value })
            }
            placeholder="paie@example.fr"
            rows={3}
          />
        </div>

        {canEdit ? (
          <Button
            type="button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            <Bell className="mr-2 h-4 w-4" />
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
