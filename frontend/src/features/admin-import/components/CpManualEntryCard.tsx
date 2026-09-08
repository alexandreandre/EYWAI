import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Loader2, PencilLine, Save } from 'lucide-react';
import {
  commitCpImport,
  fetchCpRoster,
  type CpImportCommitRow,
} from '@/api/adminImport';
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
import { getUserErrorMessage } from '@/lib/errorMessages';

/** Libellés avec accents : la note « Import CP bulletin <Mois Année> » ancre
 * le mode « fidèle au bulletin » côté moteur — le mois doit y être lisible. */
const MOIS_FR = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];

interface CpManualEntryCardProps {
  companyId: string;
  companyName?: string;
  onComplete?: () => void;
}

/** Saisie manuelle des compteurs CP (sans bulletin PDF).
 *
 * Même mécanisme que l'import de bulletins : les valeurs saisies passent par
 * le commit d'import (reprise « fidèle au bulletin », référence = fin du mois
 * choisi). À utiliser quand l'état du service paie arrive en tableur. */
export function CpManualEntryCard({
  companyId,
  companyName,
  onComplete,
}: CpManualEntryCardProps) {
  const { toast } = useToast();
  const now = new Date();
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() === 0 ? 12 : now.getMonth());
  const [values, setValues] = useState<Record<string, { n1: string; n: string }>>({});

  const rosterQuery = useQuery({
    queryKey: ['cp-roster', companyId],
    queryFn: () => fetchCpRoster(companyId),
    enabled: open && Boolean(companyId),
  });

  const rows = useMemo(() => rosterQuery.data?.employees ?? [], [rosterQuery.data]);

  const filled = useMemo(
    () =>
      rows.filter((e) => {
        const v = values[e.id];
        return v && (v.n1.trim() !== '' || v.n.trim() !== '');
      }),
    [rows, values],
  );

  const parseSolde = (raw: string): number => {
    const n = Number(raw.replace(',', '.'));
    return Number.isFinite(n) ? n : 0;
  };

  const commitMutation = useMutation({
    mutationFn: async () => {
      const periodLabel = `${MOIS_FR[month - 1]} ${year}`;
      const payload: CpImportCommitRow[] = filled.map((e, index) => ({
        row_index: index,
        company_id: companyId,
        employee_id: e.id,
        year,
        month,
        cp_n1_solde: parseSolde(values[e.id]?.n1 ?? ''),
        cp_n_solde: parseSolde(values[e.id]?.n ?? ''),
        source_file: 'saisie manuelle',
        period_label: periodLabel,
        confirmed: true,
      }));
      if (payload.length === 0) {
        throw new Error('Aucun compteur saisi.');
      }
      return commitCpImport({ rows: payload });
    },
    onSuccess: (data) => {
      toast({
        title: 'Compteurs CP enregistrés',
        description: `${data.applied} salarié(s) recalé(s)${data.skipped ? `, ${data.skipped} ignoré(s)` : ''}.`,
      });
      if (data.errors.length > 0) {
        toast({
          title: 'Avertissements',
          description: data.errors.slice(0, 3).join(' '),
          variant: 'destructive',
        });
      }
      setValues({});
      setOpen(false);
      onComplete?.();
    },
    onError: (error) => {
      toast({
        title: 'Enregistrement impossible',
        description: getUserErrorMessage(error),
        variant: 'destructive',
      });
    },
  });

  const setValue = (employeeId: string, key: 'n1' | 'n', raw: string) => {
    setValues((prev) => ({
      ...prev,
      [employeeId]: { n1: '', n: '', ...prev[employeeId], [key]: raw },
    }));
  };

  if (!open) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <PencilLine className="h-4 w-4" />
            Saisie manuelle des compteurs
          </CardTitle>
          <CardDescription>
            Pas de bulletin PDF sous la main ? Saisis directement les compteurs
            CP N-1 / CP N (état du service paie) — même mécanisme de reprise
            que l&apos;import de bulletins.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button type="button" variant="outline" onClick={() => setOpen(true)}>
            Saisir sans bulletin
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <PencilLine className="h-4 w-4" />
          Saisie manuelle des compteurs{companyName ? ` — ${companyName}` : ''}
        </CardTitle>
        <CardDescription>
          Compteurs tels qu&apos;ils figurent sur les bulletins à la FIN du mois
          choisi. Les salariés laissés vides ne sont pas touchés.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label className="text-xs">Compteurs à fin de</Label>
            <div className="flex items-center gap-2">
              <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
                <SelectTrigger className="h-9 w-[130px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MOIS_FR.map((label, i) => (
                    <SelectItem key={label} value={String(i + 1)}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                type="number"
                className="h-9 w-[90px]"
                value={year}
                onChange={(e) => setYear(Number(e.target.value) || year)}
              />
            </div>
          </div>
        </div>

        {rosterQuery.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Chargement des salariés…
          </div>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucun salarié présent dans cette société.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Salarié</TableHead>
                <TableHead className="w-[130px]">CP N-1 (j)</TableHead>
                <TableHead className="w-[130px]">CP N (j)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="font-medium">
                    {e.last_name} {e.first_name}
                  </TableCell>
                  <TableCell>
                    <Input
                      inputMode="decimal"
                      placeholder="—"
                      className="h-8"
                      value={values[e.id]?.n1 ?? ''}
                      onChange={(ev) => setValue(e.id, 'n1', ev.target.value)}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      inputMode="decimal"
                      placeholder="—"
                      className="h-8"
                      value={values[e.id]?.n ?? ''}
                      onChange={(ev) => setValue(e.id, 'n', ev.target.value)}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        <div className="flex items-center gap-3">
          <Button
            type="button"
            onClick={() => commitMutation.mutate()}
            disabled={commitMutation.isPending || filled.length === 0}
          >
            {commitMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Enregistrer {filled.length > 0 ? `(${filled.length})` : ''}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => setOpen(false)}
            disabled={commitMutation.isPending}
          >
            Annuler
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
