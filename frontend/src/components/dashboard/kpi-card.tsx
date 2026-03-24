import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string;
  subtitle?: string;
  trend?: {
    type: "up" | "down" | "neutral";
    value: string;
  };
  className?: string;
}

export function KPICard({ title, value, subtitle, trend, className }: KPICardProps) {
  const getTrendIcon = () => {
    switch (trend?.type) {
      case "up":
        return <TrendingUp className="h-3 w-3" />;
      case "down":
        return <TrendingDown className="h-3 w-3" />;
      default:
        return <Minus className="h-3 w-3" />;
    }
  };

  const getTrendVariant = () => {
    switch (trend?.type) {
      case "up":
        return "success";
      case "down":
        return "danger";
      default:
        return "default";
    }
  };

  return (
    <Card className={cn("kpi-card animate-fade-in", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-2xl font-bold text-foreground">{value}</div>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
            )}
          </div>
          {trend && (
            <Badge variant={getTrendVariant() as any} className="flex items-center gap-1">
              {getTrendIcon()}
              {trend.value}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}