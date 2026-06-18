import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createCetDeposit,
  createCetDepositCp,
  createCetWithdrawal,
  getEmployeeCetSummary,
  getMyCetSummary,
  validateCetMovement,
} from '@/api/cet';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { useAuth } from '@/contexts/AuthContext';

function formatHours(h: number): string {
  const hrs = Math.floor(h);
  const mins = Math.round((h - hrs) * 60);
  return mins > 0 ? `${hrs}h${String(mins).padStart(2, '0')}` : `${hrs}h`;
}

function cpUnitLabel(unit: 'ouvres' | 'ouvrables'): string {
  return unit === 'ouvres' ? 'ouvrés' : 'ouvrables';
}

function movementLabel(m: {
  movement_type: string;
  hours: number;
  days: number;
}): string {
  if (m.movement_type === 'deposit_hs') {
    return `Épargne HS — ${m.hours} h`;
  }
  if (m.movement_type === 'deposit_cp') {
    return `Transfert CP — ${m.days} j`;
  }
  return `Retrait — ${m.hours} h`;
}

type Props = {
  variant?: 'inline' | 'card';
  year?: number;
  month?: number;
};

export function EmployeeCetPanel({ variant = 'inline', year, month }: Props) {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [depositOpen, setDepositOpen] = useState(false);
  const [depositCpOpen, setDepositCpOpen] = useState(false);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [hoursInput, setHoursInput] = useState('');
  const [daysInput, setDaysInput] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.employeeCetSummary(user?.id, year, month),
    queryFn: () => getMyCetSummary({ year, month }),
    enabled: Boolean(user?.id),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: ['employee', user?.id ?? 'none', 'cet'],
    });
  };

  const depositMutation = useMutation({
    mutationFn: () =>
      createCetDeposit({
        hours: Number(hoursInput),
        year,
        month,
      }),
    onSuccess: () => {
      toast({ title: 'Demande envoyée', description: 'Épargne CET enregistrée.' });
      setDepositOpen(false);
      setHoursInput('');
      invalidate();
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Impossible d’enregistrer.',
        variant: 'destructive',
      });
    },
  });

  const depositCpMutation = useMutation({
    mutationFn: () =>
      createCetDepositCp({
        days: Number(daysInput),
        year,
        month,
      }),
    onSuccess: () => {
      toast({
        title: 'Demande envoyée',
        description:
          data?.settings.validation_mode === 'rh'
            ? 'Transfert CP en attente de validation RH.'
            : 'Transfert CP enregistré.',
      });
      setDepositCpOpen(false);
      setDaysInput('');
      invalidate();
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Impossible d’enregistrer.',
        variant: 'destructive',
      });
    },
  });

  const withdrawMutation = useMutation({
    mutationFn: () => createCetWithdrawal({ hours: Number(hoursInput) }),
    onSuccess: () => {
      toast({ title: 'Demande envoyée', description: 'Retrait CET enregistré.' });
      setWithdrawOpen(false);
      setHoursInput('');
      invalidate();
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Impossible d’enregistrer.',
        variant: 'destructive',
      });
    },
  });

  if (isLoading || !data?.cet_enabled || !data.eligible) {
    return null;
  }

  const cpRemaining = data.cp_transfer_remaining_days;
  const cpCanTransfer =
    data.allow_deposit_cp &&
    data.cp_balance_available > 0 &&
    (cpRemaining == null || cpRemaining > 0);

  const showPanel =
    data.balance_hours > 0 ||
    data.spareable_hours > 0 ||
    cpCanTransfer ||
    (data.pending_movements?.length ?? 0) > 0;

  if (!showPanel && variant === 'inline') {
    return null;
  }

  return (
    <>
      <div
        className={
          variant === 'card'
            ? 'rounded-lg border bg-muted/30 px-4 py-3 text-sm space-y-2'
            : 'text-sm text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1'
        }
      >
        <span>
          CET :{' '}
          <span className="font-medium text-foreground">
            {formatHours(data.balance_hours)}
          </span>
        </span>
        {data.allow_deposit_hs && data.spareable_hours > 0 ? (
          <span>
            HS épargables :{' '}
            <span className="font-medium text-foreground">
              {formatHours(data.spareable_hours)}
            </span>
          </span>
        ) : null}
        {data.allow_deposit_cp ? (
          <span>
            CP transférables :{' '}
            <span className="font-medium text-foreground">
              {data.cp_balance_available.toFixed(1)} j {cpUnitLabel(data.cp_unit)}
            </span>
            {cpRemaining != null ? (
              <span className="text-muted-foreground">
                {' '}
                ({data.cp_transfer_used_days.toFixed(1)} / {cpRemaining + data.cp_transfer_used_days} j
                cette année)
              </span>
            ) : null}
          </span>
        ) : null}
        <div className="flex gap-2 flex-wrap">
          {data.allow_deposit_hs && data.spareable_hours > 0 ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => {
                setHoursInput(String(Math.min(data.spareable_hours, 1)));
                setDepositOpen(true);
              }}
            >
              Mettre en CET
            </Button>
          ) : null}
          {cpCanTransfer ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => {
                const maxDays = Math.min(
                  data.cp_balance_available,
                  cpRemaining ?? data.cp_balance_available,
                );
                setDaysInput(String(Math.min(maxDays, 1)));
                setDepositCpOpen(true);
              }}
            >
              Transférer vers CET
            </Button>
          ) : null}
          {data.balance_hours > 0 ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 text-xs"
              onClick={() => {
                setHoursInput(String(data.balance_hours));
                setWithdrawOpen(true);
              }}
            >
              Poser un congé CET
            </Button>
          ) : null}
        </div>
      </div>

      <Dialog open={depositOpen} onOpenChange={setDepositOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Épargner des heures sup</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="cet-deposit-hours">
              Heures (max {formatHours(data.spareable_hours)})
            </Label>
            <Input
              id="cet-deposit-hours"
              type="number"
              min={0.25}
              step={0.25}
              max={data.spareable_hours}
              value={hoursInput}
              onChange={(e) => setHoursInput(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button
              onClick={() => depositMutation.mutate()}
              disabled={depositMutation.isPending}
            >
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={depositCpOpen} onOpenChange={setDepositCpOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Transférer des congés payés vers le CET</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="cet-deposit-cp-days">
              Jours {cpUnitLabel(data.cp_unit)} (max{' '}
              {Math.min(
                data.cp_balance_available,
                cpRemaining ?? data.cp_balance_available,
              ).toFixed(1)}
              )
            </Label>
            <Input
              id="cet-deposit-cp-days"
              type="number"
              min={0.5}
              step={0.5}
              max={Math.min(
                data.cp_balance_available,
                cpRemaining ?? data.cp_balance_available,
              )}
              value={daysInput}
              onChange={(e) => setDaysInput(e.target.value)}
            />
            {data.settings.validation_mode === 'rh' ? (
              <p className="text-xs text-muted-foreground">
                La demande sera soumise à validation RH avant crédit du solde CET.
              </p>
            ) : null}
          </div>
          <DialogFooter>
            <Button
              onClick={() => depositCpMutation.mutate()}
              disabled={depositCpMutation.isPending}
            >
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={withdrawOpen} onOpenChange={setWithdrawOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Poser un congé depuis le CET</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="cet-withdraw-hours">
              Heures (solde {formatHours(data.balance_hours)})
            </Label>
            <Input
              id="cet-withdraw-hours"
              type="number"
              min={0.25}
              step={0.25}
              max={data.balance_hours}
              value={hoursInput}
              onChange={(e) => setHoursInput(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button
              onClick={() => withdrawMutation.mutate()}
              disabled={withdrawMutation.isPending}
            >
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function RhCetPendingPanel({
  employeeId,
  companyId,
  year,
  month,
}: {
  employeeId: string;
  companyId: string;
  year?: number;
  month?: number;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: queryKeys.employeeCetRhSummary(companyId, employeeId, year, month),
    queryFn: () => getEmployeeCetSummary(employeeId, { companyId, year, month }),
    enabled: Boolean(employeeId && companyId),
  });

  const validateMutation = useMutation({
    mutationFn: ({
      movementId,
      approved,
    }: {
      movementId: string;
      approved: boolean;
    }) => validateCetMovement(movementId, approved, companyId),
    onSuccess: () => {
      toast({ title: 'Mise à jour', description: 'Demande CET traitée.' });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.employeeCetRhSummary(companyId, employeeId, year, month),
      });
    },
  });

  if (!data?.cet_enabled || !data.pending_movements?.length) {
    return null;
  }

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-3 space-y-2 text-sm">
      <p className="font-medium text-amber-900">Demandes CET en attente</p>
      <ul className="space-y-2">
        {data.pending_movements.map((m) => (
          <li key={m.id} className="flex flex-wrap items-center justify-between gap-2">
            <span>{movementLabel(m)}</span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  validateMutation.mutate({ movementId: m.id, approved: true })
                }
              >
                Valider
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  validateMutation.mutate({ movementId: m.id, approved: false })
                }
              >
                Refuser
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
