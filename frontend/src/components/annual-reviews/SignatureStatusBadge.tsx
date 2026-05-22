import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { signatureStatusLabel } from "@/lib/annualReviewLabels";

const SIGNATURE_CLASSES: Record<string, string> = {
  pending: "border-transparent bg-warning/15 text-warning",
  signed: "border-transparent bg-success/15 text-success",
  refused: "border-transparent bg-destructive/15 text-destructive",
  expired: "border-transparent bg-muted text-muted-foreground",
};

interface SignatureStatusBadgeProps {
  status: string | null | undefined;
  className?: string;
}

export function SignatureStatusBadge({ status, className }: SignatureStatusBadgeProps) {
  if (!status) return null;
  const label = signatureStatusLabel(status) ?? status;
  const key = status.toLowerCase();
  const tone = SIGNATURE_CLASSES[key] ?? "bg-muted text-muted-foreground";

  return (
    <Badge variant="outline" className={cn(tone, "font-normal", className)}>
      {label}
    </Badge>
  );
}
