import { ExternalLink } from 'lucide-react';

import { classifyRateSourceLinks } from '@/lib/rateSourceLinks';
import { cn } from '@/lib/utils';

type RatesSourceLinksProps = {
  links: string[] | null | undefined;
  variant?: 'link' | 'pill';
};

function SourceLinkGroup({
  items,
  variant,
}: {
  items: { url: string; label: string }[];
  variant: 'link' | 'pill';
}) {
  if (items.length === 0) return null;

  if (variant === 'pill') {
    return (
      <div className="flex flex-wrap gap-2">
        {items.map(({ url, label }) => (
          <a
            key={url}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-full border border-border/80 bg-muted/30 px-2.5 py-1 text-xs text-foreground transition-colors hover:bg-muted/60"
          >
            <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" />
            {label}
          </a>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map(({ url, label }) => (
        <a
          key={url}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <ExternalLink className="h-3 w-3" />
          {label}
        </a>
      ))}
    </div>
  );
}

export function RatesSourceLinks({ links, variant = 'link' }: RatesSourceLinksProps) {
  const { official, complementary } = classifyRateSourceLinks(links);
  const items = [...official, ...complementary];
  if (items.length === 0) return null;

  const wrapperClass =
    variant === 'pill' ? undefined : cn('mt-3 space-y-2 border-t border-border/60 pt-2');

  return (
    <div className={wrapperClass}>
      <SourceLinkGroup items={items} variant={variant} />
    </div>
  );
}
