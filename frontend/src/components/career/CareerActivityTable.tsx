import { Fragment, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Loader2, Trash2 } from "lucide-react";

import { deleteDocument } from "@/api/documents";
import type { GeneratedDocument } from "@/api/documents";
import type { Promotion, PromotionListItem } from "@/api/promotions";
import { AvenantRowActions } from "@/components/career/AvenantRowActions";
import { CareerKindBadge, CareerStatusBadge } from "@/components/career/careerStatusBadge";
import { PromotionsActions } from "@/components/career/PromotionsActions";
import type { CareerActivityItem, SalaryReviewSession } from "@/components/career/types";
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
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateFR } from "@/lib/careerFormat";
import { AVENANTS_QUERY_KEY } from "@/lib/careerActivity";
import { toast } from "@/components/ui/use-toast";

type CareerActivityTableProps = {
  items: CareerActivityItem[];
  companyId: string;
  onEditPromotion: (promotion: Promotion) => void;
};

function employeesLabel(item: CareerActivityItem): string {
  if (item.employees.length === 0) return "—";
  if (item.employees.length === 1) return item.employees[0].name;
  if (item.employees.length <= 3) {
    return item.employees.map((e) => e.name).join(", ");
  }
  return `${item.employees[0].name} et ${item.employees.length - 1} autre(s)`;
}

function SessionExpandRow({
  session,
  companyId,
  colSpan,
}: {
  session: SalaryReviewSession;
  companyId: string;
  colSpan: number;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <TableRow className="bg-muted/30">
        <TableCell colSpan={colSpan} className="p-0">
          <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-start gap-2 rounded-none px-4 py-2 h-auto font-normal"
              >
                {open ? (
                  <ChevronDown className="h-4 w-4 shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0" />
                )}
                <span className="text-sm">
                  Voir les {session.documents.length} avenant(s) de cette augmentation
                </span>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="border-t px-4 py-3 space-y-2">
                {session.documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex flex-wrap items-center justify-between gap-2 text-sm"
                  >
                    <span className="font-medium">{doc.employee_name ?? "—"}</span>
                    <AvenantRowActions document={doc} companyId={companyId} />
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        </TableCell>
      </TableRow>
    </>
  );
}

function DeleteSessionButton({
  session,
  companyId,
}: {
  session: SalaryReviewSession;
  companyId: string;
}) {
  const queryClient = useQueryClient();
  const deleteSessionMut = useMutation({
    mutationFn: async () => {
      await Promise.all(session.documents.map((doc) => deleteDocument(doc.id)));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...AVENANTS_QUERY_KEY, companyId] });
      toast({
        title: "Campagne supprimée",
        description: "Les avenants de cette augmentation ont été retirés du registre.",
      });
    },
    onError: () => {
      toast({
        title: "Suppression impossible",
        description: "Un des avenants n'a pas pu être supprimé.",
        variant: "destructive",
      });
    },
  });

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 text-destructive hover:text-destructive"
          aria-label="Supprimer la campagne d'augmentation"
          title="Supprimer la campagne"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Supprimer cette campagne ?</AlertDialogTitle>
          <AlertDialogDescription>
            Les {session.documents.length} avenant(s) de cette augmentation seront retirés du
            registre. Cette action est irréversible.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => deleteSessionMut.mutate()}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={deleteSessionMut.isPending}
          >
            {deleteSessionMut.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Suppression...
              </>
            ) : (
              "Supprimer"
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function CareerActivityTable({
  items,
  companyId,
  onEditPromotion,
}: CareerActivityTableProps) {
  const navigate = useNavigate();
  const colSpan = 6;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Concerné(s)</TableHead>
          <TableHead>Détail</TableHead>
          <TableHead>Statut</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => {
          const promotion =
            item.kind === "promotion" ? (item.raw as PromotionListItem) : null;
          const avenant = item.kind === "avenant" ? (item.raw as GeneratedDocument) : null;
          const session =
            item.kind === "salary_review_session"
              ? (item.raw as SalaryReviewSession)
              : null;

          return (
            <Fragment key={item.id}>
              <TableRow
                className={
                  item.kind === "promotion"
                    ? "cursor-pointer hover:bg-muted/50"
                    : undefined
                }
                onClick={() => {
                  if (promotion) navigate(`/promotions/${promotion.id}`);
                }}
              >
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {formatDateFR(item.date)}
                </TableCell>
                <TableCell>
                  <CareerKindBadge kind={item.kind} />
                </TableCell>
                <TableCell className="font-medium">{employeesLabel(item)}</TableCell>
                <TableCell className="text-muted-foreground max-w-[280px] truncate">
                  {item.detail}
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <CareerStatusBadge
                    kind={item.kind}
                    status={item.status}
                    promotionType={item.promotionType}
                  />
                </TableCell>
                <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                  {promotion && (
                    <PromotionsActions
                      item={promotion}
                      onView={() => navigate(`/promotions/${promotion.id}`)}
                      onEdit={onEditPromotion}
                    />
                  )}
                  {avenant && (
                    <AvenantRowActions document={avenant} companyId={companyId} />
                  )}
                  {session && (
                    <DeleteSessionButton session={session} companyId={companyId} />
                  )}
                </TableCell>
              </TableRow>
              {session && (
                <SessionExpandRow
                  session={session}
                  companyId={companyId}
                  colSpan={colSpan}
                />
              )}
            </Fragment>
          );
        })}
      </TableBody>
    </Table>
  );
}
