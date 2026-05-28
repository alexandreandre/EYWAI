import { formatPercent, formatRateKey } from '@/lib/ratesUtils';

export function RatesRateValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">-</span>;
  }
  if (typeof value === 'number') {
    return <span>{formatPercent(value)}</span>;
  }
  if (typeof value === 'object' && value !== null) {
    return (
      <div className="flex flex-col items-end">
        {Object.entries(value as Record<string, unknown>).map(([key, val]) => (
          <div key={key}>
            <span className="text-xs text-muted-foreground">{formatRateKey(key)}: </span>
            <span className="font-medium">{formatPercent(val)}</span>
          </div>
        ))}
      </div>
    );
  }
  return <span>{String(value)}</span>;
}
