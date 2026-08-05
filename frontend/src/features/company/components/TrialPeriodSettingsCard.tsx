import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Timer, Trash2 } from 'lucide-react';
import {
  getCompanySettings,
  patchCompanySettings,
  type CompanySettingsResponse,
} from '@/api/company';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
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

type Unit = 'jours' | 'semaines' | 'mois';

interface BaremeLine {
  contract_type: string;
  statut: string;
  duree: number;
  unite: Unit;
  renouvellement: boolean;
}

const DEFAULT_ALERT_DAYS = 15;

/** Durées légales : elles s'appliquent tant qu'aucune ligne n'est saisie. */
const LEGAL_BAREME: BaremeLine[] = [
  { contract_type: 'CDI', statut: 'Non-Cadre', duree: 2, unite: 'mois', renouvellement: true },
  { contract_type: 'CDI', statut: 'Cadre', duree: 4, unite: 'mois', renouvellement: true },
];

interface TrialPeriodSection {
  alerte_jours?: number;
  regle_legale_cdd?: boolean;
  bareme?: BaremeLine[];
}

function readSection(settings: CompanySettingsResponse | undefined): TrialPeriodSection {
  const raw = settings?.settings?.periode_essai;
  return raw && typeof raw === 'object' ? (raw as TrialPeriodSection) : {};
}

export default function TrialPeriodSettingsCard() {
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.companySettings(activeCompanyId),
    queryFn: getCompanySettings,
    enabled: Boolean(activeCompanyId),
  });

  const saved = useMemo(() => readSection(data), [data]);

  const [alertDays, setAlertDays] = useState<number>(DEFAULT_ALERT_DAYS);
  const [cddLegalRule, setCddLegalRule] = useState<boolean>(true);
  const [lines, setLines] = useState<BaremeLine[]>([]);

  useEffect(() => {
    setAlertDays(saved.alerte_jours ?? DEFAULT_ALERT_DAYS);
    setCddLegalRule(saved.regle_legale_cdd ?? true);
    setLines(saved.bareme ?? []);
  }, [saved]);

  const mutation = useMutation({
    mutationFn: () =>
      patchCompanySettings({
        periode_essai: {
          alerte_jours: alertDays,
          regle_legale_cdd: cddLegalRule,
          bareme: lines,
        },
      }),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.companySettings(activeCompanyId), result);
      toast({ title: "Paramétrage de période d'essai enregistré" });
    },
    onError: (error: unknown) =>
      toast({
        title: 'Erreur',
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Impossible d'enregistrer le paramétrage.",
        variant: 'destructive',
      }),
  });

  const updateLine = (index: number, patch: Partial<BaremeLine>) =>
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));

  const addLine = () =>
    setLines((prev) => [
      ...prev,
      { contract_type: 'CDI', statut: 'Non-Cadre', duree: 2, unite: 'mois', renouvellement: true },
    ]);

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Timer className="h-5 w-5" />
          Périodes d&apos;essai
        </CardTitle>
        <CardDescription>
          Durées proposées à la création d&apos;un salarié et délai d&apos;alerte avant le terme.
          Le barème propose : la durée reste modifiable salarié par salarié.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="trial-alert-days">Alerter combien de jours avant le terme</Label>
            <Input
              id="trial-alert-days"
              type="number"
              min={1}
              value={alertDays}
              onChange={(e) => setAlertDays(Number(e.target.value) || DEFAULT_ALERT_DAYS)}
            />
          </div>
          <div className="flex items-start gap-2 rounded-md border p-3">
            <Checkbox
              id="trial-cdd-rule"
              checked={cddLegalRule}
              onCheckedChange={(checked) => setCddLegalRule(checked === true)}
            />
            <Label htmlFor="trial-cdd-rule" className="text-sm font-normal">
              Appliquer la règle légale des CDD
              <span className="block text-xs text-muted-foreground">
                Un jour par semaine de contrat, plafonné à deux semaines si le contrat fait six
                mois ou moins, un mois au-delà.
              </span>
            </Label>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Barème par type de contrat</Label>
            <Button type="button" variant="outline" size="sm" onClick={addLine}>
              Ajouter une ligne
            </Button>
          </div>
          {lines.length === 0 ? (
            <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              Aucune ligne saisie : les durées légales s&apos;appliquent —{' '}
              {LEGAL_BAREME.map((l) => `${l.statut} ${l.duree} mois`).join(', ')}. Ajoutez une
              ligne pour surcharger votre convention.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Contrat</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Durée</TableHead>
                  <TableHead>Unité</TableHead>
                  <TableHead>Renouvelable</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {lines.map((line, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Input
                        value={line.contract_type}
                        onChange={(e) => updateLine(index, { contract_type: e.target.value })}
                        aria-label="Type de contrat"
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        value={line.statut}
                        onValueChange={(value) => updateLine(index, { statut: value })}
                      >
                        <SelectTrigger aria-label="Statut">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Non-Cadre">Non-Cadre</SelectItem>
                          <SelectItem value="Cadre">Cadre</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={1}
                        value={line.duree}
                        onChange={(e) => updateLine(index, { duree: Number(e.target.value) || 1 })}
                        aria-label="Durée"
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        value={line.unite}
                        onValueChange={(value) => updateLine(index, { unite: value as Unit })}
                      >
                        <SelectTrigger aria-label="Unité">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="jours">Jours</SelectItem>
                          <SelectItem value="semaines">Semaines</SelectItem>
                          <SelectItem value="mois">Mois</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Checkbox
                        checked={line.renouvellement}
                        onCheckedChange={(checked) =>
                          updateLine(index, { renouvellement: checked === true })
                        }
                        aria-label="Renouvellement possible"
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => setLines((prev) => prev.filter((_, i) => i !== index))}
                        aria-label="Supprimer la ligne"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>

        <Button
          type="button"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          Enregistrer
        </Button>
      </CardContent>
    </Card>
  );
}
