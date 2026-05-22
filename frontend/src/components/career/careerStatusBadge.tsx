import { Badge } from "@/components/ui/badge";
import { PromotionBadge } from "@/components/PromotionBadge";
import type { PromotionStatus, PromotionType } from "@/api/promotions";
import { cn } from "@/lib/utils";

const DOC_STATUS: Record<string, { className: string; label: string }> = {
  brouillon: { className: "bg-amber-100 text-amber-900 border-amber-200", label: "Brouillon" },
  envoye: { className: "bg-blue-100 text-blue-900 border-blue-200", label: "Envoyé" },
  signe: { className: "bg-emerald-100 text-emerald-900 border-emerald-200", label: "Signé" },
  archive: { className: "bg-slate-100 text-slate-700 border-slate-200", label: "Archivé" },
};

export function CareerKindBadge({ kind }: { kind: string }) {
  const labels: Record<string, string> = {
    promotion: "Promotion",
    salary_review_session: "Augmentation",
    avenant: "Avenant salaire",
  };
  return (
    <Badge variant="outline" className="font-medium">
      {labels[kind] ?? kind}
    </Badge>
  );
}

export function CareerStatusBadge({
  kind,
  status,
  promotionType,
}: {
  kind: string;
  status?: string;
  promotionType?: PromotionType | null;
}) {
  if (kind === "promotion" && promotionType) {
    return <PromotionBadge type={promotionType} variant="type" compact showTooltip={false} />;
  }
  if (kind === "promotion" && status) {
    return (
      <PromotionBadge
        status={status as PromotionStatus}
        variant="status"
        compact
        showTooltip={false}
      />
    );
  }
  if (kind === "avenant" && status) {
    const m = DOC_STATUS[status] ?? {
      className: "bg-muted text-muted-foreground",
      label: status,
    };
    return (
      <Badge variant="outline" className={cn("font-medium", m.className)}>
        {m.label}
      </Badge>
    );
  }
  if (kind === "salary_review_session") {
    return (
      <Badge variant="outline" className="bg-blue-50 text-blue-800 border-blue-200">
        Collective
      </Badge>
    );
  }
  return <span className="text-muted-foreground">—</span>;
}
