import { useMemo } from 'react';
import { Percent } from 'lucide-react';
import type { DsnImportItemPreview } from '@/api/dsnImport';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

function formatOccurrence(value: unknown): string {
  if (value === -1) return 'Dernier du mois';
  if (value === null || value === undefined) return '—';
  return String(value);
}

export function DsnCompanyPayrollExtractCard({
  establishmentItem,
}: {
  establishmentItem: DsnImportItemPreview | null;
}) {
  const payload = establishmentItem?.mapped_payload ?? {};
  const extract =
    (establishmentItem as DsnImportItemPreview & { payroll_extract?: Record<string, unknown> })
      ?.payroll_extract ??
    (payload._dsn_extracted as Record<string, unknown> | undefined) ??
    {};

  const rows = useMemo(() => {
    const fields = ['taux_at_mp', 'paie_occurrence'] as const;
    return fields
      .map((field) => {
        const dsnVal = extract[field] ?? payload[field];
        if (dsnVal === null || dsnVal === undefined || dsnVal === '') return null;
        return { field, dsnVal };
      })
      .filter(Boolean) as Array<{ field: (typeof fields)[number]; dsnVal: unknown }>;
  }, [extract, payload]);

  if (!establishmentItem || rows.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Percent className="h-4 w-4 text-amber-600" />
          Paramètres paie (DSN)
        </CardTitle>
        <CardDescription>
          Le taux AT/MP et l&apos;occurrence paie seront mis à jour automatiquement à la
          validation de l&apos;import.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-wrap gap-3">
          {rows.map(({ field, dsnVal }) => (
            <div
              key={field}
              className="flex min-w-[140px] flex-col gap-1 rounded-lg border bg-muted/20 px-3 py-2"
            >
              <dt className="text-xs text-muted-foreground">
                {field === 'taux_at_mp' ? 'Taux AT/MP (%)' : 'Occurrence paie'}
              </dt>
              <dd className="flex items-center gap-2">
                <span className="font-semibold tabular-nums">
                  {field === 'paie_occurrence' ? formatOccurrence(dsnVal) : String(dsnVal)}
                </span>
                <Badge variant="secondary" className="bg-emerald-50 text-[10px] text-emerald-800">
                  Auto
                </Badge>
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
