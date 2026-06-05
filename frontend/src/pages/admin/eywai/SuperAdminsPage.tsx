import { useQuery } from "@tanstack/react-query";
import { Shield } from "lucide-react";
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { listSuperAdmins } from "@/api/adminEYWAI";
import { AdminPageHeader } from "@/features/admin/components/eywai/AdminPageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function SuperAdminsPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["admin", "super-admins"],
    queryFn: listSuperAdmins,
  });

  const rows = data?.platform_admins ?? data?.super_admins ?? [];

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Équipe EYWAI"
        description="Comptes disposant de l'accès Administration plateforme."
      />

      <Card>
        <CardContent className="p-0 pt-0">
          {isLoading ? (
            <SharkFinLoader label="Chargement de l'équipe EYWAI…" />
          ) : isError && rows.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-destructive">
                Impossible de charger l&apos;équipe EYWAI.
              </p>
              <Button className="mt-4" variant="outline" onClick={() => void refetch()}>
                Réessayer
              </Button>
            </div>
          ) : (
            <>
              {isError ? (
                <div className="flex items-center justify-between gap-4 border-b px-4 py-3">
                  <p className="text-sm text-destructive">
                    Impossible de charger l&apos;équipe EYWAI.
                  </p>
                  <Button variant="outline" size="sm" onClick={() => void refetch()}>
                    Réessayer
                  </Button>
                </div>
              ) : null}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Identifiant</TableHead>
                  <TableHead>E-mail</TableHead>
                  <TableHead>Statut</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const r = row as Record<string, unknown>;
                  return (
                    <TableRow key={String(r.user_id ?? r.id)}>
                      <TableCell>
                        <Shield className="mr-2 inline h-4 w-4 text-primary" />
                        {String(r.user_id ?? r.id).slice(0, 12)}…
                      </TableCell>
                      <TableCell>{String(r.email ?? "—")}</TableCell>
                      <TableCell>{r.is_active === false ? "Inactif" : "Actif"}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
