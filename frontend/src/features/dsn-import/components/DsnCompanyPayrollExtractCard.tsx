import { useMemo } from 'react';
import { Percent, CalendarDays, AlertTriangle } from 'lucide-react';
import type { DsnImportItemPreview } from '@/api/dsnImport';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table';

type PayrollField = 'taux_at_mp' | 'paie_jour_de_fin' | 'paie_occurrence' | 'effectif';

const FIELD_LABELS: Record<PayrollField, string> = {
  taux_at_mp: 'Taux AT/MP (%)',
  paie_jour_de_fin: 'Jour fin période',
  paie_occurrence: 'Occurrence paie',
  effectif: 'Effectif',
};

function formatOccurrence(value: unknown): string {
  if (value === -1) return 'Dernier du mois';
  if (value === null || value === undefined) return '—';
  return String(value);
}

export function DsnCompanyPayrollExtractCard({
  establishmentItem,
  applyFields,
  onToggleField,
}: {
  establishmentItem: DsnImportItemPreview | null;
  applyFields: Set<PayrollField>;
  onToggleField: (field: PayrollField, checked: boolean) => void;
}) {
  const payload = establishmentItem?.mapped_payload ?? {};
  const extract = (establishmentItem as DsnImportItemPreview & { payroll_extract?: Record<string, unknown> })
    ?.payroll_extract ?? (payload._dsn_extracted as Record<string, unknown> | undefined) ?? {};
  const conflicts =
    (establishmentItem as DsnImportItemPreview & { payroll_conflicts?: Record<string, { existing: unknown; dsn: unknown }> })
      ?.payroll_conflicts ??
    (payload._payroll_conflicts as Record<string, { existing: unknown; dsn: unknown }> | undefined) ??
    {};

  const rows = useMemo(() => {
    const fields: PayrollField[] = ['taux_at_mp', 'paie_jour_de_fin', 'paie_occurrence', 'effectif'];
    return fields
      .map((field) => {
        const dsnVal = extract[field] ?? payload[field];
        if (dsnVal === null || dsnVal === undefined || dsnVal === '') return null;
        return { field, dsnVal, conflict: conflicts[field] };
      })
      .filter(Boolean) as Array<{
      field: PayrollField;
      dsnVal: unknown;
      conflict?: { existing: unknown; dsn: unknown };
    }>;
  }, [extract, payload, conflicts]);

  if (!establishmentItem || rows.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Percent className="h-4 w-4 text-amber-600" />
          Paramètres paie extraits (DSN)
        </CardTitle>
        <CardDescription>
          Cochez les champs à appliquer. Les valeurs déjà renseignées en base ne sont pas écrasées
          sans votre accord.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Table>
          <TableBody>
            {rows.map(({ field, dsnVal, conflict }) => (
              <TableRow key={field}>
                <TableCell className="w-10">
                  <Checkbox
                    id={`payroll-apply-${field}`}
                    checked={applyFields.has(field)}
                    onCheckedChange={(checked) => onToggleField(field, Boolean(checked))}
                    disabled={!conflict && establishmentItem.action === 'update'}
                  />
                </TableCell>
                <TableCell className="font-medium text-muted-foreground">
                  <Label htmlFor={`payroll-apply-${field}`}>{FIELD_LABELS[field]}</Label>
                </TableCell>
                <TableCell className="font-semibold tabular-nums">
                  {field === 'paie_occurrence' ? formatOccurrence(dsnVal) : String(dsnVal)}
                </TableCell>
                <TableCell>
                  {conflict ? (
                    <Badge variant="outline" className="gap-1 border-amber-300 bg-amber-50 text-amber-900">
                      <AlertTriangle className="h-3 w-3" />
                      Existant : {String(conflict.existing)}
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="bg-emerald-50 text-emerald-800">
                      Nouveau
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {(extract.dsn_organismes as unknown[] | undefined)?.length ? (
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <CalendarDays className="h-3 w-3" />
            {(extract.dsn_organismes as unknown[]).length} versement(s) organisme enregistré(s) dans les
            métadonnées entreprise.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export type { PayrollField };
