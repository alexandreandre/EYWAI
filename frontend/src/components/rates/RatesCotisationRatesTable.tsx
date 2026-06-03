import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table';
import { RatesRateValue } from '@/components/rates/RatesRateValue';
import { formatRateKey, type Cotisation } from '@/lib/ratesUtils';

type RatesCotisationRatesTableProps = {
  cotisation: Cotisation;
};

export function RatesCotisationRatesTable({ cotisation }: RatesCotisationRatesTableProps) {
  return (
    <Table>
      <TableBody>
        {Object.entries(cotisation)
          .filter(([key]) => key.includes('salarial') || key.includes('patronal'))
          .map(([key, value]) => (
            <TableRow key={key} className="border-border/40">
              <TableCell className="h-auto py-2.5 text-sm text-muted-foreground">
                {formatRateKey(key)}
              </TableCell>
              <TableCell className="h-auto py-2.5 text-right text-sm font-medium tabular-nums">
                <RatesRateValue value={value} />
              </TableCell>
            </TableRow>
          ))}
      </TableBody>
    </Table>
  );
}
