import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

type PayrollSettingsSectionProps = {
  title: string;
  description?: string;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Style allégé pour sous-sections imbriquées. */
  nested?: boolean;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
};

export function PayrollSettingsSection({
  title,
  description,
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  nested = false,
  children,
  className,
  contentClassName,
}: PayrollSettingsSectionProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;

  const handleOpenChange = (next: boolean) => {
    if (!isControlled) setUncontrolledOpen(next);
    onOpenChange?.(next);
  };

  useEffect(() => {
    if (!isControlled) setUncontrolledOpen(defaultOpen);
  }, [defaultOpen, isControlled]);

  return (
    <Collapsible
      open={open}
      onOpenChange={handleOpenChange}
      className={cn(
        nested ? "rounded-md border border-dashed bg-muted/20" : "rounded-lg border bg-card",
        className,
      )}
    >
      <CollapsibleTrigger
        className={cn(
          "group flex w-full items-start gap-3 text-left transition-colors",
          nested ? "rounded-md px-3 py-2.5 hover:bg-muted/50" : "rounded-lg px-4 py-3 hover:bg-muted/40",
        )}
      >
        <ChevronDown
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
            open && "rotate-180",
          )}
          aria-hidden
        />
        <div className="min-w-0 flex-1 space-y-0.5">
          <p
            className={cn(
              "font-semibold uppercase tracking-wide text-muted-foreground",
              nested ? "text-xs" : "text-sm",
            )}
          >
            {title}
          </p>
          {description ? (
            <p className="text-sm font-normal normal-case tracking-normal text-muted-foreground/90">
              {description}
            </p>
          ) : null}
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className={cn("space-y-4 border-t", nested ? "px-3 pb-3 pt-2" : "px-4 pb-4 pt-3", contentClassName)}>
          {children}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export const PAYROLL_SECTION_KEYS = [
  "convention-collective",
  "taux-paie",
  "declarations",
  "temps-travail",
  "exoneration",
  "dialogue-social",
  "primes-distinctions",
  "oeth",
  "planning",
  "variables-paie",
  "avance",
] as const;

export type PayrollSectionKey = (typeof PAYROLL_SECTION_KEYS)[number];

export const DEFAULT_OPEN_PAYROLL_SECTIONS: PayrollSectionKey[] = [
  "convention-collective",
  "taux-paie",
];
