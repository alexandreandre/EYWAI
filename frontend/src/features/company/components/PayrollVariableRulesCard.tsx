import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Coins } from 'lucide-react';
import {
  createPayrollVariableRule,
  generatePayrollVariables,
  listPayrollVariableRules,
  type PayrollVariableRule,
} from '@/api/payrollVariables';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';

const RULE_TYPE_LABELS: Record<string, string> = {
  fixed_monthly: 'Montant fixe mensuel',
  per_astreinte_week: 'Par semaine d\'astreinte',
  per_shift_type: 'Par type de poste',
  per_modulation_payout: 'Prime liquidation modulation',
  per_night_hour: 'Par heure de nuit',
};

export default function PayrollVariableRulesCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const now = new Date();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data: rules = [], isLoading } = useQuery({
    queryKey: queryKeys.payrollVariableRules(activeCompanyId),
    queryFn: listPayrollVariableRules,
    enabled: Boolean(activeCompanyId),
  });

  const [draft, setDraft] = useState<Partial<PayrollVariableRule>>({
    code: '',
    label: '',
    rule_type: 'fixed_monthly',
    amount: 0,
    enabled: true,
    generation_mode: 'auto',
    conditions: {},
    sort_order: 0,
  });

  const createRule = useMutation({
    mutationFn: () =>
      createPayrollVariableRule({
        code: draft.code || 'rule',
        label: draft.label || 'Nouvelle règle',
        enabled: true,
        rule_type: draft.rule_type || 'fixed_monthly',
        amount: draft.amount ?? 0,
        conditions: draft.conditions || {},
        generation_mode: draft.generation_mode || 'auto',
        sort_order: rules.length,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.payrollVariableRules(activeCompanyId),
      });
      toast({ title: 'Règle créée' });
      setDraft({
        code: '',
        label: '',
        rule_type: 'fixed_monthly',
        amount: 0,
        enabled: true,
        generation_mode: 'auto',
        conditions: {},
        sort_order: 0,
      });
    },
  });

  const generate = useMutation({
    mutationFn: (dryRun: boolean) =>
      generatePayrollVariables(now.getFullYear(), now.getMonth() + 1, dryRun),
    onSuccess: (result) => {
      toast({
        title: result.dry_run ? 'Simulation terminée' : 'Variables générées',
        description: `${result.preview.length} ligne(s) — ${result.written_count} écriture(s)`,
      });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Coins className="h-5 w-5" />
          Variables de paie récurrentes
        </CardTitle>
        <CardDescription>
          Productivité, astreintes, primes équipe — génération vers les saisies mensuelles.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Libellé</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Montant</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.code}</TableCell>
                  <TableCell>{r.label}</TableCell>
                  <TableCell>{RULE_TYPE_LABELS[r.rule_type] ?? r.rule_type}</TableCell>
                  <TableCell>{r.amount ?? '—'}</TableCell>
                </TableRow>
              ))}
              {rules.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-muted-foreground">
                    Aucune règle configurée.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}

        {canEdit && (
          <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Code</Label>
              <Input
                value={draft.code ?? ''}
                onChange={(e) => setDraft({ ...draft, code: e.target.value })}
                placeholder="productivite"
              />
            </div>
            <div className="space-y-2">
              <Label>Libellé</Label>
              <Input
                value={draft.label ?? ''}
                onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                placeholder="Prime productivité"
              />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Select
                value={draft.rule_type}
                onValueChange={(v) =>
                  setDraft({
                    ...draft,
                    rule_type: v as PayrollVariableRule['rule_type'],
                  })
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(RULE_TYPE_LABELS).map(([k, label]) => (
                    <SelectItem key={k} value={k}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Montant (€)</Label>
              <Input
                type="number"
                value={draft.amount ?? 0}
                onChange={(e) =>
                  setDraft({ ...draft, amount: Number(e.target.value) || 0 })
                }
              />
            </div>
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button
                variant="outline"
                disabled={createRule.isPending}
                onClick={() => createRule.mutate()}
              >
                Ajouter la règle
              </Button>
              <Button
                variant="secondary"
                disabled={generate.isPending}
                onClick={() => generate.mutate(true)}
              >
                Simuler le mois
              </Button>
              <Button
                disabled={generate.isPending}
                onClick={() => generate.mutate(false)}
              >
                Générer les saisies
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
