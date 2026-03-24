import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";

const statusBadgeVariants = cva(
  "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium transition-all duration-200",
  {
    variants: {
      variant: {
        success: "bg-gradient-to-r from-green-500 to-green-600 text-white shadow-sm",
        warning: "bg-gradient-to-r from-yellow-500 to-yellow-600 text-white shadow-sm",
        danger: "bg-gradient-to-r from-red-500 to-red-600 text-white shadow-sm",
        info: "bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-sm",
        default: "bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface StatusBadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof statusBadgeVariants> {}

function StatusBadge({ className, variant, ...props }: StatusBadgeProps) {
  return (
    <div className={cn(statusBadgeVariants({ variant }), className)} {...props} />
  );
}

export { StatusBadge, statusBadgeVariants };