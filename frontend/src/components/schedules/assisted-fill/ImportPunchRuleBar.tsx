import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clock } from 'lucide-react';
import {
  getPunchAccountingSettings,
  listPunchShiftSlots,
  updatePunchAccountingSettings,
  type PunchAccountingSettings,
} from '@/api/punchAccounting';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { queryKeys } from '@/lib/queryKeys';
import type { PunchBreakRule } from '@/lib/punchBreakHours';

function toRule(settings: PunchAccountingSettings): PunchBreakRule {
  return {
    enabled: settings.enabled,
    breakMinutes: settings.default_break_deduct_minutes,
    thresholdMinutes: settings.break_threshold_minutes,
  };
}

interface ImportPunchRuleBarProps {
  onApply: (prev: PunchBreakRule, next: PunchBreakRule) => void;
}

export function ImportPunchRuleBar({ onApply }: ImportPunchRuleBarProps) {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const canEdit =
    user?.role === 'admin' || user?.role === 'rh' || user?.role === 'collaborateur_rh';

  const { data: settings } = useQuery({
    queryKey: queryKeys.punchAccountingSettings(companyId),
    queryFn: getPunchAccountingSettings,
    enabled: Boolean(companyId),
  });

  const { data: slots = [] } = useQuery({
    queryKey: queryKeys.punchShiftSlots(companyId),
    queryFn: listPunchShiftSlots,
    enabled: Boolean(companyId),
  });

  const [form, setForm] = useState<PunchAccountingSettings | null>(null);

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  const saveMut = useMutation({
    mutationFn: updatePunchAccountingSettings,
    onSuccess: (saved) => {
      const prev = settings ? toRule(settings) : toRule(saved);
      queryClient.setQueryData(queryKeys.punchAccountingSettings(companyId), saved);
      setForm(saved);
      onApply(prev, toRule(saved));
    },
    onError: () => {
      toast({
        title: 'Règle pointage',
        description: 'Enregistrement impossible.',
        variant: 'destructive',
      });
    },
  });

  if (!form) return null;

  const commit = (patch: Partial<PunchAccountingSettings>) => {
    if (!canEdit) return;
    const next = { ...form, ...patch };
    setForm(next);
    saveMut.mutate(patch);
  };

  return (
    <div className="shrink-0 rounded-md border bg-muted/10 px-2 py-1.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
        <Clock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <Switch
          id="import-punch-enabled"
          className="scale-90"
          checked={form.enabled}
          disabled={!canEdit || saveMut.isPending}
          onCheckedChange={(enabled) => commit({ enabled })}
        />
        <label htmlFor="import-punch-enabled" className="font-medium">
          Pause pointage
        </label>
        <Input
          type="number"
          min={0}
          max={180}
          className="h-7 w-14 px-1 text-xs"
          value={form.default_break_deduct_minutes}
          disabled={!canEdit || !form.enabled}
          onChange={(e) =>
            setForm({
              ...form,
              default_break_deduct_minutes: Number(e.target.value) || 0,
            })
          }
          onBlur={() => {
            if (
              settings &&
              form.default_break_deduct_minutes !== settings.default_break_deduct_minutes
            ) {
              commit({ default_break_deduct_minutes: form.default_break_deduct_minutes });
            }
          }}
        />
        <span className="text-muted-foreground">min déduites</span>
        <span className="text-muted-foreground">si présence &gt;</span>
        <Input
          type="number"
          min={0}
          max={960}
          className="h-7 w-14 px-1 text-xs"
          value={form.break_threshold_minutes}
          disabled={!canEdit || !form.enabled}
          onChange={(e) =>
            setForm({
              ...form,
              break_threshold_minutes: Number(e.target.value) || 0,
            })
          }
          onBlur={() => {
            if (
              settings &&
              form.break_threshold_minutes !== settings.break_threshold_minutes
            ) {
              commit({ break_threshold_minutes: form.break_threshold_minutes });
            }
          }}
        />
        <span className="text-muted-foreground">min</span>
      </div>
      {slots.length > 0 && (
        <p className="mt-1 text-[10px] text-muted-foreground">
          Créneaux :{' '}
          {slots
            .map(
              (s) =>
                `${s.label || s.code || 'créneau'} −${s.break_deduct_minutes} min`,
            )
            .join(' · ')}
        </p>
      )}
    </div>
  );
}
