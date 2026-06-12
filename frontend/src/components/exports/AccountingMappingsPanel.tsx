import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Settings2 } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { useToast } from "@/hooks/use-toast";
import {
  getAccountingMappings,
  upsertAccountingMapping,
  type AccountingMapping,
} from "@/api/exports";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SharkFinLoader } from "@/components/SharkFinLoader";
import { ExportCardRefreshOverlay } from "@/components/exports/ExportCardRefreshOverlay";
import { exportsLiveQueryOptions, refreshExportsPageQueries } from "@/lib/exportsQuery";

export function AccountingMappingsPanel() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const { toast } = useToast();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<AccountingMapping | null>(null);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["accounting-mappings", companyId],
    queryFn: () => getAccountingMappings(companyId),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const saveMutation = useMutation({
    mutationFn: (body: Parameters<typeof upsertAccountingMapping>[1]) =>
      upsertAccountingMapping(companyId, body),
    onSuccess: () => {
      toast({ title: "Compte comptable enregistré" });
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["accounting-mappings", companyId] });
      refreshExportsPageQueries(qc, companyId);
    },
    onError: (e: Error) => {
      toast({ title: "Erreur", description: e.message, variant: "destructive" });
    },
  });

  if (!companyId) return null;

  return (
    <Card id="accounting-mappings" className="relative">
      <ExportCardRefreshOverlay
        visible={isFetching && !isLoading}
        label="Actualisation des comptes…"
      />
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Settings2 className="h-5 w-5" />
          Comptes comptables PCG (paie)
        </CardTitle>
        <CardDescription>
          Personnalisez le mapping rubriques → comptes pour votre société. Les valeurs par défaut
          s&apos;appliquent si aucun override n&apos;est défini.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <SharkFinLoader className="min-h-[160px]" label="Chargement des comptes comptables…" />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rubrique</TableHead>
                  <TableHead>Compte</TableHead>
                  <TableHead>Journal</TableHead>
                  <TableHead>Sens</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.mappings ?? []).map((m) => (
                  <TableRow key={m.rubrique_code}>
                    <TableCell>
                      <div className="font-medium">{m.rubrique_libelle}</div>
                      <div className="text-muted-foreground text-xs">{m.rubrique_code}</div>
                    </TableCell>
                    <TableCell>{m.compte_comptable}</TableCell>
                    <TableCell>{m.journal}</TableCell>
                    <TableCell>{m.sens}</TableCell>
                    <TableCell>
                      {m.is_global_default && !m.company_id ? "Défaut global" : "Société"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setEditing(m)}
                      >
                        Modifier
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {editing ? (
          <div className="mt-6 space-y-3 rounded-lg border p-4">
            <p className="font-medium">Override — {editing.rubrique_libelle}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label>Compte comptable</Label>
                <Input
                  value={editing.compte_comptable}
                  onChange={(e) =>
                    setEditing({ ...editing, compte_comptable: e.target.value })
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>Journal</Label>
                <Input
                  value={editing.journal}
                  onChange={(e) => setEditing({ ...editing, journal: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label>Sens</Label>
                <Select
                  value={editing.sens}
                  onValueChange={(v) =>
                    setEditing({ ...editing, sens: v as "debit" | "credit" })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="debit">Débit</SelectItem>
                    <SelectItem value="credit">Crédit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                disabled={saveMutation.isPending}
                onClick={() =>
                  saveMutation.mutate({
                    rubrique_code: editing.rubrique_code,
                    rubrique_libelle: editing.rubrique_libelle,
                    compte_comptable: editing.compte_comptable,
                    journal: editing.journal,
                    sens: editing.sens,
                    type_rubrique: editing.type_rubrique,
                    analytique: editing.analytique ?? undefined,
                    is_active: true,
                  })
                }
              >
                Enregistrer
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(null)}>
                Annuler
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
