import type { LucideIcon } from "lucide-react";

export function EmptyChartState({
  icon: Icon,
  title,
  description,
  heightClass = "h-[220px]",
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  heightClass?: string;
}): JSX.Element {
  return (
    <div
      className={`flex ${heightClass} flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 px-4 text-center`}
      role="status"
    >
      <Icon className="text-muted-foreground h-8 w-8" aria-hidden />
      <p className="text-sm font-medium">{title}</p>
      <p className="text-muted-foreground max-w-xs text-xs">{description}</p>
    </div>
  );
}
