import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { Loader2 } from "lucide-react";
import { getPlatformAuditLogs, type PlatformAuditLogEntry } from "@/api/adminEYWAI";
import { getActionLabel } from "@/lib/auditLabels";
import { AdminPageHeader } from "@/features/admin/components/eywai/AdminPageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

export default function ActivityLog() {
  const [searchParams] = useSearchParams();
  const initialCompany = searchParams.get("company") ?? "";
  const [logs, setLogs] = useState<PlatformAuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [companyId, setCompanyId] = useState(initialCompany);
  const [userEmail, setUserEmail] = useState("");
  const [actionFilter, setActionFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getPlatformAuditLogs({
        company_id: companyId || undefined,
        limit: 100,
        offset: 0,
      });
      let filtered = data;
      if (userEmail.trim()) {
        const q = userEmail.trim().toLowerCase();
        filtered = filtered.filter((e) => e.user_email?.toLowerCase().includes(q));
      }
      if (actionFilter.trim()) {
        filtered = filtered.filter((e) => e.action.includes(actionFilter.trim()));
      }
      setLogs(filtered);
    } catch {
      setLoadError("Impossible de charger le journal d'activité.");
    } finally {
      setLoading(false);
    }
  }, [companyId, userEmail, actionFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Journal d'activité"
        description="Traçabilité des actions réalisées sur la plateforme par entreprise et par utilisateur."
      />

      <Card>
        <CardContent className="grid gap-4 pt-6 md:grid-cols-4">
          <div className="space-y-2">
            <Label htmlFor="company-id">ID entreprise</Label>
            <Input
              id="company-id"
              placeholder="UUID…"
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">E-mail utilisateur</Label>
            <Input
              id="email"
              placeholder="filtrer…"
              value={userEmail}
              onChange={(e) => setUserEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="action">Code action</Label>
            <Input
              id="action"
              placeholder="ex. user.create"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button className="w-full" onClick={() => void load()}>
              Appliquer les filtres
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : loadError && logs.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-destructive">{loadError}</p>
              <Button className="mt-4" variant="outline" onClick={() => void load()}>
                Réessayer
              </Button>
            </div>
          ) : logs.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">
              Aucune entrée pour ces critères.
            </p>
          ) : (
            <>
              {loadError ? (
                <div className="flex items-center justify-between gap-4 border-b px-4 py-3">
                  <p className="text-sm text-destructive">{loadError}</p>
                  <Button variant="outline" size="sm" onClick={() => void load()}>
                    Réessayer
                  </Button>
                </div>
              ) : null}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Utilisateur</TableHead>
                  <TableHead>Entreprise</TableHead>
                  <TableHead>Ressource</TableHead>
                  <TableHead className="w-[80px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap text-xs">
                      {formatDate(entry.created_at)}
                    </TableCell>
                    <TableCell className="text-sm font-medium">
                      {getActionLabel(entry.action)}
                    </TableCell>
                    <TableCell className="text-sm">{entry.user_email ?? "—"}</TableCell>
                    <TableCell className="max-w-[140px] truncate text-sm">
                      {entry.company_name ?? entry.company_id.slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {entry.resource_type}
                      {entry.resource_id ? ` · ${entry.resource_id.slice(0, 8)}` : ""}
                    </TableCell>
                    <TableCell>
                      {entry.details && Object.keys(entry.details).length > 0 ? (
                        <Collapsible>
                          <CollapsibleTrigger asChild>
                            <Button variant="ghost" size="sm">
                              Détail
                            </Button>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <pre className="mt-1 max-w-xs overflow-auto rounded bg-muted p-2 text-[10px]">
                              {JSON.stringify(entry.details, null, 2)}
                            </pre>
                          </CollapsibleContent>
                        </Collapsible>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    return format(new Date(iso), "dd/MM/yyyy HH:mm", { locale: fr });
  } catch {
    return iso;
  }
}
