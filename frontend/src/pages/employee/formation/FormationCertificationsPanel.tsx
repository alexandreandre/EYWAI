import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { SharkFinLoader } from '@/components/SharkFinLoader';

import { getEmployeeCertifications, type EmployeeCertification } from "@/api/certifications";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  type CertFilter,
  filterCertifications,
  sortCertificationsByUrgency,
} from "@/lib/employeeFormationUtils";

import { certStatusBadge, fmtDate } from "./employeeFormationFormatters";

export function FormationCertificationsPanel({ employeeId }: { employeeId: string }) {
  const [filter, setFilter] = useState<CertFilter>("all");

  const q = useQuery({
    queryKey: ["formation-certs", employeeId],
    queryFn: () => getEmployeeCertifications({ employee_id: employeeId, include_archived: false }),
  });

  const sortedRows = useMemo(() => {
    const rows = sortCertificationsByUrgency(q.data ?? []);
    return filterCertifications(rows, filter);
  }, [q.data, filter]);

  const watchCount = useMemo(
    () =>
      (q.data ?? []).filter(
        (r) => r.computed_status === "expiring_soon" || r.computed_status === "expired",
      ).length,
    [q.data],
  );

  if (q.isLoading) {
    return <SharkFinLoader label="Chargement des habilitations…" />;
  }
  if (q.isError) {
    return <p className="text-sm text-destructive">Impossible de charger vos habilitations.</p>;
  }
  const rows = q.data ?? [];
  if (rows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Aucune habilitation enregistrée pour votre profil.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {watchCount > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p>
            {watchCount === 1
              ? "1 habilitation nécessite votre attention (expirée ou expiration proche)."
              : `${watchCount} habilitations nécessitent votre attention.`}
          </p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["all", "Toutes"],
            ["watch", "À surveiller"],
            ["valid", "Valides"],
          ] as const
        ).map(([value, label]) => (
          <Button
            key={value}
            type="button"
            size="sm"
            variant={filter === value ? "default" : "outline"}
            onClick={() => setFilter(value)}
          >
            {label}
          </Button>
        ))}
      </div>

      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Habilitation</TableHead>
              <TableHead>Obtention</TableHead>
              <TableHead>Expiration</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead className="text-right">Certificat</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedRows.map((r: EmployeeCertification) => (
              <TableRow
                key={r.id}
                className={cn(
                  (r.computed_status === "expiring_soon" || r.computed_status === "expired") &&
                    "bg-amber-50/50 dark:bg-amber-950/20",
                )}
              >
                <TableCell className="font-medium">{r.certification_ref?.name ?? "—"}</TableCell>
                <TableCell>{fmtDate(r.obtained_date)}</TableCell>
                <TableCell>{r.expiry_date ? fmtDate(r.expiry_date) : "—"}</TableCell>
                <TableCell>{certStatusBadge(r.computed_status)}</TableCell>
                <TableCell className="text-right">
                  {r.certificate_url ? (
                    <Button variant="outline" size="sm" asChild>
                      <a href={r.certificate_url} target="_blank" rel="noopener noreferrer">
                        Voir certificat
                      </a>
                    </Button>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {sortedRows.length === 0 && filter !== "all" && (
        <p className="text-center text-sm text-muted-foreground">Aucune habilitation dans cette catégorie.</p>
      )}
    </div>
  );
}
