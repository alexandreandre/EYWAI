import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AlertTriangle, Users } from 'lucide-react';
import {
  getCseSettings,
  saveCseSettings,
  type CompanyCseSettings,
  type CompanyCseSettingsUpdate,
  type CseStatus,
} from '@/api/cse';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import { useToast } from '@/hooks/use-toast';

const STATUS_LABELS: Record<CseStatus, string> = {
  unknown: 'Non renseigné',
  not_required: 'Non requis (effectif < 11)',
  obligation_pending: 'Obligation CSE — à traiter',
  carence: 'Carence électorale (PV valide)',
  elected: 'CSE élu en place',
};

export default function CseStatusCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cse-settings', activeCompanyId],
    queryFn: getCseSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<CompanyCseSettings | null>(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (payload: CompanyCseSettingsUpdate) => saveCseSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(['cse-settings', activeCompanyId], saved);
      queryClient.invalidateQueries({ queryKey: ['company-overview'] });
      setForm(saved);
      toast({ title: 'Enregistré', description: 'Statut CSE mis à jour.' });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Impossible d’enregistrer le statut CSE.',
        variant: 'destructive',
      });
    },
  });

  const carenceExpired =
    form?.cse_status === 'carence' &&
    form.carence_valid_until != null &&
    form.carence_valid_until < new Date().toISOString().slice(0, 10);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !form) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Users className="h-4 w-4" />
            Statut CSE
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Impossible de charger le statut CSE.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card id="cse-status">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="h-4 w-4" />
          Statut CSE
        </CardTitle>
        <CardDescription>
          Carence électorale (Cerfa 15248), élus ou obligation légale — impacte le bandeau conformité.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {carenceExpired ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              La carence CSE a expiré le{' '}
              {new Date(form.carence_valid_until!).toLocaleDateString('fr-FR')}. Renouvelez le PV de
              carence ou organisez des élections.
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-2 max-w-md">
          <Label htmlFor="cse_status">Statut</Label>
          <Select
            value={form.cse_status}
            onValueChange={(v) =>
              setForm((p) => (p ? { ...p, cse_status: v as CseStatus } : p))
            }
            disabled={!canEdit}
          >
            <SelectTrigger id="cse_status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(STATUS_LABELS) as CseStatus[]).map((key) => (
                <SelectItem key={key} value={key}>
                  {STATUS_LABELS[key]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {form.cse_status === 'carence' ? (
          <div className="grid gap-2 max-w-xs">
            <Label htmlFor="carence_valid_until">Carence valide jusqu’au</Label>
            <Input
              id="carence_valid_until"
              type="date"
              value={form.carence_valid_until ?? ''}
              onChange={(e) =>
                setForm((p) =>
                  p ? { ...p, carence_valid_until: e.target.value || null } : p,
                )
              }
              disabled={!canEdit}
            />
            <p className="text-xs text-muted-foreground">
              Durée habituelle : 4 ans à compter du PV de carence.
            </p>
          </div>
        ) : null}

        <div className="grid gap-2">
          <Label htmlFor="cse_notes">Notes</Label>
          <Input
            id="cse_notes"
            value={form.notes ?? ''}
            onChange={(e) => setForm((p) => (p ? { ...p, notes: e.target.value || null } : p))}
            disabled={!canEdit}
            placeholder="Ex. : PV Cerfa 15248*03 du 06/09/2019"
          />
        </div>

        <div className="flex flex-wrap gap-2">
          {canEdit ? (
            <Button
              onClick={() =>
                mutation.mutate({
                  cse_status: form.cse_status,
                  carence_valid_until: form.carence_valid_until,
                  carence_pv_document_id: form.carence_pv_document_id,
                  notes: form.notes,
                })
              }
              disabled={mutation.isPending}
            >
              Enregistrer
            </Button>
          ) : null}
          <Button variant="outline" asChild>
            <Link to="/cse?tab=bdes">Archiver un PV (BDES)</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/cse?tab=elections">Calendrier électoral</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
