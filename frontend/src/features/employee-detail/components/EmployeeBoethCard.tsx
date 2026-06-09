import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BOETH_CODE_OPTIONS,
  deleteEmployeeBoeth,
  getEmployeeBoeth,
  saveEmployeeBoeth,
  type EmployeeBoethProfile,
} from '@/api/oethSettings';
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
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { Accessibility, Trash2 } from 'lucide-react';

interface EmployeeBoethCardProps {
  employeeId: string;
  canEdit?: boolean;
}

export function EmployeeBoethCard({ employeeId, canEdit = true }: EmployeeBoethCardProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['employee-boeth', employeeId],
    queryFn: () => getEmployeeBoeth(employeeId),
    enabled: Boolean(employeeId),
  });

  const [form, setForm] = useState<Partial<EmployeeBoethProfile>>({});

  useEffect(() => {
    if (data) {
      setForm(data);
    } else if (!isLoading) {
      setForm({
        boeth_code: '01',
        valid_from: new Date().toISOString().slice(0, 10),
      });
    }
  }, [data, isLoading]);

  const saveMutation = useMutation({
    mutationFn: () =>
      saveEmployeeBoeth(employeeId, {
        boeth_code: form.boeth_code ?? '01',
        valid_from: form.valid_from ?? new Date().toISOString().slice(0, 10),
        valid_to: form.valid_to || null,
        document_type: form.document_type || null,
        document_expires_at: form.document_expires_at || null,
        notes: form.notes || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employee-boeth', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['oeth-compliance'] });
      toast({ title: 'Statut BOETH enregistré' });
    },
    onError: () => {
      toast({ title: 'Erreur', description: 'Impossible d’enregistrer le statut BOETH.', variant: 'destructive' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEmployeeBoeth(employeeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employee-boeth', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['oeth-compliance'] });
      toast({ title: 'Statut BOETH retiré' });
    },
  });

  const selectedLabel = useMemo(
    () => BOETH_CODE_OPTIONS.find((o) => o.value === form.boeth_code)?.label,
    [form.boeth_code],
  );

  if (isLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Accessibility className="mr-2 h-5 w-5 text-primary" />
          Statut BOETH / Travailleur handicapé
        </CardTitle>
        <CardDescription>
          Déclaration mensuelle DSN (S21.G00.40.072). Un seul code par salarié.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {data && !canEdit ? (
          <div className="space-y-1 text-sm">
            <p className="font-medium">{data.boeth_label ?? selectedLabel}</p>
            <p className="text-muted-foreground">
              Valide du {data.valid_from}
              {data.valid_to ? ` au ${data.valid_to}` : ' (en cours)'}
            </p>
          </div>
        ) : canEdit ? (
          <>
            <div className="space-y-2">
              <Label>Code BOETH</Label>
              <Select
                value={form.boeth_code ?? '01'}
                onValueChange={(v) => setForm((f) => ({ ...f, boeth_code: v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choisir un statut" />
                </SelectTrigger>
                <SelectContent>
                  {BOETH_CODE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Valide depuis</Label>
                <Input
                  type="date"
                  value={form.valid_from ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Valide jusqu&apos;au (optionnel)</Label>
                <Input
                  type="date"
                  value={form.valid_to ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, valid_to: e.target.value || null }))}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Type de justificatif</Label>
                <Input
                  value={form.document_type ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, document_type: e.target.value }))}
                  placeholder="RQTH, CMI…"
                />
              </div>
              <div className="space-y-2">
                <Label>Expiration justificatif</Label>
                <Input
                  type="date"
                  value={form.document_expires_at ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, document_expires_at: e.target.value || null }))
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Notes internes</Label>
              <Textarea
                value={form.notes ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                rows={2}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
                {data ? 'Mettre à jour' : 'Enregistrer le statut BOETH'}
              </Button>
              {data ? (
                <Button
                  variant="outline"
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Retirer le statut
                </Button>
              ) : null}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Aucun statut BOETH déclaré.</p>
        )}
      </CardContent>
    </Card>
  );
}
