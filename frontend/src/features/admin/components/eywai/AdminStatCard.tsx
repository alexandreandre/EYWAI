import type { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type AdminStatCardProps = {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: LucideIcon;
  onClick?: () => void;
  variant?: "default" | "warning" | "success";
};

export function AdminStatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  onClick,
  variant = "default",
}: AdminStatCardProps) {
  return (
    <Card
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      className={cn(
        "text-left transition-shadow",
        onClick &&
          "cursor-pointer hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        variant === "warning" && "border-amber-200/80 dark:border-amber-900/50",
        variant === "success" && "border-emerald-200/80 dark:border-emerald-900/50",
      )}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon
          className={cn(
            "h-4 w-4",
            variant === "warning" && "text-amber-600",
            variant === "success" && "text-emerald-600",
            variant === "default" && "text-primary",
          )}
        />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        {subtitle ? <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p> : null}
      </CardContent>
    </Card>
  );
}
