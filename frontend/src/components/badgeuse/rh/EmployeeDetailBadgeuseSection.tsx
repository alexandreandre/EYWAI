import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getEmployeeBadgeQr,
  regenerateEmployeeBadge,
  getEmployeeDaysSummary,
} from "@/api/badgeuse";
import { BadgeCardExport } from "@/components/badgeuse/rh/BadgeCardExport";
import { formatSecondsToHoursMinutes } from "@/lib/badgeuseFormat";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";

type Props = {
  employeeId: string;
  companyId: string;
  employeeName: string;
};

export function EmployeeDetailBadgeuseSection({
  employeeId,
  companyId,
  employeeName,
}: Props) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const weekEnd = new Date().toISOString().slice(0, 10);
  const weekStart = new Date();
  weekStart.setDate(weekStart.getDate() - 6);
  const from = weekStart.toISOString().slice(0, 10);

  const { data: qr, isLoading: qrLoading } = useQuery({
    queryKey: ["badgeuse", "employee-qr", employeeId, companyId],
    queryFn: () => getEmployeeBadgeQr(employeeId, companyId),
  });

  const { data: days } = useQuery({
    queryKey: ["badgeuse", "employee-days", companyId, employeeId, from, weekEnd],
    queryFn: () => getEmployeeDaysSummary(employeeId, companyId, from, weekEnd),
  });

  const regenerateMutation = useMutation({
    mutationFn: () => regenerateEmployeeBadge(employeeId, companyId),
    onSuccess: () => {
      toast.success("Nouveau QR généré — les anciennes cartes ne fonctionnent plus.");
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-qr", employeeId, companyId],
      });
      setConfirmOpen(false);
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Échec de la régénération";
      toast.error(String(message));
    },
  });

  return (
    <Card className="p-6 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">Badgeuse</h3>
          <p className="text-sm text-muted-foreground">
            Carte QR et historique des 7 derniers jours
          </p>
        </div>
        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <AlertDialogTrigger asChild>
            <Button variant="outline" size="sm" type="button">
              Régénérer le QR
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Régénérer le badge ?</AlertDialogTitle>
              <AlertDialogDescription>
                Les cartes et QR actuels de {employeeName} ne fonctionneront plus.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => regenerateMutation.mutate()}
                disabled={regenerateMutation.isPending}
              >
                Confirmer
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      {qrLoading && (
        <p className="text-sm text-muted-foreground">Chargement du QR…</p>
      )}
      {qr?.qr_payload && (
        <BadgeCardExport
          qrPayload={qr.qr_payload}
          displayName={qr.employee_display_name || employeeName}
          username={qr.badge_username}
        />
      )}

      <div>
        <h4 className="text-sm font-medium mb-2">7 derniers jours</h4>
        {!days?.length ? (
          <p className="text-sm text-muted-foreground">Aucun pointage sur la période.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {days.map((d) => (
              <li
                key={d.date}
                className="flex justify-between rounded-md border px-3 py-2"
              >
                <span>
                  {d.date} — {d.status}
                  {d.has_anomalies && " ⚠"}
                </span>
                <span className="tabular-nums text-muted-foreground">
                  {formatSecondsToHoursMinutes(d.total_seconds)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
