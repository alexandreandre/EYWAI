import type { ReactNode } from "react";

export function SectionHeading({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}): JSX.Element {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-lg font-semibold leading-tight tracking-tight">{title}</h2>
        {subtitle ? (
          <p className="text-muted-foreground line-clamp-2 text-sm">{subtitle}</p>
        ) : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}
