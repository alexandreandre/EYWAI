import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getEnrollments,
  getPendingManagerApproval,
  managerApprove,
  type TrainingEnrollment,
} from "@/api/training";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { useCompany } from "@/contexts/CompanyContext";
import { Loader2 } from "lucide-react";

import { useCanQueryRhApis, useManagerTeamMemberIds } from "@/pages/manager/teamScope";

function enrollmentStatusBadge(status: string) {
  const s = status.toLowerCase();
  const cfg: Record<string, { label: string; className: string }> = {
    planned: { label: "Planifié", className: "bg-blue-600 text-white hover:bg-blue-600" },
    in_progress: { label: "En cours", className: "bg-orange-500 text-white hover:bg-orange-500" },
    completed: { label: "Terminé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    realise: { label: "Réalisé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    cancelled: { label: "Annulé", className: "bg-muted text-muted-foreground" },
    demande_salarie: {
      label: "En attente manager",
      className: "bg-amber-400 text-amber-950 hover:bg-amber-400",
    },
    approuve_manager: {
      label: "En attente RH",
      className: "bg-sky-600 text-white hover:bg-sky-600",
    },
    approuve_rh: { label: "Inscrit", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    rejete_manager: {
      label: "Refusé par le manager",
      className: "bg-red-600 text-white hover:bg-red-600",
    },
    rejete_rh: { label: "Refusé par la RH", className: "bg-red-600 text-white hover:bg-red-600" },
  };
  const x = cfg[s] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return <Badge className={x.className}>{x.label}</Badge>;
}

function fmtDate(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fr-FR");
}

export default function ManagerFormations() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";
  const canRh = useCanQueryRhApis(activeCompany);
  const teamQ = useManagerTeamMemberIds();

  const [rejectRow, setRejectRow] = useState<TrainingEnrollment | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const pendingQ = useQuery({
    queryKey: ["formation-demandes", "pending-manager", companyId, "manager-page"],
    queryFn: () => getPendingManagerApproval(companyId),
    enabled: Boolean(companyId),
  });

  const enrollAllQ = useQuery({
    queryKey: ["training-enrollments", "manager-team", companyId],
    queryFn: () => getEnrollments({}),
    enabled: Boolean(companyId) && canRh,
  });

  const teamEnrollments = useMemo(() => {
    const ids = teamQ.data;
    const rows = enrollAllQ.data ?? [];
    if (!ids || ids.size === 0) return [];
    return rows.filter((e) => ids.has(e.employee_id));
  }, [enrollAllQ.data, teamQ.data]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["formation-demandes"] });
    void qc.invalidateQueries({ queryKey: ["training-enrollments"] });
    void qc.invalidateQueries({ queryKey: ["manager-team-member-ids"] });
  };

  const mgrMut = useMutation({
    mutationFn: async ({
      row,
      approved,
      reason,
    }: {
      row: TrainingEnrollment;
      approved: boolean;
      reason?: string;
    }) => managerApprove(row.id, companyId, { approved, rejection_reason: reason }),
    onSuccess: () => {
      toast({ title: "Décision enregistrée" });
      setRejectRow(null);
      setRejectReason("");
      invalidate();
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Action impossible.";
      toast({ title: "Erreur", description: String(detail), variant: "destructive" });
    },
  });

  const loadingBlock = pendingQ.isLoading || teamQ.isLoading;

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Formations de mon équipe</h1>
        <p className="text-sm text-muted-foreground">
          Demandes à valider et inscriptions des membres de votre périmètre.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Demandes à valider</h2>
        {loadingBlock ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : pendingQ.isError ? (
          <p className="text-sm text-destructive">Impossible de charger les demandes.</p>
        ) : (pendingQ.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune demande en attente de votre part.</p>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Formation</TableHead>
                  <TableHead>Date demande</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(pendingQ.data ?? []).map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.employee_name ?? "—"}</TableCell>
                    <TableCell>{row.training_title ?? "—"}</TableCell>
                    <TableCell>{fmtDate(row.created_at)}</TableCell>
                    <TableCell className="text-right space-x-2">
                      <Button
                        type="button"
                        size="sm"
                        disabled={mgrMut.isPending}
                        onClick={() => mgrMut.mutate({ row, approved: true })}
                      >
                        {mgrMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                        Approuver
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={mgrMut.isPending}
                        onClick={() => {
                          setRejectRow(row);
                          setRejectReason("");
                        }}
                      >
                        Refuser
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Inscriptions de l&apos;équipe</h2>
        {!canRh && (
          <p className="rounded-md border border-muted bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
            La liste complète des inscriptions nécessite des droits RH. Votre périmètre manager
            couvre surtout les demandes ci-dessus.
          </p>
        )}
        {canRh && enrollAllQ.isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        )}
        {canRh && enrollAllQ.isError && (
          <p className="text-sm text-destructive">Impossible de charger les inscriptions.</p>
        )}
        {canRh && !enrollAllQ.isLoading && !enrollAllQ.isError && teamEnrollments.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Aucune inscription pour les membres de votre équipe (ou équipe non paramétrée).
          </p>
        )}
        {canRh && teamEnrollments.length > 0 && (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Formation</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Dates</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {teamEnrollments.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.employee_name ?? "—"}</TableCell>
                    <TableCell>{row.training_title ?? "—"}</TableCell>
                    <TableCell>{enrollmentStatusBadge(row.status)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      Prévu : {fmtDate(row.planned_date)} — Fin : {fmtDate(row.completion_date)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <Dialog open={Boolean(rejectRow)} onOpenChange={(o) => !o && setRejectRow(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Refuser la demande</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="rej-reason">Motif (optionnel)</Label>
            <Textarea
              id="rej-reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setRejectRow(null)}>
              Annuler
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={mgrMut.isPending || !rejectRow}
              onClick={() => {
                if (!rejectRow) return;
                mgrMut.mutate({
                  row: rejectRow,
                  approved: false,
                  rejection_reason: rejectReason.trim() || undefined,
                });
              }}
            >
              Confirmer le refus
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
