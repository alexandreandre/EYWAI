import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BOETH_CODE_OPTIONS,
  deleteEmployeeBoeth,
  saveEmployeeBoeth,
  type EmployeeBoethProfile,
} from '@/api/oethSettings';
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import { Accessibility, AlertTriangle, Pencil, Trash2 } from 'lucide-react';

interface EmployeeBoethCardProps {
  employeeId: string;
  profile: EmployeeBoethProfile | null | undefined;
  canEdit?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}

function formatDateFR(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso.slice(0, 10)).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const target = new Date(iso.slice(0, 10));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

export function EmployeeBoethCard({
  employeeId,
  profile,
  canEdit = true,
  sheetOpen: controlledOpen,
  onSheetOpenChange,
}: EmployeeBoethCardProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [internalOpen, setInternalOpen] = useState(false);
  const sheetOpen = controlledOpen ?? internalOpen;
  const setSheetOpen = onSheetOpenChange ?? setInternalOpen;

  const [form, setForm] = useState<Partial<EmployeeBoethProfile>>({});

  useEffect(() => {
    if (sheetOpen) {
      if (profile) {
        setForm(profile);
      } else {
        setForm({
          boeth_code: '01',
          valid_from: new Date().toISOString().slice(0, 10),
        });
      }
    }
  }, [sheetOpen, profile]);

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
      setSheetOpen(false);
    },
    onError: () => {
      toast({
        title: 'Erreur',
        description: 'Impossible d’enregistrer le statut BOETH.',
        variant: 'destructive',
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEmployeeBoeth(employeeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employee-boeth', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['oeth-compliance'] });
      toast({ title: 'Statut BOETH retiré' });
      setSheetOpen(false);
    },
  });

  const selectedLabel = useMemo(
    () => BOETH_CODE_OPTIONS.find((o) => o.value === form.boeth_code)?.label,
    [form.boeth_code],
  );

  const docDays = daysUntil(profile?.document_expires_at);
  const validDays = daysUntil(profile?.valid_to);
  const showDocAlert = docDays != null && docDays <= 60;
  const showValidAlert = validDays != null && validDays <= 60;

  if (!profile && !canEdit) {
    return null;
  }

  return (
    <>
      {profile ? (
        <div
          className={cn(
            'flex flex-col gap-2 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between',
            (showDocAlert || showValidAlert) && 'border-amber-300 bg-amber-50/50',
          )}
        >
          <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <span className="font-medium">
              {profile.boeth_label ?? profile.boeth_code}
            </span>
            <span className="text-muted-foreground">
              Valide du {formatDateFR(profile.valid_from)}
              {profile.valid_to ? ` au ${formatDateFR(profile.valid_to)}` : ' (en cours)'}
            </span>
            {profile.document_expires_at ? (
              <span
                className={cn(
                  'text-muted-foreground',
                  showDocAlert && 'font-medium text-amber-900',
                )}
              >
                Justificatif jusqu&apos;au {formatDateFR(profile.document_expires_at)}
              </span>
            ) : null}
            {(showDocAlert || showValidAlert) && (
              <span className="inline-flex items-center gap-1 text-xs text-amber-900">
                <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                Échéance proche
              </span>
            )}
          </div>
          {canEdit ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={() => setSheetOpen(true)}
            >
              <Pencil className="mr-2 h-4 w-4" />
              Modifier
            </Button>
          ) : null}
        </div>
      ) : null}

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Accessibility className="h-5 w-5 text-primary" />
              Statut BOETH
            </SheetTitle>
            <SheetDescription>
              Déclaration mensuelle DSN (S21.G00.40.072). Un seul code par salarié.
            </SheetDescription>
          </SheetHeader>

          {canEdit ? (
            <div className="mt-6 space-y-4">
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
                {selectedLabel ? (
                  <p className="text-xs text-muted-foreground">{selectedLabel}</p>
                ) : null}
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
                    onChange={(e) =>
                      setForm((f) => ({ ...f, valid_to: e.target.value || null }))
                    }
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
            </div>
          ) : profile ? (
            <div className="mt-6 space-y-1 text-sm">
              <p className="font-medium">{profile.boeth_label ?? selectedLabel}</p>
              <p className="text-muted-foreground">
                Valide du {formatDateFR(profile.valid_from)}
                {profile.valid_to ? ` au ${formatDateFR(profile.valid_to)}` : ' (en cours)'}
              </p>
            </div>
          ) : (
            <p className="mt-6 text-sm text-muted-foreground">Aucun statut BOETH déclaré.</p>
          )}

          {canEdit ? (
            <SheetFooter className="mt-6 flex-col gap-2 sm:flex-row sm:justify-start">
              <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
                {profile ? 'Mettre à jour' : 'Enregistrer le statut BOETH'}
              </Button>
              {profile ? (
                <Button
                  variant="outline"
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Retirer le statut
                </Button>
              ) : null}
            </SheetFooter>
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}
