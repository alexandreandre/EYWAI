import { useQuery } from '@tanstack/react-query';
import { getModulationOverview } from '@/api/modulation';
import { useCompany } from '@/contexts/CompanyContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { queryKeys } from '@/lib/queryKeys';

export default function SuiviModulationPage() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const year = new Date().getFullYear();

  const { data = [], isLoading } = useQuery({
    queryKey: queryKeys.modulationOverview(companyId, year),
    queryFn: () => getModulationOverview(year),
    enabled: Boolean(companyId),
  });

  return (
    <div className="container max-w-5xl py-6 space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Suivi modulation</h1>
      <p className="text-sm text-muted-foreground">
        Solde théorique vs réalisé par salarié pour l&apos;année {year}.
      </p>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Effectif</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Théorique (h)</TableHead>
                  <TableHead>Réalisé (h)</TableHead>
                  <TableHead>Solde (h)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((row) => (
                  <TableRow key={row.employee_id}>
                    <TableCell>
                      {row.first_name} {row.last_name}
                    </TableCell>
                    <TableCell>{row.theoretical_hours.toFixed(2)}</TableCell>
                    <TableCell>{row.actual_hours.toFixed(2)}</TableCell>
                    <TableCell
                      className={
                        row.balance_hours < 0
                          ? 'text-destructive font-medium'
                          : row.balance_hours > 0
                            ? 'text-amber-700 font-medium'
                            : ''
                      }
                    >
                      {row.balance_hours > 0 ? '+' : ''}
                      {row.balance_hours.toFixed(2)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
