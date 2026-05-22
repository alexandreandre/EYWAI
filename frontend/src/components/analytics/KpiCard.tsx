import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function KpiCard({
  label,
  value,
  hint,
  badge,
  delta,
  href,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  badge?: ReactNode;
  delta?: { value: number; worseIfPositive: boolean };
  href?: string;
}): JSX.Element {
  const evoNeutral = delta != null && Math.abs(delta.value) < 0.05;
  const evoWorse =
    delta != null && !evoNeutral && (delta.worseIfPositive ? delta.value > 0 : delta.value < 0);

  const content = (
    <CardContent className="flex flex-col gap-1 p-4">
      <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
        {label}
      </p>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <p className="text-2xl font-bold tabular-nums leading-none">{value}</p>
        {badge}
      </div>
      {hint ? <p className="text-muted-foreground text-xs">{hint}</p> : null}
      {delta != null ? (
        <div
          className={`flex items-center gap-1 text-xs font-medium ${
            evoNeutral
              ? "text-muted-foreground"
              : evoWorse
                ? "text-red-600"
                : "text-emerald-600"
          }`}
        >
          {!evoNeutral ? (
            delta.value > 0 ? (
              <ArrowUpRight className="h-3.5 w-3.5 shrink-0" aria-hidden />
            ) : (
              <ArrowDownRight className="h-3.5 w-3.5 shrink-0" aria-hidden />
            )
          ) : null}
          <span>
            {delta.value > 0 ? "+" : ""}
            {delta.value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}% vs période préc.
          </span>
        </div>
      ) : null}
    </CardContent>
  );

  if (href) {
    return (
      <Card className="overflow-hidden transition-colors hover:bg-muted/30">
        <Link to={href} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          {content}
        </Link>
      </Card>
    );
  }

  return <Card className="overflow-hidden">{content}</Card>;
}
