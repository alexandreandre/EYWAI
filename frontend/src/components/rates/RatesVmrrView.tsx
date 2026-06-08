import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

function communeLabel(row: Record<string, unknown>): string {
  for (const [key, val] of Object.entries(row)) {
    const keyLower = key.toLowerCase();
    if (val == null || String(val).trim() === '') continue;
    if (
      keyLower.includes('commune') ||
      keyLower === 'libelle' ||
      keyLower === 'libcom'
    ) {
      return String(val).trim();
    }
  }
  return '—';
}

function tauxLabel(row: Record<string, unknown>): string {
  for (const key of ['taux', 'Taux', 'taux_vm', 'TAUX']) {
    if (row[key] != null && String(row[key]).trim() !== '') {
      const raw = Number(String(row[key]).replace(',', '.').replace('%', ''));
      if (!Number.isFinite(raw)) return String(row[key]);
      const pct = Math.abs(raw) > 1 ? raw : raw * 100;
      return `${pct.toFixed(2).replace('.', ',')} %`;
    }
  }
  for (const [key, val] of Object.entries(row)) {
    if (key.toLowerCase().includes('taux') && val != null) {
      return String(val);
    }
  }
  return '—';
}

function normalizeVmrrRows(configData: unknown): Record<string, unknown>[] {
  if (Array.isArray(configData)) {
    return configData.filter(
      (row): row is Record<string, unknown> =>
        typeof row === 'object' && row !== null && !Array.isArray(row),
    );
  }
  if (configData && typeof configData === 'object') {
    const inner =
      (configData as { rows?: unknown; taux?: unknown }).rows ??
      (configData as { taux?: unknown }).taux;
    if (Array.isArray(inner)) {
      return inner.filter(
        (row): row is Record<string, unknown> =>
          typeof row === 'object' && row !== null && !Array.isArray(row),
      );
    }
  }
  return [];
}

export function RatesVmrrView({ configData }: { configData: unknown }) {
  const rows = normalizeVmrrRows(configData);

  if (rows.length === 0) {
    return (
      <p className="text-sm leading-relaxed text-muted-foreground">
        Barème non chargé. Cliquez sur{' '}
        <span className="font-medium text-foreground">⋮</span> puis{' '}
        <span className="font-medium text-foreground">Mise à jour</span> pour importer la
        table URSSAF (communes et taux VMRR).
      </p>
    );
  }

  const preview = rows.slice(0, 8);

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        <span className="font-medium tabular-nums text-foreground">{rows.length}</span>{' '}
        communes dans le barème national versement mobilité.
      </p>
      <Table>
        <TableHeader>
          <TableRow className="border-border/40 hover:bg-transparent">
            <TableHead className="h-9 text-xs font-medium text-muted-foreground">
              Commune
            </TableHead>
            <TableHead className="h-9 text-right text-xs font-medium text-muted-foreground">
              Taux VM
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {preview.map((row, index) => (
            <TableRow key={`${communeLabel(row)}-${index}`} className="border-border/40">
              <TableCell className="py-2 text-sm">{communeLabel(row)}</TableCell>
              <TableCell className="py-2 text-right text-sm font-medium tabular-nums">
                {tauxLabel(row)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {rows.length > preview.length && (
        <p className="text-xs text-muted-foreground">
          Aperçu limité aux {preview.length} premières lignes.
        </p>
      )}
    </div>
  );
}
